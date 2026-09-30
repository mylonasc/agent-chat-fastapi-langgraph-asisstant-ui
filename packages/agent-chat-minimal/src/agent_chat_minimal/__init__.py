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
from .composition import create_app, create_configured_app, create_default_app, main
from .config import CONFIG_VERSION, ENV_DOC, ProposedQuestion, Settings
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
from .models import ModelConfig, resolve_model
from .ports import PrincipalResolver
from .registry import AGENT_REGISTRY, discover_agents
from .runtime_config import (
    DEFAULT_RUNTIME_CONFIG,
    RUNTIME_CONFIG_VERSION,
    RuntimeConfig,
    build_runtime_config,
    parse_runtime_config,
)
from .services import SessionService, TranscriptService
from .demo_agent.agent_factory import ToolsNotSupportedError
from .starter import StarterError, generate_starter, plan_starter, render_starter_files
from .setup import (
    SETUP_CONTRACT_VERSION,
    TEMPLATE_VERSION,
    Diagnostic,
    GenerationPlan,
    ProviderDescriptor,
    SetupReport,
    StarterGenerator,
    StarterOptions,
    describe_setup,
    diagnose_options,
    exit_status_for,
    get_config_schema,
    get_provider_descriptor,
    list_providers,
    normalize_package_name,
    redacted_options,
    register_provider_descriptor,
    validate_options,
)
from .server import (
    DEFAULT_WEB_DIR,
    DEFAULT_WEB_FULL_DIR,
    ChatGraph,
    ScopedChatRequest,
    default_prepare_state,
    resolve_thread_id,
)
from .static_ui import bundled_ui_dir, is_ui_bundle, resolve_ui_dir
from .threads import ThreadManager, ThreadMessageStore, ThreadMetadata

__version__ = "0.6.1"

__all__ = [
    "__version__",
    "AGENT_REGISTRY",
    "ENV_DOC",
    "ChatGraph",
    "CapabilityProvider",
    "CONFIG_VERSION",
    "DEFAULT_WEB_DIR",
    "DefaultPrincipalResolver",
    "DEFAULT_WEB_FULL_DIR",
    "Feedback",
    "FeedbackRating",
    "MessageRole",
    "ModelConfig",
    "DEFAULT_RUNTIME_CONFIG",
    "Diagnostic",
    "GenerationPlan",
    "Principal",
    "PrincipalResolver",
    "ProposedQuestion",
    "ProviderDescriptor",
    "RUNTIME_CONFIG_VERSION",
    "RuntimeConfig",
    "ScopedChatRequest",
    "build_runtime_config",
    "bundled_ui_dir",
    "create_configured_app",
    "is_ui_bundle",
    "resolve_ui_dir",
    "Session",
    "SETUP_CONTRACT_VERSION",
    "SessionService",
    "SessionStatus",
    "Settings",
    "SetupReport",
    "StarterError",
    "StarterGenerator",
    "StarterOptions",
    "TEMPLATE_VERSION",
    "StoredMessage",
    "TranscriptService",
    "parse_runtime_config",
    "ThreadManager",
    "ThreadMessageStore",
    "ToolsNotSupportedError",
    "ThreadMetadata",
    "create_app",
    "create_default_app",
    "default_prepare_state",
    "describe_setup",
    "diagnose_options",
    "discover_agents",
    "docs",
    "exit_status_for",
    "generate_starter",
    "get_config_schema",
    "get_provider_descriptor",
    "list_providers",
    "main",
    "normalize_package_name",
    "plan_starter",
    "redacted_options",
    "register_provider_descriptor",
    "render_starter_files",
    "resolve_thread_id",
    "resolve_model",
    "validate_options",
]
