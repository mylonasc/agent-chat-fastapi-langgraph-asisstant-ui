import argparse
import logging
import os
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

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


logger = logging.getLogger(__name__)
DEFAULT_WEB_DIR = Path(__file__).parent / "web"


@runtime_checkable
class ChatGraph(Protocol):
    """Minimal contract for a graph servable by ``create_app``.

    The graph must accept ``{"messages": [...]}`` as input and support
    ``astream(input, stream_mode=["messages"], subgraphs=True)`` yielding
    ``(namespace, event_type, chunk)`` triples consumable by
    ``assistant_stream_ce.modules.langgraph.append_langgraph_event``.
    """

    def astream(self, *args: Any, **kwargs: Any) -> Any: ...


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        reserved_paths = ("assistant", "agents", "health", "docs", "openapi.json")
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


def _legacy_openai_503() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={
            "error": "OPENAI_API_KEY not configured",
            "message": "Please set the OPENAI_API_KEY environment variable to use the chat functionality.",
            "instructions": "Add OPENAI_API_KEY=your-key to your .env file and restart the server.",
        },
    )


def default_prepare_state(state: dict, request: ChatRequest) -> list:
    """Fold ``add-message`` commands into message dicts (the default reducer)."""
    messages = list(state.get("messages", []))
    for command in request.commands:
        if command.type == "add-message":
            text = " ".join(
                part.text for part in command.message.parts if part.type == "text"
            )
            if text:
                message_id = getattr(command.message, "id", str(uuid.uuid4()))
                message = HumanMessage(content=text, id=message_id)
                messages.append(message.model_dump())
    return messages


def resolve_thread_id(request: ChatRequest) -> str:
    """Derive a persistence thread id from the request (default: "default").

    Looks in ``request.state["thread_id"]`` then ``request.runConfig`` so
    graphs compiled with a LangGraph checkpointer get stable per-conversation
    threads without any client change.
    """
    for source in (request.state, request.runConfig):
        if isinstance(source, dict) and source.get("thread_id"):
            return str(source["thread_id"])
    return "default"


def create_app(
    graph: ChatGraph | None = None,
    graph_factory: Callable[[], ChatGraph | None] | None = None,
    agents: dict[str, Callable[[], ChatGraph | None]] | None = None,
    default_agent: str = "weather",
    web_dir: Path | None = None,
    prepare_state: Callable[[dict, ChatRequest], list] | None = None,
) -> FastAPI:
    """Create the FastAPI app serving LangGraph agent(s).

    Single-agent override (takes precedence):
        ``create_app(graph=my_graph)`` or
        ``create_app(graph_factory=make_my_agent)`` serves one agent as both
        ``POST /assistant`` and ``GET /agents == ["default"]``.

    Multi-agent registry (default):
        ``create_app()`` serves the built-in registry (``weather`` +
        ``calculator`` plus ``agent_chat.agents`` entry points) at
        ``POST /assistant/{agent_id}``, with ``POST /assistant`` aliasing
        ``default_agent``. Pass ``agents={...}`` to override.

    Args:
        graph: Already-compiled graph (single-agent mode).
        graph_factory: Zero-arg factory (single-agent mode, deferred build).
        agents: Mapping of name -> factory (multi-agent mode).
        default_agent: Name aliased by ``POST /assistant``.
        web_dir: Override for the bundled static UI directory.
        prepare_state: ``(state, request) -> message dicts`` reducer hook;
            defaults to :func:`default_prepare_state`.
    """
    from .registry import discover_agents

    openai_api_key = os.getenv("OPENAI_API_KEY")
    single_mode = graph is not None or graph_factory is not None

    if single_mode:
        if graph is not None:
            factories: dict[str, Callable[[], Any]] = {
                "default": lambda: graph
            }
        else:
            assert graph_factory is not None
            factories = {"default": graph_factory}
        default_agent = "default"
        legacy_default = False
    elif agents is not None:
        factories = dict(agents)
        legacy_default = False
    else:
        factories = discover_agents()
        legacy_default = True
        if not openai_api_key:
            logger.warning(
                "OPENAI_API_KEY is not set; the /assistant endpoint will return 503."
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
            instance = factory()
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
            inst = factories["default"]()
            if inst is None:
                eager_error = "factory returned None"
            else:
                built["default"] = inst
        except Exception as exc:
            eager_error = str(exc)
            logger.warning("graph_factory failed: %s", exc)

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

    @app.get("/agents")
    async def list_agents():
        return {"agents": sorted(factories.keys()), "default": default_agent}

    async def run_assistant(request: ChatRequest, agent_id: str):
        if agent_id not in factories:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "unknown_agent",
                    "message": f"Unknown agent {agent_id!r}.",
                    "hint": f"Available: {sorted(factories.keys())}",
                },
            )
        if (
            legacy_default
            and agent_id == default_agent
            and agent_id == "weather"
            and not openai_api_key
        ):
            raise _legacy_openai_503()

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

        reducer = prepare_state or default_prepare_state

        async def run_callback(controller: RunController):
            if controller.state is None:
                controller.state = {"messages": []}

            controller.state["messages"] = reducer(controller.state, request)
            thread_id = resolve_thread_id(request)
            input_message = {"messages": list(controller.state["messages"])}
            async for namespace, event_type, chunk in instance.astream(
                input_message,
                config={"configurable": {"thread_id": thread_id}},
                stream_mode=["messages"],
                subgraphs=True,
            ):
                append_langgraph_event(
                    controller.state, namespace, event_type, chunk
                )

        stream = create_run(run_callback, state=request.state)
        return DataStreamResponse(stream)

    @app.post("/assistant")
    async def chat_endpoint(request: ChatRequest):
        return await run_assistant(request, default_agent)

    @app.post("/assistant/{agent_id}")
    async def chat_endpoint_for_agent(agent_id: str, request: ChatRequest):
        return await run_assistant(request, agent_id)

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
    from .config import Settings

    env = Settings.from_env()
    parser = argparse.ArgumentParser(description="Serve the minimal chat application")
    parser.add_argument("--host", default=env.host)
    parser.add_argument("--port", type=int, default=env.port)
    parser.add_argument(
        "--model",
        default=None,
        help="Model spec, e.g. openai:gpt-4o-mini (sets MODEL env)",
    )
    parser.add_argument(
        "--agent",
        default=None,
        help="Default agent id for POST /assistant (sets DEFAULT_AGENT env)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Build the default agent graph and exit (smoke check)",
    )
    args = parser.parse_args(argv)
    if args.model:
        os.environ["MODEL"] = args.model
    default_agent = args.agent or os.getenv("DEFAULT_AGENT", env.default_agent)
    if args.check:
        from .registry import discover_agents

        factories = discover_agents()
        factory = factories.get(default_agent)
        if factory is None:
            raise SystemExit(f"unknown agent {default_agent!r}")
        factory()
        print(f"agent {default_agent!r} built OK")
        return
    uvicorn.run(
        create_app(default_agent=default_agent), host=args.host, port=args.port
    )
