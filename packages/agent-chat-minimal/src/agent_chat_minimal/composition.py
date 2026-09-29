"""Application composition and executable entry points."""

import argparse
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI

from .capabilities import CapabilityProvider
from .config import Settings
from .server import ChatGraph, _build_app
from .services import SessionService, TranscriptService
from .threads import ThreadManager, ThreadMessageStore
from .transport import ChatRequest


def create_app(
    graph: ChatGraph | None = None,
    graph_factory: Callable[..., ChatGraph | None] | None = None,
    agents: dict[str, Callable[..., ChatGraph | None]] | None = None,
    default_agent: str | None = None,
    web_dir: Path | None = None,
    web_full_dir: Path | None = None,
    prepare_state: Callable[[dict, ChatRequest], list] | None = None,
    checkpointer: Any | None = "memory",
    thread_manager: ThreadManager | None = None,
    message_store: ThreadMessageStore | None = None,
    settings: Settings | None = None,
    capability_provider: CapabilityProvider | None = None,
    principal_resolver: Any | None = None,
    repositories: Any | None = None,
    session_service: SessionService | None = None,
    transcript_service: TranscriptService | None = None,
    checkpoint_deleter: Any | None = None,
    lifespan: Any | None = None,
) -> FastAPI:
    """Compose an application from validated settings and injectable services.

    Existing keyword arguments remain supported and override the corresponding
    value from ``settings``. With no settings object, environment-backed settings
    retain the historical ``create_app()`` behavior.
    """
    resolved = settings or Settings.from_env()
    overrides = {}
    if default_agent is not None:
        overrides["default_agent"] = default_agent
    if web_dir is not None:
        overrides["web_dir"] = str(web_dir)
    if web_full_dir is not None:
        overrides["web_full_dir"] = str(web_full_dir)
    if agents is not None and settings is None and default_agent is None and agents:
        # Preserve the released custom-registry default while allowing an
        # explicit Settings object to be authoritative.
        overrides["default_agent"] = next(iter(agents))
    if overrides:
        resolved = replace(resolved, **overrides)

    capabilities = capability_provider or CapabilityProvider.for_preset(
        resolved.ui_preset
    )
    return _build_app(
        resolved,
        capabilities,
        graph=graph,
        graph_factory=graph_factory,
        agents=agents,
        prepare_state=prepare_state,
        checkpointer=checkpointer,
        thread_manager=thread_manager,
        message_store=message_store,
        principal_resolver=principal_resolver,
        repositories=repositories,
        session_service=session_service,
        transcript_service=transcript_service,
        checkpoint_deleter=checkpoint_deleter,
        lifespan=lifespan,
    )


class _DeferredCheckpointer:
    """Expose the lifespan-owned saver to lazily constructed graph factories."""

    def __init__(self) -> None:
        self._adapter: Any | None = None

    def set_adapter(self, adapter: Any) -> None:
        self._adapter = adapter

    def clear_adapter(self) -> None:
        self._adapter = None

    @property
    def checkpointer(self) -> Any:
        if self._adapter is None:
            raise RuntimeError("checkpoint store is not available before application startup")
        return self._adapter.checkpointer

    async def delete_session(self, session_id: str) -> None:
        await self.checkpointer.adelete_thread(session_id)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.checkpointer, name)


def _durable_dependencies(settings: Settings) -> tuple[Any, Any, Any]:
    """Construct lazy durable dependencies without opening loop-bound I/O."""
    try:
        from .adapters.langgraph_sqlite import LangGraphSQLiteCheckpoints
        from .adapters.sqlite import SQLiteRepositories, create_sqlite_engine, upgrade_database
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Durable persistence requires the persistence extra. Install with "
            'pip install "agent-chat-fastapi-langgraph-assistant-ui[persistence]".'
        ) from exc

    repositories = SQLiteRepositories(create_sqlite_engine(settings.resolved_database_url()))
    deferred_checkpointer = _DeferredCheckpointer()

    @asynccontextmanager
    async def durable_lifespan(_: FastAPI):
        checkpoints = None
        try:
            if settings.auto_migrate:
                await upgrade_database(repositories.engine)
            checkpoints = await LangGraphSQLiteCheckpoints.open(
                settings.resolved_checkpoint_database_url()
            )
            deferred_checkpointer.set_adapter(checkpoints)
            yield
        finally:
            deferred_checkpointer.clear_adapter()
            if checkpoints is not None:
                await checkpoints.dispose()
            await repositories.dispose()

    return repositories, deferred_checkpointer, durable_lifespan


def create_configured_app(
    settings: Settings,
    agents: dict[str, Callable[..., ChatGraph | None]] | None = None,
    default_agent: str | None = None,
    graph: ChatGraph | None = None,
    graph_factory: Callable[..., ChatGraph | None] | None = None,
    capability_provider: CapabilityProvider | None = None,
) -> FastAPI:
    """Compose the supported app, owning durable resources when enabled.

    Accepts the same explicit Python agent mappings/factories as
    :func:`create_app`, so generated projects and embedders share one
    route/service/transport implementation instead of copying private
    persistence or lifespan code. The entry points call this synchronous
    factory before their event loop starts. Explicit ``create_app(...)``
    remains injection-first for tests and embedding applications.
    """
    if not settings.persistence_enabled:
        return create_app(
            settings=settings,
            agents=agents,
            default_agent=default_agent,
            graph=graph,
            graph_factory=graph_factory,
            capability_provider=capability_provider,
        )

    repositories, checkpoints, lifespan = _durable_dependencies(settings)
    app = create_app(
        settings=settings,
        agents=agents,
        default_agent=default_agent,
        graph=graph,
        graph_factory=graph_factory,
        capability_provider=capability_provider,
        repositories=repositories,
        checkpointer=checkpoints,
        checkpoint_deleter=checkpoints,
        lifespan=lifespan,
    )
    app.state.repositories = repositories
    app.state.checkpoints = checkpoints
    return app


def create_default_app() -> FastAPI:
    """ASGI factory for ``uvicorn agent_chat_minimal:create_default_app --factory``."""
    return create_configured_app(Settings.load())


def main(argv=None):
    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument("--config", help="Path to versioned agent-chat YAML")
    config_args, _ = config_parser.parse_known_args(argv)
    env = Settings.from_yaml(config_args.config) if config_args.config else Settings.load()
    parser = argparse.ArgumentParser(description="Serve the minimal chat application")
    parser.add_argument("--config", default=config_args.config, help=argparse.SUPPRESS)
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
    settings = replace(
        env,
        host=args.host,
        port=args.port,
        model=args.model or env.model,
        default_agent=args.agent or env.default_agent,
    )
    if args.check:
        from .registry import discover_agents

        factories = discover_agents(model=settings.model)
        factory = factories.get(settings.default_agent)
        if factory is None:
            raise SystemExit(f"unknown agent {settings.default_agent!r}")
        factory()
        print(f"agent {settings.default_agent!r} built OK")
        return
    uvicorn.run(
        create_configured_app(settings), host=settings.host, port=settings.port
    )
