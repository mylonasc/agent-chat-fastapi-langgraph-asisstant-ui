import asyncio
import inspect
import logging
import uuid
import warnings
from collections.abc import Callable
from datetime import timezone
from typing import Annotated, Any, Optional, Protocol, runtime_checkable

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from .adapters.memory import InMemoryRepositories
from .capabilities import CapabilityProvider
from .config import Settings
from .domain import Feedback, FeedbackRating, MessageRole, Principal, Session, SessionStatus
from .identity import DefaultPrincipalResolver
from .services import (
    ConflictError,
    ForbiddenError,
    FeedbackService,
    NotFoundError,
    SessionService,
    TranscriptService,
)
from .static_ui import DEFAULT_WEB_DIR, DEFAULT_WEB_FULL_DIR, mount_static_ui
from .threads import ThreadManager, ThreadMessageStore, ThreadMetadata
from .transport import (
    ChatRequest,
    RunController,
    append_graph_event,
    create_response,
    create_run,
)


logger = logging.getLogger(__name__)


@runtime_checkable
class ChatGraph(Protocol):
    """Minimal contract for a graph servable by ``create_app``.

    The graph must accept ``{"messages": [...]}`` as input and support
    ``astream(input, config, stream_mode=[...], subgraphs=True)`` yielding
    ``(namespace, event_type, chunk)`` triples consumable by
    the package transport adapter.
    """

    def astream(self, *args: Any, **kwargs: Any) -> Any: ...


class ScopedChatRequest(ChatRequest):
    """Chat request with full-stack thread scoping (same shape as full backend)."""

    thread_id: Optional[str] = None
    user_id: Optional[str] = "default_user"


class CreateThreadBody(BaseModel):
    localId: str
    # Legacy client-supplied owner claim. Accepted for shape compatibility but
    # never authorizes: when present it must equal the resolved principal.
    user_id: Optional[str] = None
    title: str = "New Chat"


class AppendMessageBody(BaseModel):
    message: dict[str, Any]


class RenameThreadBody(BaseModel):
    title: str


class FeedbackBody(BaseModel):
    rating: FeedbackRating
    comment: str | None = None
    metadata: dict[str, Any] | None = None


def _feedback_payload(feedback: Feedback) -> dict[str, Any]:
    return {
        "id": feedback.id,
        "thread_id": feedback.session_id,
        "message_id": feedback.message_id,
        "rating": feedback.rating.value,
        "comment": feedback.comment,
        "metadata": feedback.metadata,
        "created_at": feedback.created_at.isoformat(),
        "updated_at": feedback.updated_at.isoformat(),
    }


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


def _session_to_thread_metadata(session: Session) -> ThreadMetadata:
    """Map the canonical session onto the compatibility thread shape."""
    created = session.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return ThreadMetadata(
        id=session.id,
        user_id=session.owner_subject,
        title=session.title,
        created_at=created,
        is_archived=session.status is SessionStatus.ARCHIVED,
        is_public=False,
    )


def _infer_message_role(message: dict[str, Any]) -> MessageRole:
    """Infer a transcript role from a verbatim UI message object."""
    role = str(message.get("role") or "").strip().lower()
    try:
        return MessageRole(role)
    except ValueError:
        return MessageRole.USER


def _service_error_to_http(exc: Exception) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ForbiddenError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    raise exc


def _seed_repositories_from_legacy(
    repositories: InMemoryRepositories,
    thread_manager: ThreadManager | None,
    message_store: ThreadMessageStore | None,
) -> None:
    """Best-effort migration of deprecated process-local stores into services."""

    async def seed() -> None:
        if thread_manager is not None:
            snapshot = dict(getattr(thread_manager, "_threads", {}))
            for thread in snapshot.values():
                created = thread.created_at
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                try:
                    await repositories.sessions.add(
                        Session(
                            id=thread.id,
                            owner_subject=thread.user_id,
                            title=thread.title,
                            created_at=created,
                            updated_at=created,
                            status=SessionStatus.ARCHIVED
                            if thread.is_archived
                            else SessionStatus.ACTIVE,
                            archived_at=created if thread.is_archived else None,
                            metadata={"migrated_from": "ThreadManager"},
                        )
                    )
                except ValueError:
                    continue
        if message_store is not None:
            snapshot = dict(getattr(message_store, "_messages", {}))
            for thread_id, items in snapshot.items():
                if await repositories.sessions.get(thread_id) is None:
                    continue
                existing = await repositories.transcripts.list_by_session(thread_id)
                sequence = existing[-1].sequence if existing else 0
                for item in items:
                    from .domain import StoredMessage, utc_now

                    sequence += 1
                    try:
                        await repositories.transcripts.add(
                            StoredMessage(
                                id=str(item.get("id"))
                                if item.get("id") is not None
                                else f"legacy-{sequence}",
                                session_id=thread_id,
                                sequence=sequence,
                                role=_infer_message_role(item),
                                payload=item,
                                created_at=utc_now(),
                                metadata={"migrated_from": "ThreadMessageStore"},
                            )
                        )
                    except ValueError:
                        sequence -= 1
                        continue

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(seed())
    else:
        warnings.warn(
            "legacy thread_manager/message_store seeding skipped: "
            "a running event loop owns _build_app; pass repositories instead",
            stacklevel=2,
        )


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
    principal_resolver: Any | None = None,
    repositories: Any | None = None,
    session_service: SessionService | None = None,
    transcript_service: TranscriptService | None = None,
    checkpoint_deleter: Any | None = None,
    lifespan: Any | None = None,
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
        thread_manager: Deprecated legacy thread registry. When provided its
            contents are best-effort migrated into the session service;
            prefer ``repositories`` or ``session_service``.
        message_store: Deprecated verbatim message store. When provided its
            contents are best-effort migrated into the transcript service;
            prefer ``repositories`` or ``transcript_service``.
        principal_resolver: Maps a request to a trusted
            :class:`~agent_chat_minimal.domain.Principal`. Defaults to
            :class:`~agent_chat_minimal.identity.DefaultPrincipalResolver`
            (``x-agent-chat-subject`` header, ``default_user`` fallback).
        repositories: Bundle exposing ``sessions``/``transcripts``/``feedback``
            repositories (in-memory or SQLite). Defaults to fresh
            :class:`~agent_chat_minimal.adapters.memory.InMemoryRepositories`.
        session_service: Override the session application service (tests).
        transcript_service: Override the transcript application service (tests).
        checkpoint_deleter: Separate-lifecycle checkpoint port wired into the
            session service so deletion removes graph state (PUIR-06 adapter).
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
            # Durable composition defers opening SQLite until FastAPI lifespan.
            # Resolve its proxy only when the lazy registry factory is built,
            # so LangGraph receives the actual BaseCheckpointSaver.
            factory_checkpointer = getattr(checkpointer, "checkpointer", checkpointer)
            return factory(checkpointer=factory_checkpointer)
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

    resolver = principal_resolver or DefaultPrincipalResolver()
    owned_repositories: InMemoryRepositories | Any | None = repositories
    if session_service is None or transcript_service is None:
        if owned_repositories is None:
            owned_repositories = InMemoryRepositories()
            if thread_manager is not None or message_store is not None:
                warnings.warn(
                    "thread_manager/message_store are deprecated; "
                    "pass repositories or session_service instead",
                    DeprecationWarning,
                    stacklevel=2,
                )
                if isinstance(owned_repositories, InMemoryRepositories):
                    _seed_repositories_from_legacy(
                        owned_repositories, thread_manager, message_store
                    )
        base_sessions = session_service or SessionService(
            owned_repositories.sessions,
            owned_repositories.transcripts,
            owned_repositories.feedback,
            checkpoint_deleter,
        )
        base_transcripts = transcript_service or TranscriptService(
            owned_repositories.sessions, owned_repositories.transcripts
        )
    else:
        base_sessions = session_service
        base_transcripts = transcript_service
    sessions = base_sessions
    transcripts = base_transcripts
    feedback = FeedbackService(
        owned_repositories.sessions,
        owned_repositories.transcripts,
        owned_repositories.feedback,
    )

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

    app = FastAPI(lifespan=lifespan)
    app.state.settings = settings
    app.state.capabilities = capability_provider
    app.state.session_service = sessions
    app.state.transcript_service = transcripts
    app.state.principal_resolver = resolver

    async def _resolve_principal(request: Request) -> Principal:
        return await resolver.resolve(request)

    PrincipalDep = Annotated[Principal, Depends(_resolve_principal)]
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

    # --- Threads (full-stack compatible, service-backed) ---
    #
    # Ownership always comes from the resolved principal. The legacy
    # ``user_id`` query/body fields are accepted for shape compatibility but
    # never authorize: a value that disagrees with the principal is rejected
    # with 403. ``POST /assistant`` ignores ``user_id`` in the body and owns
    # auto-created sessions by the principal.

    @app.get("/threads", response_model=list[ThreadMetadata])
    async def get_threads(
        principal: PrincipalDep,
        user_id: str | None = None,
        include_archived: bool = False,
    ):
        """List the principal's sessions (legacy ``user_id`` must match)."""
        if user_id is not None and user_id != principal.subject:
            raise HTTPException(
                status_code=403,
                detail=f"principal cannot list sessions for {user_id!r}",
            )
        try:
            owned = await sessions.list(
                principal, include_archived=include_archived
            )
        except (NotFoundError, ForbiddenError, ConflictError) as exc:
            raise _service_error_to_http(exc) from exc
        return [_session_to_thread_metadata(item) for item in reversed(owned)]

    @app.post("/threads", response_model=ThreadMetadata)
    async def create_thread(body: CreateThreadBody, principal: PrincipalDep):
        """Idempotently register a session (legacy ``user_id`` must match)."""
        if body.user_id is not None and body.user_id != principal.subject:
            raise HTTPException(
                status_code=403,
                detail=f"principal cannot create sessions for {body.user_id!r}",
            )
        try:
            created = await sessions.create(
                principal, title=body.title, session_id=body.localId
            )
        except ConflictError:
            try:
                created = await sessions.get(principal, body.localId)
            except (NotFoundError, ForbiddenError, ConflictError) as exc:
                raise _service_error_to_http(exc) from exc
        except (NotFoundError, ForbiddenError) as exc:
            raise _service_error_to_http(exc) from exc
        return _session_to_thread_metadata(created)

    @app.get("/threads/{thread_id}", response_model=ThreadMetadata)
    async def fetch_thread(thread_id: str, principal: PrincipalDep):
        try:
            found = await sessions.get(principal, thread_id)
        except (NotFoundError, ForbiddenError, ConflictError) as exc:
            raise _service_error_to_http(exc) from exc
        return _session_to_thread_metadata(found)

    @app.patch("/threads/{thread_id}", response_model=ThreadMetadata)
    async def rename_thread(
        thread_id: str, body: RenameThreadBody, principal: PrincipalDep
    ):
        new_title = (body.title or "").strip()
        if not new_title:
            raise HTTPException(status_code=400, detail="title must not be empty")
        try:
            renamed = await sessions.rename(principal, thread_id, new_title)
        except (NotFoundError, ForbiddenError, ConflictError) as exc:
            raise _service_error_to_http(exc) from exc
        return _session_to_thread_metadata(renamed)

    @app.post("/threads/{thread_id}/archive", response_model=ThreadMetadata)
    async def archive_thread(thread_id: str, principal: PrincipalDep):
        try:
            archived = await sessions.set_archived(principal, thread_id, True)
        except (NotFoundError, ForbiddenError, ConflictError) as exc:
            raise _service_error_to_http(exc) from exc
        return _session_to_thread_metadata(archived)

    @app.post("/threads/{thread_id}/unarchive", response_model=ThreadMetadata)
    async def unarchive_thread(thread_id: str, principal: PrincipalDep):
        try:
            active = await sessions.set_archived(principal, thread_id, False)
        except (NotFoundError, ForbiddenError, ConflictError) as exc:
            raise _service_error_to_http(exc) from exc
        return _session_to_thread_metadata(active)

    @app.delete("/threads/{thread_id}")
    async def delete_thread(thread_id: str, principal: PrincipalDep):
        """Delete a session, its transcript/feedback, and its checkpoints."""
        try:
            await sessions.delete(principal, thread_id)
        except (NotFoundError, ForbiddenError, ConflictError) as exc:
            raise _service_error_to_http(exc) from exc
        return {"ok": True}

    async def _checkpointer_fallback_messages(thread_id: str) -> list | None:
        """Legacy hydration from graph state when no transcript is stored."""
        instance = get_or_build(default_agent)
        if instance is not None and hasattr(instance, "get_state"):
            try:
                config = {"configurable": {"thread_id": thread_id}}
                state = await asyncio.to_thread(instance.get_state, config)
                if state and "messages" in (state.values or {}):
                    return [m.model_dump() for m in state.values["messages"]]
            except Exception as exc:
                logger.debug("checkpointer fallback failed: %s", exc)
        return None

    @app.get("/threads/{thread_id}/messages")
    async def get_thread_messages(thread_id: str, principal: PrincipalDep):
        """Owned transcript payloads, else legacy checkpointer hydration."""
        try:
            stored = await transcripts.list(principal, thread_id)
        except ForbiddenError as exc:
            raise _service_error_to_http(exc) from exc
        except NotFoundError:
            stored = None
        except ConflictError as exc:
            raise _service_error_to_http(exc) from exc
        if stored:
            return {"messages": [item.payload for item in stored]}
        fallback = await _checkpointer_fallback_messages(thread_id)
        return {"messages": fallback or []}

    @app.post("/threads/{thread_id}/messages")
    async def append_thread_message(
        thread_id: str, body: AppendMessageBody, principal: PrincipalDep
    ):
        """Append a verbatim UI message (unknown/archived sessions rejected)."""
        from .domain import new_id

        message = body.message if isinstance(body.message, dict) else {}
        try:
            await transcripts.append(
                principal,
                thread_id,
                role=_infer_message_role(message),
                payload=body.message,
                message_id=str(message.get("id"))
                if message.get("id") is not None
                else new_id(),
            )
        except (NotFoundError, ForbiddenError, ConflictError) as exc:
            raise _service_error_to_http(exc) from exc
        return {"ok": True}

    @app.get("/threads/{thread_id}/messages/{message_id}/feedback")
    async def get_message_feedback(
        thread_id: str, message_id: str, principal: PrincipalDep
    ):
        try:
            item = await feedback.get(principal, thread_id, message_id)
        except (NotFoundError, ForbiddenError, ConflictError) as exc:
            raise _service_error_to_http(exc) from exc
        if item is None:
            raise HTTPException(status_code=404, detail=f"feedback for {message_id!r} was not found")
        return _feedback_payload(item)

    @app.put("/threads/{thread_id}/messages/{message_id}/feedback")
    async def upsert_message_feedback(
        thread_id: str,
        message_id: str,
        body: FeedbackBody,
        principal: PrincipalDep,
    ):
        try:
            item = await feedback.upsert(
                principal,
                thread_id,
                message_id,
                rating=body.rating,
                comment=body.comment,
                metadata=body.metadata,
            )
        except (NotFoundError, ForbiddenError, ConflictError) as exc:
            raise _service_error_to_http(exc) from exc
        logger.info(
            "feedback upserted thread_id=%s message_id=%s rating=%s",
            thread_id,
            message_id,
            item.rating.value,
        )
        return _feedback_payload(item)

    @app.delete("/threads/{thread_id}/messages/{message_id}/feedback")
    async def delete_message_feedback(
        thread_id: str, message_id: str, principal: PrincipalDep
    ):
        try:
            deleted = await feedback.delete(principal, thread_id, message_id)
        except (NotFoundError, ForbiddenError, ConflictError) as exc:
            raise _service_error_to_http(exc) from exc
        if not deleted:
            raise HTTPException(status_code=404, detail=f"feedback for {message_id!r} was not found")
        logger.info("feedback deleted thread_id=%s message_id=%s", thread_id, message_id)
        return {"ok": True}

    async def run_assistant(
        request: ScopedChatRequest, agent_id: str, principal: Principal
    ):
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

        # Ownership is server-derived: the body's legacy ``user_id`` is
        # accepted for shape compatibility but never authorizes.
        thread_id = resolve_thread_id(request, default=str(uuid.uuid4()))
        try:
            await sessions.create(principal, title="New Chat", session_id=thread_id)
        except ConflictError:
            try:
                await sessions.get(principal, thread_id)
            except (NotFoundError, ForbiddenError, ConflictError) as exc:
                raise _service_error_to_http(exc) from exc
        except (NotFoundError, ForbiddenError) as exc:
            raise _service_error_to_http(exc) from exc
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
                append_graph_event(controller.state, namespace, event_type, chunk)

        stream = create_run(run_callback, state=request.state)
        return create_response(stream)

    @app.api_route(
        "/tools/{subpath:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        include_in_schema=False,
    )
    async def unsupported_tool_capability(subpath: str):
        """Explicit refusal for optional tool capabilities.

        RAG/admin ``/tools/*`` routes live only in the separate full backend.
        The packaged application refuses them as JSON (never SPA HTML) so
        bundled-UI polling degrades gracefully; PUIR-13 owns real
        capability gating.
        """
        raise HTTPException(
            status_code=501,
            detail={
                "error": "capability_disabled",
                "message": (
                    f"Tool capability {subpath!r} is not served "
                    "by this application."
                ),
                "hint": (
                    "RAG/admin tool routes live in the full backend; "
                    "serve that backend or wait for PUIR-13 capability gating."
                ),
            },
        )

    @app.get("/api/config")
    async def runtime_config():
        """Serve the versioned runtime UI configuration (PUIR-08).

        Deployment-specific values are computed per request and marked
        ``no-store`` so wheels stay portable while deployments can change
        behavior without rebuilding the static UI.
        """
        from fastapi.responses import JSONResponse

        from .runtime_config import build_runtime_config

        snapshot = build_runtime_config(settings, capability_provider)
        return JSONResponse(content=snapshot.as_dict(), headers={"Cache-Control": "no-store"})

    @app.post("/assistant")
    async def chat_endpoint(request: ScopedChatRequest, principal: PrincipalDep):
        return await run_assistant(request, default_agent, principal)

    @app.post("/assistant/{agent_id}")
    async def chat_endpoint_for_agent(
        agent_id: str, request: ScopedChatRequest, principal: PrincipalDep
    ):
        return await run_assistant(request, agent_id, principal)

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
