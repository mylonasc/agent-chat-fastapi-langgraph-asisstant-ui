from assistant_stream_ce import RunController, create_run
from assistant_stream_ce.modules.langgraph import append_langgraph_event
from assistant_stream_ce.assistant_stream_models import ChatRequest
from assistant_stream_ce.serialization import DataStreamResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from langchain_core.messages import HumanMessage
from thread_manager import ThreadManager, ThreadMetadata
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import uuid
import logging

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("assistant-backend")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-thread-id", "Content-Disposition", "X-Suggested-Filename"],
)

thread_manager = ThreadManager()

# --- NEW: in-memory persisted assistant-ui messages ---
# maps thread_id -> list[assistant-ui message json]
PERSISTED_AUI_MESSAGES: Dict[str, List[Dict[str, Any]]] = {}



class ScopedChatRequest(ChatRequest):
    thread_id: Optional[str] = None
    user_id: Optional[str] = "default_user"


class CreateThreadBody(BaseModel):
    localId: str
    user_id: str = "default_user"
    title: str = "New Chat"


class AppendMessageBody(BaseModel):
    # Store the FULL assistant-ui message object as JSON
    message: Dict[str, Any]


@app.get("/threads", response_model=List[ThreadMetadata])
async def get_threads(user_id: str = "default_user"):
    threads = thread_manager.list_user_threads(user_id)
    logger.info(f"Listing threads for {user_id}: Found {len(threads)}")
    return threads


@app.post("/threads", response_model=ThreadMetadata)
async def create_thread(body: CreateThreadBody):
    existing = thread_manager.get(body.localId)
    if existing:
        return existing

    logger.info(f"Thread registered: {body.localId}")
    return thread_manager.create_thread(body.user_id, title=body.title, thread_id=body.localId)


@app.get("/threads/{thread_id}", response_model=ThreadMetadata)
async def fetch_thread(thread_id: str ):
    thread = thread_manager.get(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread

@app.get("/threads/{thread_id}/messages")
async def get_thread_messages(thread_id: str):
    """
    Preferred: return assistant-ui message objects persisted via history.append.
    Fallback: return LangGraph checkpointer messages (text-only) if no persisted aui messages exist.
    """
    if thread_id in PERSISTED_AUI_MESSAGES:
        msgs = PERSISTED_AUI_MESSAGES[thread_id]
        logger.info(f"Returning {len(msgs)} persisted AUI messages for {thread_id}")
        return {"messages": msgs}

    # --- fallback to old behavior (LangGraph state dumps) ---
    logger.info(f"No persisted AUI messages for {thread_id}. Falling back to graph state.")
    config = {"configurable": {"thread_id": thread_id}}
    state = graph.get_state(config)

    if not state or "messages" not in state.values:
        logger.warning(f"No state/messages found in checkpointer for thread: {thread_id}")
        return {"messages": []}

    msgs = state.values["messages"]
    logger.info(f"Retrieved {len(msgs)} messages from checkpointer for {thread_id}")
    # This is NOT assistant-ui shaped; it’s only for backward compatibility.
    return {"messages": [m.model_dump() for m in msgs]}


@app.post("/threads/{thread_id}/messages")
async def append_thread_message(thread_id: str, body: AppendMessageBody):
    """
    Called by assistant-ui history.append(message).
    Store message verbatim so tool UI parts can rehydrate.
    """
    if thread_id not in PERSISTED_AUI_MESSAGES:
        PERSISTED_AUI_MESSAGES[thread_id] = []
    PERSISTED_AUI_MESSAGES[thread_id].append(body.message)
    logger.info(f"Appended message to {thread_id}. Total now: {len(PERSISTED_AUI_MESSAGES[thread_id])}")
    return {"ok": True}

# --- Agent Logic ---
from pathlib import Path
import sys
curr_path = Path(__file__).resolve().parent.as_posix()
sys.path.append(curr_path)
from demo_agent.get_graph import make_agent_with_weather_tool
from langgraph.checkpoint.memory import MemorySaver

# NOTE: MemorySaver is lost if uvicorn restarts!
checkpointer = MemorySaver()
graph = make_agent_with_weather_tool("gpt-4o-mini", checkpointer=checkpointer)


@app.post("/assistant") 
async def chat_endpoint(req: Request, request: ScopedChatRequest):
    
    payload = await req.json()
    
    logger.info(f"/assistant payload keys: {list(payload.keys())}")
    logger.info(f"/assistant payload : {str(payload)}")

    user_id = request.user_id or "default_user"

    # Resolve thread_id from top-level or request.state
    thread_id = request.thread_id
    if (not thread_id or thread_id == "new") and isinstance(request.state, dict):
        thread_id = request.state.get("thread_id")

    logger.info(f"Resolved Thread ID: {thread_id}")

    if not thread_id:
        logger.error(f"Failed to find thread_id. State was: {request.state}")
        raise HTTPException(400, "thread_id missing from request state")

    # Ensure thread metadata exists
    if not thread_manager.get(thread_id):
        logger.info(f"Creating missing metadata for thread: {thread_id}")
        thread_manager.create_thread(user_id, title="New Chat", thread_id=thread_id)

    config = {"configurable": {"thread_id": thread_id}}

    async def run_callback(controller: RunController):
        if controller.state is None:
            controller.state = {"messages": []}
        if 'messages' not in controller.state:
            controller.state['messages'] = []

        for command in request.commands:
            if command.type == "add-message":
                text = " ".join([p.text for p in command.message.parts if p.type == "text"])
                if text:
                    msg_id = getattr(command.message, "id", str(uuid.uuid4()))
                    _msg = HumanMessage(content=text, id=msg_id)
                    controller.state["messages"].append(_msg.model_dump())

        input_msg = {"messages": list(controller.state["messages"])}

        async for namespace, event_type, chunk in graph.astream(
            input_msg, config, stream_mode=["messages"], subgraphs=True
        ):
            append_langgraph_event(controller.state, namespace, event_type, chunk)

    stream = create_run(run_callback, state=request.state)
    return DataStreamResponse(stream)
