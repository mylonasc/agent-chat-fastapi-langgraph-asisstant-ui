"""Portable FastAPI + LangGraph chat with a bundled Assistant UI.

Quick links (also shipped as markdown in ``agent_chat_minimal/docs/``):

- ``docs.list()`` / ``docs.get(name)`` — guides: quickstart, agents,
  providers, configuration, threads.
- ``create_app(...)`` — serve one graph, a factory, or an agent registry.
- ``Settings.from_env()`` — all env vars in one place.
- ``GET /docs`` on a running server — interactive Swagger UI.

Example:
    >>> from agent_chat_minimal import create_app
    >>> app = create_app(agents={"weather": ...})  # doctest: +SKIP
"""

from . import docs
from .capabilities import CapabilityProvider
from .composition import create_app, create_default_app, main
from .config import ENV_DOC, Settings
from .domain import (
    Feedback,
    FeedbackRating,
    MessageRole,
    Principal,
    Session,
    SessionStatus,
    StoredMessage,
)
from .identity import DefaultPrincipalResolver
from .ports import PrincipalResolver
from .registry import AGENT_REGISTRY, discover_agents
from .services import SessionService, TranscriptService
from .server import (
    DEFAULT_WEB_DIR,
    DEFAULT_WEB_FULL_DIR,
    ChatGraph,
    ScopedChatRequest,
    default_prepare_state,
    resolve_thread_id,
)
from .threads import ThreadManager, ThreadMessageStore, ThreadMetadata

__version__ = "0.3.5"

__all__ = [
    "__version__",
    "AGENT_REGISTRY",
    "ENV_DOC",
    "ChatGraph",
    "CapabilityProvider",
    "DEFAULT_WEB_DIR",
    "DefaultPrincipalResolver",
    "DEFAULT_WEB_FULL_DIR",
    "Feedback",
    "FeedbackRating",
    "MessageRole",
    "Principal",
    "PrincipalResolver",
    "ScopedChatRequest",
    "Session",
    "SessionService",
    "SessionStatus",
    "Settings",
    "StoredMessage",
    "TranscriptService",
    "ThreadManager",
    "ThreadMessageStore",
    "ThreadMetadata",
    "create_app",
    "create_default_app",
    "default_prepare_state",
    "discover_agents",
    "docs",
    "main",
    "resolve_thread_id",
]
