import argparse
import importlib
import logging
import os
import uuid
from pathlib import Path
from typing import Callable

import uvicorn
from assistant_stream_ce import RunController, create_run
from assistant_stream_ce.assistant_stream_models import ChatRequest
from assistant_stream_ce.modules.langgraph import append_langgraph_event
from assistant_stream_ce.serialization import DataStreamResponse
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import HumanMessage
from starlette.exceptions import HTTPException as StarletteHTTPException

from .demo_agent.local_agent import make_local_agent


logger = logging.getLogger(__name__)
DEFAULT_WEB_DIR = Path(__file__).parent / "web"


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


def _load_factory(path: str) -> Callable[[], object]:
    """Import a ``package.module:factory`` (or ``package.module.factory``) path."""
    module_name, _, attr = path.partition(":")
    if not attr:
        module_name, _, attr = path.rpartition(".")
    if not module_name or not attr:
        raise ValueError(
            f"Invalid MINIMAL_AGENT_FACTORY {path!r}: "
            "expected 'package.module:factory'."
        )
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise ImportError(
            f"Could not import module {module_name!r} "
            f"from MINIMAL_AGENT_FACTORY={path!r}."
        ) from exc
    try:
        factory = getattr(module, attr)
    except AttributeError as exc:
        raise ImportError(
            f"Module {module_name!r} has no attribute {attr!r} "
            f"(from MINIMAL_AGENT_FACTORY={path!r})."
        ) from exc
    if not callable(factory):
        raise TypeError(
            f"MINIMAL_AGENT_FACTORY={path!r} is not callable. "
            "Point it at a zero-argument function returning a compiled graph."
        )
    return factory


def _default_graph_factory() -> Callable[[], object]:
    configured = os.getenv("MINIMAL_AGENT_FACTORY")
    if configured:
        logger.info("Using custom agent factory %s", configured)
        return _load_factory(configured)
    return make_local_agent


def create_app(
    web_dir: Path | None = None,
    graph_factory: Callable[[], object] | None = None,
) -> FastAPI:
    """Create the FastAPI app serving the bundled UI and ``/assistant``.

    Args:
        web_dir: Directory with the prebuilt static UI. Defaults to the
            bundled ``web/`` payload (or ``MINIMAL_WEB_DIR``).
        graph_factory: Zero-argument callable returning a compiled LangGraph
            graph. Defaults to the key-free local demo agent, or to
            ``MINIMAL_AGENT_FACTORY`` when that env var is set. See the
            package README section "Creating a compatible agent".
    """
    factory = graph_factory or _default_graph_factory()
    graph = factory()
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
