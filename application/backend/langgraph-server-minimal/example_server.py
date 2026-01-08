from assistant_stream_ce import RunController, create_run
from assistant_stream_ce.modules.langgraph import append_langgraph_event
from assistant_stream_ce.assistant_stream_models import ChatRequest
from assistant_stream_ce.serialization import DataStreamResponse
from langchain_core.messages import HumanMessage, AIMessage

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Add this block
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with your frontend URL (e.g., ["http://localhost:3000"])
    allow_credentials=True,
    allow_methods=["*"], # This allows the POST and OPTIONS methods
    allow_headers=["*"],
)

from pathlib import Path
curr_path= Path(__file__).resolve().parent.as_posix()
import sys
sys.path.append(curr_path)
from demo_agent.get_graph import make_agent_with_weather_tool, AgentState
import uuid # to give a unique ID to the messages (the front-end doesn't do that automatically)

graph = make_agent_with_weather_tool('gpt-4o-mini')


@app.post("/assistant")
async def chat_endpoint(request: ChatRequest):
    async def run_callback(controller: RunController):
        # 1. Initialize state from the frontend's current state
        if controller.state is None:
            controller.state = {"messages": []}
        
        # 2. Extract and Append the Human Message
        for command in request.commands:
            if command.type == "add-message":
                text = " ".join([p.text for p in command.message.parts if p.type == "text"])
                if text:
                    # Explicitly use the LangChain format the frontend expects
                    msg_id = getattr(command.message, 'id', str(uuid.uuid4()))
                    _msg = HumanMessage(content = text, id = msg_id)
                    controller.state["messages"].append(_msg.model_dump())

        # 3. Stream from LangGraph
        input_msg = {"messages": list(controller.state["messages"])}
        
        
        async for namespace, event_type, chunk in graph.astream(
            input_msg,
            stream_mode=["messages"], # Use only 'messages' for stability
            subgraphs=True
        ):
            append_langgraph_event(
                controller.state,
                namespace,
                event_type,
                chunk
            )
            
    stream = create_run(run_callback, state=request.state)
    return DataStreamResponse(stream)
