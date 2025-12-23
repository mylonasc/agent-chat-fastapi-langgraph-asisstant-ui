from assistant_stream_ce import RunController, create_run
from assistant_stream_ce.modules.langgraph import append_langgraph_event
from assistant_stream_ce.assistant_stream_models import ChatRequest
from assistant_stream_ce.serialization import DataStreamResponse
from typing import List, Optional
from langchain_core.messages import HumanMessage, AIMessage
from thread_manager import ThreadManager, ThreadMetadata
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uuid
app = FastAPI()

# Add this block
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with your frontend URL (e.g., ["http://localhost:3000"])
    allow_credentials=True,
    allow_methods=["*"], # This allows the POST and OPTIONS methods
    allow_headers=["*"],
)

thread_manager = ThreadManager()

class ScopedChatRequest(ChatRequest):
    """Extended request model to support thread and user identity."""
    thread_id: Optional[str] = None
    user_id: Optional[str] = "default_user"

@app.get("/threads", response_model=List[ThreadMetadata])
async def get_threads(user_id: str):
    """
    Fetch all threads for a specific user from the directory.
    """
    return thread_manager.list_user_threads(user_id)

@app.get("/threads/{thread_id}/messages")
async def get_thread_messages(thread_id: str):
    """
    Fetch the heavy message history from the LangGraph Checkpointer.
    """
    config = {"configurable": {"thread_id": thread_id}}
    state = graph.get_state(config)
    
    if not state or "messages" not in state.values:
        return {"messages": []}
    
    return {"messages": [m.model_dump() for m in state.values["messages"]]}


from pathlib import Path
curr_path= Path(__file__).resolve().parent.as_posix()
import sys
sys.path.append(curr_path)
from demo_agent.get_graph import make_agent_with_weather_tool, AgentState
import uuid # to give a unique ID to the messages (the front-end doesn't do that automatically)

# --- initialize the graph --- 
from langgraph.checkpoint.memory import MemorySaver # Added Checkpointer
checkpointer = MemorySaver()
graph = make_agent_with_weather_tool('gpt-4o-mini', checkpointer = checkpointer)

@app.post("/assistant")
async def chat_endpoint(request: ScopedChatRequest):  
    user_id = request.user_id or "default_user"
    if not request.thread_id:
        # This is the line that was missing or being bypassed
        new_thread = thread_manager.create_thread(user_id, title="New Chat")
        thread_id = new_thread.id
    else:
        thread_id = request.thread_id
        
    if not thread_id:
        new_thread = thread_manager.create_thread(user_id)
        thread_id = new_thread.id
        
    config = {"configurable": {"thread_id": thread_id}}
    
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
            config,
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
    return DataStreamResponse(stream, headers={"x-thread-id": thread_id})
