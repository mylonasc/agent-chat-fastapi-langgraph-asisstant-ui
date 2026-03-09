from assistant_stream_ce import RunController, create_run
from assistant_stream_ce.modules.langgraph import append_langgraph_event
from assistant_stream_ce.assistant_stream_models import ChatRequest
from assistant_stream_ce.serialization import DataStreamResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from langchain_core.messages import HumanMessage
from .thread_manager import ThreadManager, ThreadMetadata
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import uuid
import logging
import os
import importlib.util
from threading import RLock

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print(
        "WARNING: OPENAI_API_KEY not set. The /assistant endpoint will return an error message."
    )

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

# Mount tool routers
from tools.registry import TOOL_REGISTRY

for router in TOOL_REGISTRY.get_routers():
    app.include_router(router)


@app.get("/tools/overview")
async def get_tools_overview(user_id: str = "default_user"):
    from tools.web_rag.background_jobs import INDEXING_MANAGER
    from tools.web_rag.status import get_index_status

    tool_names = sorted(list(TOOL_REGISTRY.tools.keys()))
    rag_config = CONFIG_STORE.get("web_rag") or {
        "embedding_provider": "fastembed",
        "pdf_parser": "pypdf",
    }
    search_config = CONFIG_STORE.get("web_search") or {}

    docling_available = importlib.util.find_spec("docling") is not None

    index_status = await asyncio.to_thread(get_index_status, rag_config, user_id)
    jobs = await asyncio.to_thread(
        INDEXING_MANAGER.list_jobs, user_id=user_id, limit=10
    )

    return {
        "user_id": user_id,
        "tools": {
            "available": tool_names,
            "configs": {
                "web_rag": rag_config,
                "web_search": search_config,
            },
        },
        "runtime": {
            "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
            "serper_configured": bool(os.getenv("SERPER_API_KEY")),
            "docling_available": docling_available,
            "docling_variant": os.getenv("DOCLING_VARIANT", "none"),
        },
        "web_rag_state": {
            "index": index_status,
            "jobs": jobs,
        },
        "docling": {
            "is_standalone_tool": False,
            "owner_tool": "web_rag",
            "description": "Docling is a parser backend used by web_rag ingestion.",
            "config_keys": ["pdf_parser", "docling_device"],
        },
    }


# --- Startup Validation ---
from .startup_validation import run_startup_validation
from tools.config import CONFIG_STORE


@app.on_event("startup")
def startup_checks():
    # Use web_rag config if present, otherwise minimal default
    config = CONFIG_STORE.get("web_rag") or {
        "embedding_provider": "fastembed",
        "pdf_parser": "pypdf",
    }
    run_startup_validation(config)
    if not os.getenv("SERPER_API_KEY"):
        logger.warning(
            "SERPER_API_KEY is not set. web_search tool calls will return a configuration error."
        )


# --- NEW: in-memory persisted assistant-ui messages ---
# maps thread_id -> list[assistant-ui message json]
PERSISTED_AUI_MESSAGES: Dict[str, List[Dict[str, Any]]] = {}
PERSISTED_AUI_MESSAGES_LOCK = RLock()


def _append_tool_update(state: Dict[str, Any], payload: Any) -> None:
    updates = state.get("tool_updates")
    if not isinstance(updates, list):
        updates = []

    updates.append(payload)
    state["tool_updates"] = updates[-200:]


def _append_updates_from_graph_chunk(state: Dict[str, Any], chunk: Any) -> None:
    if not isinstance(chunk, dict):
        return

    for node_name, node_payload in chunk.items():
        if not isinstance(node_payload, dict):
            continue
        messages = node_payload.get("messages")
        if not isinstance(messages, list):
            continue

        for msg in messages:
            msg_type = getattr(msg, "type", None)

            if node_name == "agent" and msg_type == "ai":
                for call in getattr(msg, "tool_calls", []) or []:
                    _append_tool_update(
                        state,
                        {
                            "tool": call.get("name"),
                            "tool_call_id": call.get("id"),
                            "status": "requested",
                        },
                    )

            if node_name == "tools" and msg_type == "tool":
                _append_tool_update(
                    state,
                    {
                        "tool": getattr(msg, "name", None),
                        "tool_call_id": getattr(msg, "tool_call_id", None),
                        "status": "completed",
                    },
                )


def _sanitize_langchain_message_history(
    messages: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Drop AI messages that contain tool_calls without matching ToolMessages.

    A failed tool invocation can leave chat history in an invalid state for
    LangGraph/LangChain providers (INVALID_CHAT_HISTORY).
    """

    tool_message_ids = {
        m.get("tool_call_id")
        for m in messages
        if isinstance(m, dict) and m.get("type") == "tool" and m.get("tool_call_id")
    }

    sanitized: List[Dict[str, Any]] = []
    dropped = 0

    for msg in messages:
        if not isinstance(msg, dict):
            sanitized.append(msg)
            continue

        if msg.get("type") != "ai":
            sanitized.append(msg)
            continue

        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            sanitized.append(msg)
            continue

        call_ids = [tc.get("id") for tc in tool_calls if isinstance(tc, dict)]
        if call_ids and all(cid in tool_message_ids for cid in call_ids):
            sanitized.append(msg)
            continue

        dropped += 1

    if dropped:
        logger.warning(
            "Dropped %s invalid AI message(s) with unresolved tool_calls before graph invoke",
            dropped,
        )

    return sanitized


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


class RenameThreadBody(BaseModel):
    title: str


@app.get("/threads", response_model=List[ThreadMetadata])
async def get_threads(user_id: str = "default_user", include_archived: bool = False):
    threads = thread_manager.list_user_threads(
        user_id, include_archived=include_archived
    )
    logger.info(f"Listing threads for {user_id}: Found {len(threads)}")
    return list(reversed(threads))


@app.post("/threads", response_model=ThreadMetadata)
async def create_thread(body: CreateThreadBody):
    existing = thread_manager.get(body.localId)
    if existing:
        return existing

    logger.info(f"Thread registered: {body.localId}")
    return thread_manager.create_thread(
        body.user_id, title=body.title, thread_id=body.localId
    )


@app.get("/threads/{thread_id}", response_model=ThreadMetadata)
async def fetch_thread(thread_id: str):
    thread = thread_manager.get(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread


@app.patch("/threads/{thread_id}", response_model=ThreadMetadata)
async def rename_thread(thread_id: str, body: RenameThreadBody):
    thread = thread_manager.get(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    new_title = (body.title or "").strip()
    if not new_title:
        raise HTTPException(status_code=400, detail="title must not be empty")

    thread_manager.update_title(thread_id, new_title)
    updated = thread_manager.get(thread_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Thread not found")
    return updated


@app.post("/threads/{thread_id}/archive", response_model=ThreadMetadata)
async def archive_thread(thread_id: str):
    thread = thread_manager.get(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    thread_manager.archive(thread_id)
    updated = thread_manager.get(thread_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Thread not found")
    return updated


@app.post("/threads/{thread_id}/unarchive", response_model=ThreadMetadata)
async def unarchive_thread(thread_id: str):
    thread = thread_manager.get(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    thread_manager.unarchive(thread_id)
    updated = thread_manager.get(thread_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Thread not found")
    return updated


@app.delete("/threads/{thread_id}")
async def delete_thread(thread_id: str):
    thread = thread_manager.get(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    thread_manager.delete(thread_id)
    with PERSISTED_AUI_MESSAGES_LOCK:
        PERSISTED_AUI_MESSAGES.pop(thread_id, None)
    return {"ok": True}


@app.get("/threads/{thread_id}/messages")
async def get_thread_messages(thread_id: str):
    """
    Preferred: return assistant-ui message objects persisted via history.append.
    Fallback: return LangGraph checkpointer messages (text-only) if no persisted aui messages exist.
    """
    with PERSISTED_AUI_MESSAGES_LOCK:
        msgs = list(PERSISTED_AUI_MESSAGES.get(thread_id, []))
    if msgs:
        logger.info(f"Returning {len(msgs)} persisted AUI messages for {thread_id}")
        return {"messages": msgs}

    # --- fallback to old behavior (LangGraph state dumps) ---
    logger.info(
        f"No persisted AUI messages for {thread_id}. Falling back to graph state."
    )
    config = {"configurable": {"thread_id": thread_id}}
    state = await asyncio.to_thread(graph.get_state, config)

    if not state or "messages" not in state.values:
        logger.warning(
            f"No state/messages found in checkpointer for thread: {thread_id}"
        )
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
    with PERSISTED_AUI_MESSAGES_LOCK:
        if thread_id not in PERSISTED_AUI_MESSAGES:
            PERSISTED_AUI_MESSAGES[thread_id] = []
        PERSISTED_AUI_MESSAGES[thread_id].append(body.message)
        total = len(PERSISTED_AUI_MESSAGES[thread_id])
    logger.info(f"Appended message to {thread_id}. Total now: {total}")
    return {"ok": True}


# --- Agent Logic ---
from pathlib import Path
import sys

curr_path = Path(__file__).resolve().parent.as_posix()
sys.path.append(curr_path)

# from examples.demo_agent.get_graph import make_agent_with_weather_tool
from .get_graph import make_web_rag_search_agent

from langgraph.checkpoint.memory import MemorySaver

# NOTE: MemorySaver is lost if uvicorn restarts!
checkpointer = MemorySaver()
# Default full agent: Web Search + Hybrid RAG
graph = make_web_rag_search_agent(
    model_name="gpt-4o-mini",
    checkpointer=checkpointer,
)


@app.post("/assistant")
async def chat_endpoint(req: Request, request: ScopedChatRequest):
    if not OPENAI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "OPENAI_API_KEY not configured",
                "message": "Please set the OPENAI_API_KEY environment variable to use the chat functionality.",
                "instructions": "Add OPENAI_API_KEY=your-key to your .env file and restart the server.",
            },
        )

    payload = await req.json()

    logger.info(f"/assistant payload keys: {list(payload.keys())}")

    user_id = request.user_id or "default_user"

    # Resolve thread_id from top-level or request.state
    thread_id = request.thread_id
    if (not thread_id or thread_id == "new") and isinstance(request.state, dict):
        thread_id = request.state.get("thread_id")

    logger.info(f"Resolved Thread ID: {thread_id}")

    if not thread_id:
        # Auto-generate thread_id if missing (to satisfy tests and UX)
        thread_id = str(uuid.uuid4())
        logger.info(f"Auto-generated thread_id: {thread_id}")

    # Ensure thread metadata exists
    if not thread_manager.get(thread_id):
        logger.info(f"Creating missing metadata for thread: {thread_id}")
        thread_manager.create_thread(user_id, title="New Chat", thread_id=thread_id)

    config = {"configurable": {"thread_id": thread_id}}

    async def run_callback(controller: RunController):
        if controller.state is None:
            controller.state = {"messages": []}
        if "messages" not in controller.state:
            controller.state["messages"] = []
        if "tool_updates" not in controller.state:
            controller.state["tool_updates"] = []

        for command in request.commands:
            if command.type == "add-message":
                text = " ".join(
                    [p.text for p in command.message.parts if p.type == "text"]
                )
                if text:
                    msg_id = getattr(command.message, "id", str(uuid.uuid4()))
                    _msg = HumanMessage(content=text, id=msg_id)
                    controller.state["messages"].append(_msg.model_dump())

        sanitized_messages = _sanitize_langchain_message_history(
            list(controller.state["messages"])
        )
        controller.state["messages"] = sanitized_messages

        input_msg = {"messages": sanitized_messages}

        async for namespace, event_type, chunk in graph.astream(
            input_msg,
            config,
            stream_mode=["messages", "updates", "custom"],
            subgraphs=True,
        ):
            if event_type == "custom":
                _append_tool_update(controller.state, chunk)
                continue
            if event_type == "updates":
                _append_updates_from_graph_chunk(controller.state, chunk)
            if event_type == "messages":
                try:
                    msg = chunk[0]
                    if getattr(msg, "type", None) == "tool":
                        _append_tool_update(
                            controller.state,
                            {
                                "tool": getattr(msg, "name", None),
                                "tool_call_id": getattr(msg, "tool_call_id", None),
                                "status": "completed",
                            },
                        )
                except Exception:
                    pass
            append_langgraph_event(controller.state, namespace, event_type, chunk)

    stream = create_run(run_callback, state=request.state)
    return DataStreamResponse(stream)
