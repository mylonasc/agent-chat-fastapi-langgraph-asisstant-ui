import os
import logging
from pathlib import Path

from assistant_stream_ce import RunController, create_run
from assistant_stream_ce.modules.langgraph import append_langgraph_event
from assistant_stream_ce.assistant_stream_models import ChatRequest
from assistant_stream_ce.serialization import DataStreamResponse
from langchain_core.messages import HumanMessage, AIMessage

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException


logger = logging.getLogger(__name__)
WEB_DIR = Path(os.getenv("MINIMAL_WEB_DIR", Path(__file__).parent / "web"))


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

app = FastAPI()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print(
        "WARNING: OPENAI_API_KEY not set. The /assistant endpoint will return an error message."
    )

app.add_middleware(
    CORSMiddleware,
    # The bundled UI is same-origin; permissive CORS remains for split-port development.
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

curr_path = Path(__file__).resolve().parent.as_posix()
import sys

sys.path.append(curr_path)
from demo_agent.get_graph import make_agent_with_weather_tool, AgentState
import uuid

graph = make_agent_with_weather_tool("gpt-4o-mini") if OPENAI_API_KEY else None


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/assistant")
async def chat_endpoint(request: ChatRequest):
    if not OPENAI_API_KEY:
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
        # 1. Initialize state from the frontend's current state
        if controller.state is None:
            controller.state = {"messages": []}

        # 2. Extract and Append the Human Message
        for command in request.commands:
            if command.type == "add-message":
                text = " ".join(
                    [p.text for p in command.message.parts if p.type == "text"]
                )
                if text:
                    # Explicitly use the LangChain format the frontend expects
                    msg_id = getattr(command.message, "id", str(uuid.uuid4()))
                    _msg = HumanMessage(content=text, id=msg_id)
                    controller.state["messages"].append(_msg.model_dump())

        # 3. Stream from LangGraph
        input_msg = {"messages": list(controller.state["messages"])}

        async for namespace, event_type, chunk in graph.astream(
            input_msg,
            stream_mode=["messages"],  # Use only 'messages' for stability
            subgraphs=True,
        ):
            append_langgraph_event(controller.state, namespace, event_type, chunk)

    stream = create_run(run_callback, state=request.state)
    return DataStreamResponse(stream)


# Mount last so API and FastAPI documentation routes always take precedence.
if WEB_DIR.is_dir() and (WEB_DIR / "index.html").is_file():
    app.mount("/", SPAStaticFiles(directory=WEB_DIR, html=True), name="web")
else:
    logger.warning(
        "Minimal UI build not found at %s; starting in API-only mode. "
        "Set MINIMAL_WEB_DIR to a frontend-minimal/out directory.",
        WEB_DIR,
    )
