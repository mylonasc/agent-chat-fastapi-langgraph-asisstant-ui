import argparse
import logging
import os
import uuid
from pathlib import Path

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

from .demo_agent.get_graph import make_agent_with_weather_tool


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


def create_app(web_dir: Path | None = None) -> FastAPI:
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logger.warning(
            "OPENAI_API_KEY is not set; the /assistant endpoint will return 503."
        )

    graph = make_agent_with_weather_tool("gpt-4o-mini") if openai_api_key else None
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
        if not openai_api_key:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "OPENAI_API_KEY not configured",
                    "message": "Please set the OPENAI_API_KEY environment variable to use the chat functionality.",
                    "instructions": "Add OPENAI_API_KEY=your-key to your .env file and restart the server.",
                },
            )

        assert graph is not None

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
