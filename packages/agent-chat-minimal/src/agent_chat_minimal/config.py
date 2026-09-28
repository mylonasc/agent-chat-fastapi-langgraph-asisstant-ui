"""Centralized settings for the portable chat server (#14).

One place for every env var / CLI flag. Stdlib only on purpose: the wheel
stays dependency-light (no ``pydantic-settings`` required).
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class Settings:
    host: str = "0.0.0.0"
    port: int = 8011
    model: str = "openai:gpt-4o-mini"
    default_agent: str = "weather"
    web_dir: str | None = None
    web_full_dir: str | None = None
    ui_preset: Literal["minimal", "full"] = "minimal"
    database_url: str | None = None
    database_path: str = "agent-chat.db"
    checkpoint_database_url: str | None = None
    checkpoint_database_path: str = "agent-chat-checkpoints.db"
    auto_migrate: bool = True

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
            database_url=os.getenv("DATABASE_URL") or None,
            database_path=os.getenv("DATABASE_PATH", "agent-chat.db"),
            checkpoint_database_url=os.getenv("CHECKPOINT_DATABASE_URL") or None,
            checkpoint_database_path=os.getenv(
                "CHECKPOINT_DATABASE_PATH", "agent-chat-checkpoints.db"
            ),
            auto_migrate=auto_migrate_raw in {"true", "1"},
        )

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


ENV_DOC = """\
HOST=0.0.0.0                # uvicorn bind host
PORT=8011                   # uvicorn bind port
MODEL=openai:gpt-4o-mini    # provider:model spec (anthropic:.., ollama:..)
DEFAULT_AGENT=weather       # registry id aliased by POST /assistant
MINIMAL_WEB_DIR=            # override bundled web/ (empty = bundled)
FULL_WEB_DIR=               # override bundled web_full/ (empty = bundled)
UI_PRESET=minimal           # runtime UI preset: minimal or full
DATABASE_PATH=agent-chat.db # default application SQLite file
DATABASE_URL=               # SQLAlchemy URL; overrides DATABASE_PATH
CHECKPOINT_DATABASE_PATH=agent-chat-checkpoints.db # separate graph state file
CHECKPOINT_DATABASE_URL=    # SQLite URL; overrides CHECKPOINT_DATABASE_PATH
AUTO_MIGRATE=true           # composition roots may upgrade before opening repos
OPENAI_API_KEY=             # credential for the default openai model
ANTHROPIC_API_KEY=          # credential when MODEL uses anthropic:
"""
