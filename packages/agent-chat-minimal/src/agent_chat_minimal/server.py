import inspect
import logging
import uuid
from collections.abc import Callable
from typing import Any, Optional, Protocol, runtime_checkable

from assistant_stream_ce import RunController, create_run
from assistant_stream_ce.assistant_stream_models import ChatRequest
from assistant_stream_ce.modules.langgraph import append_langgraph_event
from assistant_stream_ce.serialization import DataStreamResponse
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from .capabilities import CapabilityProvider
from .config import Settings
from .static_ui import DEFAULT_WEB_DIR, DEFAULT_WEB_FULL_DIR, mount_static_ui
from .threads import ThreadManager, ThreadMessageStore, ThreadMetadata


logger = logging.getLogger(__name__)


@runtime_checkable
class ChatGraph(Protocol):
    """Minimal contract for a graph servable by ``create_app``.

    The graph must accept ``{"messages": [...]}`` as input and support
    ``astream(input, config, stream_mode=[...], subgraphs=True)`` yielding
    ``(namespace, event_type, chunk)`` triples consumable by
    ``assistant_stream_ce.modules.langgraph.append_langgraph_event``.
    """

    def astream(self, *args: Any, **kwargs: Any) -> Any: ...


class ScopedChatRequest(ChatRequest):
    """Chat request with full-stack thread scoping (same shape as full backend)."""

    thread_id: Optional[str] = None
    user_id: Optional[str] = "default_user"


class CreateThreadBody(BaseModel):
    localId: str
    user_id: str = "default_user"
    title: str = "New Chat"


class AppendMessageBody(BaseModel):
    message: dict[str, Any]


class RenameThreadBody(BaseModel):
    title: str


def _next_ui_message_id(messages: list) -> str:
    """Match assistant-ui's index after joining AI/tool/AI sequences."""
    count = 0
    assistant_group_open = False
    for message in messages:
        message_type = message.get("type") if isinstance(message, dict) else None
        if message_type in {"human", "system"}:
            count += 1
            assistant_group_open = False
        elif message_type == "ai" and not assistant_group_open:
            count += 1
            assistant_group_open = True
    return str(count)


def default_prepare_state(state: dict, request: ChatRequest) -> list:
    """Fold ``add-message`` commands into message dicts (the default reducer)."""
    messages = list(state.get("messages", []))
    for command in request.commands:
        if command.type == "add-message":
            text = " ".join(
                part.text for part in command.message.parts if part.type == "text"
            )
            if text:
                message_id = getattr(command.message, "id", None)
                if not message_id:
                    message_id = _next_ui_message_id(messages)
                message = HumanMessage(content=text, id=message_id)
                messages.append(message.model_dump())
    return messages


def resolve_thread_id(request: ChatRequest, default: str = "default") -> str:
    """Derive a persistence thread id from the request (default: "default").

    Checks the top-level ``thread_id`` field (full-stack shape), then
    ``request.state["thread_id"]``, then ``request.runConfig``, so graphs
    compiled with a LangGraph checkpointer get stable per-conversation
    threads without any client change.
    """
    top = getattr(request, "thread_id", None)
    if top and top != "new":
        return str(top)
    for source in (request.state, request.runConfig):
        if isinstance(source, dict) and source.get("thread_id"):
            thread_id = str(source["thread_id"])
            if thread_id != "new":
                return thread_id
    return default


def _append_tool_update(state: dict[str, Any], payload: Any) -> None:
    updates = state.get("tool_updates")
    if not isinstance(updates, list):
        updates = []
    updates.append(payload)
    state["tool_updates"] = updates[-200:]


def _append_updates_from_graph_chunk(state: dict[str, Any], chunk: Any) -> None:
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


def _sanitize_langchain_message_history(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop AI messages with tool_calls lacking matching ToolMessages.

    A failed tool invocation can leave history invalid for providers
    (``INVALID_CHAT_HISTORY``); the full backend applies the same guard.
    """
    tool_message_ids = {
        m.get("tool_call_id")
        for m in messages
        if isinstance(m, dict) and m.get("type") == "tool" and m.get("tool_call_id")
    }
    sanitized: list[dict[str, Any]] = []
    dropped = 0
    for msg in messages:
        if not isinstance(msg, dict) or msg.get("type") != "ai":
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
            "Dropped %s invalid AI message(s) with unresolved tool_calls", dropped
        )
    return sanitized


def _default_checkpointer() -> Any:
    from langgraph.checkpoint.memory import MemorySaver

    return MemorySaver()


def _build_app(
    settings: Settings,
    capability_provider: CapabilityProvider,
    graph: ChatGraph | None = None,
    graph_factory: Callable[..., ChatGraph | None] | None = None,
    agents: dict[str, Callable[..., ChatGraph | None]] | None = None,
    prepare_state: Callable[[dict, ChatRequest], list] | None = None,
    checkpointer: Any | None = "memory",
    thread_manager: ThreadManager | None = None,
    message_store: ThreadMessageStore | None = None,
) -> FastAPI:
    """Build routes and transport from composition-root dependencies.

    Single-agent override (takes precedence):
        ``create_app(graph=my_graph)`` or
        ``create_app(graph_factory=make_my_agent)`` serves one agent as both
        ``POST /assistant`` and ``GET /agents == ["default"]``.

    Multi-agent registry (default):
        ``create_app()`` serves the built-in registry (``weather`` +
        ``calculator`` plus ``agent_chat.agents`` entry points) at
        ``POST /assistant/{agent_id}``, with ``POST /assistant`` aliasing
        ``default_agent``. Pass ``agents={...}`` to override.

    Full-stack threads:
        ``GET/POST /threads``, ``GET/PATCH/DELETE /threads/{id}``,
        ``POST /threads/{id}/archive|unarchive`` and
        ``GET/POST /threads/{id}/messages`` mirror the full backend, so
        ``frontend-full`` works against either server. ``POST /assistant``
        accepts the scoped shape (``thread_id``/``user_id`` alongside
        ``commands``/``state``) and auto-creates missing thread metadata.

    Args:
        graph: Already-compiled graph (single-agent mode).
        graph_factory: Factory building the graph (single-agent mode, deferred
            build). Receives ``checkpointer=`` when its signature accepts it.
        agents: Mapping of name -> factory (multi-agent mode).
        prepare_state: ``(state, request) -> message dicts`` reducer hook;
            defaults to :func:`default_prepare_state`.
        checkpointer: Shared LangGraph checkpointer passed to factories that
            accept a ``checkpointer`` kwarg. ``"memory"`` (default) builds one
            ``MemorySaver``; pass an instance, or ``None`` to disable.
        thread_manager: Override the in-memory thread registry (tests).
        message_store: Override the assistant-ui message store (tests).
    """
    from .registry import discover_agents

    default_agent: str | None = settings.default_agent
    single_mode = graph is not None or graph_factory is not None

    if checkpointer == "memory":
        checkpointer = _default_checkpointer()

    def call_factory(factory: Callable[..., Any]) -> Any:
        try:
            params = inspect.signature(factory).parameters
        except (TypeError, ValueError):
            return factory()
        if checkpointer is not None and "checkpointer" in params:
            return factory(checkpointer=checkpointer)
        return factory()

    if single_mode:
        if graph is not None:
            factories: dict[str, Callable[..., Any]] = {
                "default": lambda: graph
            }
        else:
            assert graph_factory is not None
            factories = {"default": graph_factory}
        default_agent = "default"
    elif agents is not None:
        factories = dict(agents)
        if not factories:
            raise ValueError("agents must contain at least one factory")
    else:
        parameters = inspect.signature(discover_agents).parameters
        factories = (
            discover_agents(model=settings.model)
            if "model" in parameters
            else discover_agents()
        )

    if default_agent not in factories:
        raise ValueError(
            f"default_agent {default_agent!r} is not registered; "
            f"available agents: {sorted(factories)}"
        )

    threads = thread_manager or ThreadManager()
    messages = message_store or ThreadMessageStore()

    built: dict[str, Any] = {}
    build_errors: dict[str, str] = {}

    def get_or_build(name: str) -> Any | None:
        if name in built:
            return built[name]
        factory = factories.get(name)
        if factory is None:
            return None
        try:
            instance = call_factory(factory)
        except Exception as exc:
            build_errors[name] = str(exc)
            logger.warning("agent factory %r failed: %s", name, exc)
            return None
        if instance is None:
            build_errors[name] = "factory returned None"
            return None
        built[name] = instance
        return instance

    # Eagerly build the single-agent override so startup (not first request)
    # surfaces factory errors; registry mode stays lazy per agent.
    eager_error: str | None = None
    if single_mode:
        try:
            assert factories["default"] is not None
            inst = call_factory(factories["default"])
            if inst is None:
                eager_error = "factory returned None"
            else:
                built["default"] = inst
        except Exception as exc:
            eager_error = str(exc)
            logger.warning("graph_factory failed: %s", exc)

    app = FastAPI()
    app.state.settings = settings
    app.state.capabilities = capability_provider
    app.add_middleware(
        CORSMiddleware,
        # The bundled UI is same-origin; permissive CORS supports split-port development.
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["x-thread-id", "Content-Disposition", "X-Suggested-Filename"],
    )

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/agents")
    async def list_agents():
        return capability_provider.agent_listing(list(factories), default_agent)

    # --- Threads (full-stack compatible) ---

    @app.get("/threads", response_model=list[ThreadMetadata])
    async def get_threads(user_id: str = "default_user", include_archived: bool = False):
        return list(reversed(threads.list_user_threads(user_id, include_archived)))

    @app.post("/threads", response_model=ThreadMetadata)
    async def create_thread(body: CreateThreadBody):
        existing = threads.get(body.localId)
        if existing:
            return existing
        return threads.create_thread(body.user_id, title=body.title, thread_id=body.localId)

    @app.get("/threads/{thread_id}", response_model=ThreadMetadata)
    async def fetch_thread(thread_id: str):
        thread = threads.get(thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
        return thread

    @app.patch("/threads/{thread_id}", response_model=ThreadMetadata)
    async def rename_thread(thread_id: str, body: RenameThreadBody):
        thread = threads.get(thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
        new_title = (body.title or "").strip()
        if not new_title:
            raise HTTPException(status_code=400, detail="title must not be empty")
        threads.update_title(thread_id, new_title)
        updated = threads.get(thread_id)
        if not updated:
            raise HTTPException(status_code=404, detail="Thread not found")
        return updated

    @app.post("/threads/{thread_id}/archive", response_model=ThreadMetadata)
    async def archive_thread(thread_id: str):
        thread = threads.get(thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
        threads.archive(thread_id)
        updated = threads.get(thread_id)
        if not updated:
            raise HTTPException(status_code=404, detail="Thread not found")
        return updated

    @app.post("/threads/{thread_id}/unarchive", response_model=ThreadMetadata)
    async def unarchive_thread(thread_id: str):
        thread = threads.get(thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
        threads.unarchive(thread_id)
        updated = threads.get(thread_id)
        if not updated:
            raise HTTPException(status_code=404, detail="Thread not found")
        return updated

    @app.delete("/threads/{thread_id}")
    async def delete_thread(thread_id: str):
        thread = threads.get(thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
        threads.delete(thread_id)
        messages.drop(thread_id)
        return {"ok": True}

    @app.get("/threads/{thread_id}/messages")
    async def get_thread_messages(thread_id: str):
        """Persisted assistant-ui messages, else checkpointer fallback."""
        persisted = messages.list(thread_id)
        if persisted:
            return {"messages": persisted}
        instance = get_or_build(default_agent)
        if instance is not None and hasattr(instance, "get_state"):
            try:
                import asyncio

                config = {"configurable": {"thread_id": thread_id}}
                state = await asyncio.to_thread(instance.get_state, config)
                if state and "messages" in (state.values or {}):
                    return {
                        "messages": [
                            m.model_dump() for m in state.values["messages"]
                        ]
                    }
            except Exception as exc:
                logger.debug("checkpointer fallback failed: %s", exc)
        return {"messages": []}

    @app.post("/threads/{thread_id}/messages")
    async def append_thread_message(thread_id: str, body: AppendMessageBody):
        messages.append(thread_id, body.message)
        return {"ok": True}

    async def run_assistant(request: ScopedChatRequest, agent_id: str):
        if agent_id not in factories:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "unknown_agent",
                    "message": f"Unknown agent {agent_id!r}.",
                    "hint": f"Available: {sorted(factories.keys())}",
                },
            )
        instance = get_or_build(agent_id)
        if instance is None:
            err = build_errors.get(agent_id) or eager_error
            if single_mode:
                raise HTTPException(
                    status_code=503,
                    detail={
                        "error": "agent_not_ready",
                        "message": "No graph was provided or the factory failed.",
                        "hint": err or "Pass graph= or graph_factory= to create_app().",
                    },
                )
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "agent_not_ready",
                    "message": f"Agent {agent_id!r} failed to build.",
                    "hint": err or "Check provider credentials / MODEL env.",
                },
            )

        user_id = request.user_id or "default_user"
        thread_id = resolve_thread_id(request, default=str(uuid.uuid4()))
        if not threads.get(thread_id):
            threads.create_thread(user_id, title="New Chat", thread_id=thread_id)
        config = {"configurable": {"thread_id": thread_id}}

        reducer = prepare_state or default_prepare_state

        async def run_callback(controller: RunController):
            if controller.state is None:
                controller.state = {"messages": []}
            if "tool_updates" not in controller.state:
                controller.state["tool_updates"] = []

            controller.state["messages"] = _sanitize_langchain_message_history(
                reducer(controller.state, request)
            )
            input_message = {"messages": list(controller.state["messages"])}
            async for namespace, event_type, chunk in instance.astream(
                input_message,
                config=config,
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
                append_langgraph_event(
                    controller.state, namespace, event_type, chunk
                )

        stream = create_run(run_callback, state=request.state)
        return DataStreamResponse(stream)

    @app.post("/assistant")
    async def chat_endpoint(request: ScopedChatRequest):
        return await run_assistant(request, default_agent)

    @app.post("/assistant/{agent_id}")
    async def chat_endpoint_for_agent(agent_id: str, request: ScopedChatRequest):
        return await run_assistant(request, agent_id)

    mount_static_ui(app, settings)

    return app


def create_app(*args, **kwargs) -> FastAPI:
    """Compatibility import for :func:`agent_chat_minimal.create_app`."""
    from .composition import create_app as compose_app

    return compose_app(*args, **kwargs)


def create_default_app() -> FastAPI:
    """Compatibility ASGI factory without import-time app construction."""
    from .composition import create_default_app as compose_default_app

    return compose_default_app()


def main(argv=None):
    """Compatibility CLI entry point."""
    from .composition import main as composition_main

    return composition_main(argv)
