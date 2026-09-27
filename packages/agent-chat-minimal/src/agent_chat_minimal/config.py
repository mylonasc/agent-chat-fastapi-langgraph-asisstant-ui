"""Centralized settings for the portable chat server (#14).

One place for every env var / CLI flag. Stdlib only on purpose: the wheel
stays dependency-light (no ``pydantic-settings`` required).
"""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    host: str = "0.0.0.0"
    port: int = 8011
    model: str = "openai:gpt-4o-mini"
    default_agent: str = "weather"
    web_dir: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        port_raw = os.getenv("PORT", "8011")
        try:
            port = int(port_raw)
        except ValueError:
            port = 8011
        return cls(
            host=os.getenv("HOST", "0.0.0.0"),
            port=port,
            model=os.getenv("MODEL", "openai:gpt-4o-mini"),
            default_agent=os.getenv("DEFAULT_AGENT", "weather"),
            web_dir=os.getenv("MINIMAL_WEB_DIR"),
        )

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
OPENAI_API_KEY=             # credential for the default openai model
ANTHROPIC_API_KEY=          # credential when MODEL uses anthropic:
"""
