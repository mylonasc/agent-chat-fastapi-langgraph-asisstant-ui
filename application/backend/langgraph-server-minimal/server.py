import os
from assistant_stream_ce import RunController, create_run
from assistant_stream_ce.modules.langgraph import append_langgraph_event
from assistant_stream_ce.assistant_stream_models import ChatRequest
from assistant_stream_ce.serialization import DataStreamResponse
from langchain_core.messages import HumanMessage, AIMessage

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print(
        "WARNING: OPENAI_API_KEY not set. The /assistant endpoint will return an error message."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from pathlib import Path

curr_path = Path(__file__).resolve().parent.as_posix()
import sys

sys.path.append(curr_path)
from demo_agent.get_graph import make_agent_with_weather_tool, AgentState
import uuid

graph = make_agent_with_weather_tool("gpt-4o-mini")


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
