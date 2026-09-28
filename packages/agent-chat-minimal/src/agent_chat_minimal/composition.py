"""Application composition and executable entry points."""

import argparse
import os
from collections.abc import Callable
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
    )


def create_default_app() -> FastAPI:
    """ASGI factory for ``uvicorn agent_chat_minimal:create_default_app --factory``."""
    return create_app(settings=Settings.from_env())


def main(argv=None):
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
    settings = replace(
        env,
        host=args.host,
        port=args.port,
        model=args.model or env.model,
        default_agent=args.agent or env.default_agent,
    )
    if args.model:
        # Built-in factories retain their released environment contract.
        os.environ["MODEL"] = args.model
    if args.check:
        from .registry import discover_agents

        factories = discover_agents()
        factory = factories.get(settings.default_agent)
        if factory is None:
            raise SystemExit(f"unknown agent {settings.default_agent!r}")
        factory()
        print(f"agent {settings.default_agent!r} built OK")
        return
    uvicorn.run(
        create_app(settings=settings), host=settings.host, port=settings.port
    )
