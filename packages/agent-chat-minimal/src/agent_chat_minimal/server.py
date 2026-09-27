import argparse
import logging
import os
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import uvicorn
from assistant_stream_ce import RunController, create_run
from assistant_stream_ce.assistant_stream_models import ChatRequest
from assistant_stream_ce.modules.langgraph import append_langgraph_event
from assistant_stream_ce.serialization import DataStreamResponse
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import HumanMessage
from starlette.exceptions import HTTPException as StarletteHTTPException


logger = logging.getLogger(__name__)
DEFAULT_WEB_DIR = Path(__file__).parent / "web"


@runtime_checkable
class ChatGraph(Protocol):
    """Minimal contract for a graph servable by ``create_app``.

    The graph must accept ``{"messages": [...]}`` as input and support
    ``astream(input, stream_mode=["messages"], subgraphs=True)`` yielding
    ``(namespace, event_type, chunk)`` triples consumable by
    ``assistant_stream_ce.modules.langgraph.append_langgraph_event``.
    """

    def astream(self, *args: Any, **kwargs: Any) -> Any: ...


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        reserved_paths = ("assistant", "health", "docs", "openapi.json")
        if path in reserved_paths or path.startswith(
            tuple(f"{prefix}/" for prefix in reserved_paths)
        ):
            raise StarletteHTTPException(status_code=404)

        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            return await super().get_response("index.html", scope)

        if response.status_code == 404:
            return await super().get_response("index.html", scope)
        return response


def _default_graph_factory() -> Any | None:
    """Legacy behavior: weather demo if credentials allow, else None."""
    from .demo_agent.get_graph import make_agent_with_weather_tool

    model = os.getenv("MODEL", "gpt-4o-mini")
    try:
        return make_agent_with_weather_tool(model)
    except Exception as exc:  # e.g. missing credentials at import/startup
        logger.warning("Default agent failed to build: %s", exc)
        return None


def create_app(
    graph: ChatGraph | None = None,
    graph_factory: Callable[[], ChatGraph | None] | None = None,
    web_dir: Path | None = None,
) -> FastAPI:
    """Create the FastAPI app serving a LangGraph agent.

    Args:
        graph: Already-compiled graph. Takes precedence over ``graph_factory``.
        graph_factory: Zero-arg callable building the graph. Deferred so
            missing credentials fail at startup, not import. When neither
            ``graph`` nor ``graph_factory`` is given, the legacy weather demo
            is built when possible, else ``/assistant`` returns 503.
        web_dir: Override for the bundled static UI directory.
    """
    openai_api_key = os.getenv("OPENAI_API_KEY")
    factory_error: str | None = None
    using_default = graph is None and graph_factory is None

    if graph is None and graph_factory is not None:
        try:
            graph = graph_factory()
        except Exception as exc:
            factory_error = str(exc)
            logger.warning("graph_factory failed: %s", exc)
            graph = None

    if using_default:
        if not openai_api_key:
            logger.warning(
                "OPENAI_API_KEY is not set; the /assistant endpoint will return 503."
            )
            graph = None
        else:
            graph = _default_graph_factory()
            if graph is None:
                factory_error = "default weather agent failed to build"
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        # The bundled UI is same-origin; permissive CORS supports split-port development.
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/assistant")
    async def chat_endpoint(request: ChatRequest):
        if graph is None:
            if using_default and not openai_api_key:
                raise HTTPException(
                    status_code=503,
                    detail={
                        "error": "OPENAI_API_KEY not configured",
                        "message": "Please set the OPENAI_API_KEY environment variable to use the chat functionality.",
                        "instructions": "Add OPENAI_API_KEY=your-key to your .env file and restart the server.",
                    },
                )
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "agent_not_ready",
                    "message": "No graph was provided or the factory failed.",
                    "hint": factory_error or "Pass graph= or graph_factory= to create_app().",
                },
            )

        async def run_callback(controller: RunController):
            if controller.state is None:
                controller.state = {"messages": []}

            for command in request.commands:
                if command.type == "add-message":
                    text = " ".join(
                        part.text
                        for part in command.message.parts
                        if part.type == "text"
                    )
                    if text:
                        message_id = getattr(command.message, "id", str(uuid.uuid4()))
                        message = HumanMessage(content=text, id=message_id)
                        controller.state["messages"].append(message.model_dump())

            input_message = {"messages": list(controller.state["messages"])}
            async for namespace, event_type, chunk in graph.astream(
                input_message,
                stream_mode=["messages"],
                subgraphs=True,
            ):
                append_langgraph_event(
                    controller.state, namespace, event_type, chunk
                )

        stream = create_run(run_callback, state=request.state)
        return DataStreamResponse(stream)

    resolved_web_dir = Path(
        web_dir or os.getenv("MINIMAL_WEB_DIR", DEFAULT_WEB_DIR)
    ).resolve()
    if resolved_web_dir.is_dir() and (resolved_web_dir / "index.html").is_file():
        app.mount(
            "/",
            SPAStaticFiles(directory=resolved_web_dir, html=True),
            name="web",
        )
    else:
        logger.warning(
            "Minimal UI build not found at %s; starting in API-only mode. "
            "Set MINIMAL_WEB_DIR to a frontend-minimal/out directory.",
            resolved_web_dir,
        )

    return app


app = create_app()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Serve the minimal chat application")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8011)
    args = parser.parse_args(argv)
    uvicorn.run(create_app(), host=args.host, port=args.port)
