"""Centralized settings for the portable chat server (#14).

One place for every env var / CLI flag. Stdlib only on purpose: the wheel
stays dependency-light (no ``pydantic-settings`` required).
"""

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

CONFIG_VERSION = 1

_CONFIG_FIELDS = frozenset(
    field
    for field in (
        "host", "port", "model", "default_agent", "web_dir", "web_full_dir",
        "ui_preset", "api_base", "identity_mode", "server_mode", "database_url",
        "database_path", "checkpoint_database_url", "checkpoint_database_path",
        "auto_migrate", "persistence_enabled", "ui", "app_title", "welcome_heading",
        "welcome_description", "composer_placeholder", "proposed_questions",
    )
)


@dataclass(frozen=True)
class ProposedQuestion:
    """A plain-text prompt that may be shown by a compatible UI."""

    id: str
    label: str
    prompt: str
    agents: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name, value in (("id", self.id), ("label", self.label), ("prompt", self.prompt)):
            if not value.strip():
                raise ValueError(f"question {name} must not be empty")
            if len(value) > 500:
                raise ValueError(f"question {name} must be at most 500 characters")


def _validate_api_base(value: str) -> None:
    """Same-origin (``""``) is the secure default; external bases are explicit."""
    if not value:
        return
    if value.endswith("/"):
        raise ValueError("api_base must not end with '/'")
    if "://" not in value:
        raise ValueError("api_base must be '' or an absolute http(s) URL")
    scheme = value.split("://", 1)[0].lower()
    if scheme not in {"http", "https"}:
        raise ValueError("api_base must use http or https")
    if any(character.isspace() for character in value):
        raise ValueError("api_base must not contain whitespace")


@dataclass(frozen=True)
class Settings:
    host: str = "0.0.0.0"
    port: int = 8011
    model: str = "openai:gpt-4o-mini"
    default_agent: str = "weather"
    web_dir: str | None = None
    web_full_dir: str | None = None
    ui_preset: Literal["minimal", "full"] = "minimal"
    api_base: str = ""
    identity_mode: Literal["anonymous", "delegated"] = "anonymous"
    # "debug" lets the bundled UI surface backend error detail in the thread;
    # "prod" keeps a generic failure message. It changes nothing else.
    server_mode: Literal["prod", "debug"] = "prod"
    database_url: str | None = None
    database_path: str = "agent-chat.db"
    checkpoint_database_url: str | None = None
    checkpoint_database_path: str = "agent-chat-checkpoints.db"
    auto_migrate: bool = True
    persistence_enabled: bool = False
    app_title: str = "Agent Chat"
    welcome_heading: str = "How can I help?"
    welcome_description: str = "Ask a question to get started."
    composer_placeholder: str = "Message the assistant..."
    # None means the YAML omitted questions; () means intentionally none.
    proposed_questions: tuple[ProposedQuestion, ...] | None = None

    def __post_init__(self) -> None:
        if not self.host.strip():
            raise ValueError("host must not be empty")
        if not 1 <= self.port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        if not self.model.strip():
            raise ValueError("model must not be empty")
        if not self.default_agent.strip():
            raise ValueError("default_agent must not be empty")
        if self.ui_preset not in {"minimal", "full"}:
            raise ValueError("ui_preset must be 'minimal' or 'full'")
        if self.identity_mode not in {"anonymous", "delegated"}:
            raise ValueError("identity_mode must be 'anonymous' or 'delegated'")
        if self.server_mode not in {"prod", "debug"}:
            raise ValueError("server_mode must be 'prod' or 'debug'")
        _validate_api_base(self.api_base)
        if self.database_url is not None and not self.database_url.strip():
            raise ValueError("database_url must not be empty")
        if not self.database_path.strip():
            raise ValueError("database_path must not be empty")
        if (
            self.checkpoint_database_url is not None
            and not self.checkpoint_database_url.strip()
        ):
            raise ValueError("checkpoint_database_url must not be empty")
        if not self.checkpoint_database_path.strip():
            raise ValueError("checkpoint_database_path must not be empty")
        for name in ("app_title", "welcome_heading", "welcome_description", "composer_placeholder"):
            value = getattr(self, name)
            if not value.strip() or len(value) > 500:
                raise ValueError(f"{name} must contain 1 to 500 characters")
        if self.proposed_questions is not None and len({question.id for question in self.proposed_questions}) != len(self.proposed_questions):
            raise ValueError("proposed question ids must be unique")

    @classmethod
    def from_env(cls) -> "Settings":
        port_raw = os.getenv("PORT", "8011")
        try:
            port = int(port_raw)
        except ValueError as exc:
            raise ValueError("PORT must be an integer") from exc
        auto_migrate_raw = os.getenv("AUTO_MIGRATE", "true").lower()
        if auto_migrate_raw not in {"true", "false", "1", "0"}:
            raise ValueError("AUTO_MIGRATE must be true or false")
        return cls(
            host=os.getenv("HOST", "0.0.0.0"),
            port=port,
            model=os.getenv("MODEL", "openai:gpt-4o-mini"),
            default_agent=os.getenv("DEFAULT_AGENT", "weather"),
            web_dir=os.getenv("MINIMAL_WEB_DIR"),
            web_full_dir=os.getenv("FULL_WEB_DIR"),
            ui_preset=os.getenv("UI_PRESET", "minimal"),
            api_base=os.getenv("API_BASE", ""),
            identity_mode=os.getenv("IDENTITY_MODE", "anonymous"),
            server_mode=os.getenv("SERVER_MODE", "prod"),
            database_url=os.getenv("DATABASE_URL") or None,
            database_path=os.getenv("DATABASE_PATH", "agent-chat.db"),
            checkpoint_database_url=os.getenv("CHECKPOINT_DATABASE_URL") or None,
            checkpoint_database_path=os.getenv(
                "CHECKPOINT_DATABASE_PATH", "agent-chat-checkpoints.db"
            ),
            auto_migrate=auto_migrate_raw in {"true", "1"},
            persistence_enabled=(
                os.getenv("PERSISTENCE_ENABLED", "false").lower()
                in {"true", "1"}
                or any(
                    os.getenv(name)
                    for name in (
                        "DATABASE_URL",
                        "DATABASE_PATH",
                        "CHECKPOINT_DATABASE_URL",
                        "CHECKPOINT_DATABASE_PATH",
                    )
                )
            ),
        )

    @classmethod
    def from_yaml(
        cls,
        path: str | Path,
        *,
        environ: Mapping[str, str] | None = None,
        overrides: Mapping[str, Any] | None = None,
    ) -> "Settings":
        """Load a versioned YAML file with present environment values applied.

        Precedence is defaults, YAML, explicitly present supported environment
        variables, then explicit caller overrides. Relative SQLite/static paths
        are interpreted relative to the configuration file, never ``cwd``.
        """
        config_path = Path(path).expanduser().resolve()
        if not config_path.is_file():
            raise ValueError(f"configuration file does not exist: {config_path}")
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover - base dependency guard
            raise RuntimeError("YAML configuration requires PyYAML") from exc
        try:
            document = yaml.safe_load(config_path.read_text())
        except yaml.YAMLError as exc:
            raise ValueError(f"invalid YAML configuration: {exc}") from exc
        if document is None:
            document = {}
        if not isinstance(document, dict):
            raise ValueError("configuration root must be a mapping")
        version = document.pop("version", CONFIG_VERSION)
        if version != CONFIG_VERSION:
            raise ValueError(f"unsupported configuration version: {version!r}")
        ui = document.pop("ui", None)
        if ui is not None:
            document.update(_parse_ui_config(ui))
        unknown = set(document) - _CONFIG_FIELDS
        if unknown:
            raise ValueError(f"unknown configuration field(s): {', '.join(sorted(unknown))}")
        values = asdict(cls())
        values.update(document)
        for name in ("web_dir", "web_full_dir", "database_path", "checkpoint_database_path"):
            value = values.get(name)
            if value and not Path(value).expanduser().is_absolute():
                values[name] = str(config_path.parent / value)
        values.update(_present_env_overrides(os.environ if environ is None else environ))
        if overrides:
            unknown = set(overrides) - _CONFIG_FIELDS
            if unknown:
                raise ValueError(f"unknown settings override(s): {', '.join(sorted(unknown))}")
            values.update(overrides)
        return cls(**values)

    @classmethod
    def load(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        """Load ``AGENT_CHAT_CONFIG`` when explicitly set, otherwise env defaults."""
        env = os.environ if environ is None else environ
        config_path = env.get("AGENT_CHAT_CONFIG")
        return cls.from_yaml(config_path, environ=env) if config_path else cls.from_env()

    def resolved_database_url(self) -> str:
        if self.database_url is not None:
            return self.database_url
        path = Path(self.database_path).expanduser().resolve().as_posix()
        return f"sqlite+aiosqlite:///{path}"

    def resolved_checkpoint_database_url(self) -> str:
        if self.checkpoint_database_url is not None:
            return self.checkpoint_database_url
        path = Path(self.checkpoint_database_path).expanduser().resolve().as_posix()
        return f"sqlite+aiosqlite:///{path}"

    def web_dir_path(self, fallback: Path) -> Path | None:
        if self.web_dir:
            return Path(self.web_dir)
        return None if fallback is None else fallback


def _parse_bool(value: str, name: str) -> bool:
    if value.lower() not in {"true", "false", "1", "0"}:
        raise ValueError(f"{name} must be true or false")
    return value.lower() in {"true", "1"}


def _present_env_overrides(environ: Mapping[str, str]) -> dict[str, Any]:
    """Translate only environment variables that are present into settings."""
    values: dict[str, Any] = {}
    names = {
        "HOST": "host", "MODEL": "model", "DEFAULT_AGENT": "default_agent",
        "MINIMAL_WEB_DIR": "web_dir", "FULL_WEB_DIR": "web_full_dir",
        "UI_PRESET": "ui_preset", "API_BASE": "api_base", "IDENTITY_MODE": "identity_mode",
        "SERVER_MODE": "server_mode",
        "DATABASE_URL": "database_url", "DATABASE_PATH": "database_path",
        "CHECKPOINT_DATABASE_URL": "checkpoint_database_url",
        "CHECKPOINT_DATABASE_PATH": "checkpoint_database_path",
    }
    for env_name, field_name in names.items():
        if env_name in environ:
            values[field_name] = environ[env_name] or None if env_name.endswith("_URL") else environ[env_name]
    if "PORT" in environ:
        try:
            values["port"] = int(environ["PORT"])
        except ValueError as exc:
            raise ValueError("PORT must be an integer") from exc
    for env_name, field_name in (("AUTO_MIGRATE", "auto_migrate"), ("PERSISTENCE_ENABLED", "persistence_enabled")):
        if env_name in environ:
            values[field_name] = _parse_bool(environ[env_name], env_name)
    return values


def _parse_ui_config(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("ui must be a mapping")
    names = {
        "title": "app_title",
        "welcome_heading": "welcome_heading",
        "welcome_description": "welcome_description",
        "composer_placeholder": "composer_placeholder",
    }
    unknown = set(value) - set(names) - {"questions"}
    if unknown:
        raise ValueError(f"unknown ui field(s): {', '.join(sorted(unknown))}")
    parsed = {target: value[source] for source, target in names.items() if source in value}
    if "questions" not in value:
        return parsed
    questions = value["questions"]
    if not isinstance(questions, list):
        raise ValueError("ui.questions must be a list")
    result: list[ProposedQuestion] = []
    for index, item in enumerate(questions):
        if not isinstance(item, dict):
            raise ValueError(f"ui.questions[{index}] must be a mapping")
        unknown = set(item) - {"id", "label", "prompt", "agents", "capabilities"}
        required = {"id", "label", "prompt"} - set(item)
        if unknown or required:
            details = sorted(unknown or required)
            raise ValueError(f"invalid ui.questions[{index}] field(s): {', '.join(details)}")
        agents = _string_list(item.get("agents", []), f"ui.questions[{index}].agents")
        capabilities = _string_list(item.get("capabilities", []), f"ui.questions[{index}].capabilities")
        result.append(ProposedQuestion(item["id"], item["label"], item["prompt"], agents, capabilities))
    parsed["proposed_questions"] = tuple(result)
    return parsed


def _string_list(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{name} must be a list of non-empty strings")
    return tuple(value)


ENV_DOC = """\
HOST=0.0.0.0                # uvicorn bind host
PORT=8011                   # uvicorn bind port
MODEL=openai:gpt-4o-mini    # provider:model spec (anthropic:.., ollama:..)
DEFAULT_AGENT=weather       # registry id aliased by POST /assistant
MINIMAL_WEB_DIR=            # override bundled web/ (empty = bundled)
FULL_WEB_DIR=               # override bundled web_full/ (empty = bundled)
UI_PRESET=minimal           # runtime UI preset: minimal or full
API_BASE=                   # same-origin default; absolute http(s) URL for split-port dev
IDENTITY_MODE=anonymous     # anonymous or delegated (custom principal resolver)
SERVER_MODE=prod            # prod hides backend error detail in the UI; debug surfaces it
DATABASE_PATH=agent-chat.db # default application SQLite file
DATABASE_URL=               # SQLAlchemy URL; overrides DATABASE_PATH
CHECKPOINT_DATABASE_PATH=agent-chat-checkpoints.db # separate graph state file
CHECKPOINT_DATABASE_URL=    # SQLite URL; overrides CHECKPOINT_DATABASE_PATH
AUTO_MIGRATE=true           # composition roots may upgrade before opening repos
PERSISTENCE_ENABLED=false   # open SQLite repos/checkpoints in supported entry points
AGENT_CHAT_CONFIG=           # explicit versioned YAML configuration path
OPENAI_API_KEY=             # credential for the default openai model
ANTHROPIC_API_KEY=          # credential when MODEL uses anthropic:
"""
