"""Versioned runtime UI configuration served same-origin (PUIR-08).

One static build adapts at load time: the UI fetches ``GET /api/config`` and
falls back to compiled defaults when the endpoint is unavailable or
malformed. The schema is versioned so old UIs can ignore unknown fields and
new UIs can detect stale servers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .capabilities import CapabilityProvider
from .config import ProposedQuestion, Settings

RUNTIME_CONFIG_VERSION = 1

DEFAULT_RUNTIME_CONFIG: dict[str, Any] = {
    "version": RUNTIME_CONFIG_VERSION,
    "api_base": "",
    "ui_preset": "minimal",
    "identity_mode": "anonymous",
    "features": {"agents": True, "assistant": True, "threads": True, "transcripts": True},
    "tools": {
        "web_rag": {"enabled": False, "status_path": "/tools/web_rag/status"},
        "admin": {"enabled": False, "status_path": None},
        "sharing": {"enabled": False, "status_path": None},
        "attachments": {"enabled": False, "status_path": None},
    },
    "presentation": {
        "title": "Agent Chat",
        "welcome_heading": "How can I help?",
        "welcome_description": "Ask a question to get started.",
        "composer_placeholder": "Message the assistant...",
        "questions": [
            {"id": "react-hooks", "label": "Explain React hooks", "prompt": "Explain React hooks like useState and useEffect"},
            {"id": "sql-query", "label": "Write a SQL query", "prompt": "Write a SQL query to find top customers"},
            {"id": "meal-plan", "label": "Create a meal plan", "prompt": "Create a meal plan for healthy weight loss"},
        ],
    },
}

_BASELINE_FEATURES = ("agents", "assistant", "threads", "transcripts")


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_str(value: Any, default: str) -> str:
    return value if isinstance(value, str) else default


@dataclass(frozen=True)
class RuntimeConfig:
    """Validated runtime configuration snapshot."""

    version: int = RUNTIME_CONFIG_VERSION
    api_base: str = ""
    ui_preset: str = "minimal"
    identity_mode: str = "anonymous"
    features: dict[str, bool] = field(default_factory=dict)
    tools: dict[str, dict[str, Any]] = field(default_factory=dict)
    presentation: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "api_base": self.api_base,
            "ui_preset": self.ui_preset,
            "identity_mode": self.identity_mode,
            "features": dict(self.features),
            "tools": {name: dict(info) for name, info in self.tools.items()},
            "presentation": {
                **self.presentation,
                "questions": [dict(question) for question in self.presentation.get("questions", [])],
            },
        }


def build_runtime_config(
    settings: Settings, provider: CapabilityProvider
) -> RuntimeConfig:
    """Build the served snapshot from deployment settings and capabilities."""
    features = {name: provider.supports(name) for name in _BASELINE_FEATURES}
    questions = settings.proposed_questions
    if questions is None:
        presentation = dict(DEFAULT_RUNTIME_CONFIG["presentation"])
        presentation.update({
            "title": settings.app_title,
            "welcome_heading": settings.welcome_heading,
            "welcome_description": settings.welcome_description,
            "composer_placeholder": settings.composer_placeholder,
        })
    else:
        presentation = {
            "title": settings.app_title,
            "welcome_heading": settings.welcome_heading,
            "welcome_description": settings.welcome_description,
            "composer_placeholder": settings.composer_placeholder,
            "questions": [_question_dict(question) for question in questions if _question_available(question, settings, provider)],
        }
    return RuntimeConfig(
        version=RUNTIME_CONFIG_VERSION,
        api_base=settings.api_base,
        ui_preset=settings.ui_preset,
        identity_mode=settings.identity_mode,
        features=features,
        tools=provider.tool_capabilities(),
        presentation=presentation,
    )


def _question_available(question: ProposedQuestion, settings: Settings, provider: CapabilityProvider) -> bool:
    return (not question.agents or settings.default_agent in question.agents) and all(
        provider.supports(capability) for capability in question.capabilities
    )


def _question_dict(question: ProposedQuestion) -> dict[str, str]:
    return {"id": question.id, "label": question.label, "prompt": question.prompt}


def parse_runtime_config(payload: Any) -> RuntimeConfig:
    """Parse untrusted config data with backward-compatible defaults.

    Malformed, missing, or unknown-version payloads degrade to compiled
    defaults (with the served version marker) instead of raising, so a UI
    always reaches a visible recoverable state.
    """
    data = _as_dict(payload)
    version = data.get("version")
    version = version if isinstance(version, int) and version >= 1 else RUNTIME_CONFIG_VERSION

    raw_features = _as_dict(data.get("features"))
    features = {
        name: raw_features.get(name, default)
        if isinstance(raw_features.get(name, default), bool)
        else default
        for name, default in DEFAULT_RUNTIME_CONFIG["features"].items()
    }

    raw_tools = _as_dict(data.get("tools"))
    tools: dict[str, dict[str, Any]] = {}
    for name, default_info in DEFAULT_RUNTIME_CONFIG["tools"].items():
        info = _as_dict(raw_tools.get(name))
        enabled = info.get("enabled", default_info["enabled"])
        tools[name] = {
            "enabled": enabled if isinstance(enabled, bool) else default_info["enabled"],
            "status_path": _as_str(
                info.get("status_path"), default_info["status_path"] or ""
            )
            or None,
        }

    ui_preset = _as_str(data.get("ui_preset"), "minimal")
    if ui_preset not in {"minimal", "full"}:
        ui_preset = "minimal"
    identity_mode = _as_str(data.get("identity_mode"), "anonymous")
    if identity_mode not in {"anonymous", "delegated"}:
        identity_mode = "anonymous"
    api_base = _as_str(data.get("api_base"), "")
    raw_presentation = _as_dict(data.get("presentation"))
    default_presentation = DEFAULT_RUNTIME_CONFIG["presentation"]
    questions = raw_presentation.get("questions", default_presentation["questions"])
    if not isinstance(questions, list) or not all(isinstance(question, dict) and all(isinstance(question.get(name), str) for name in ("id", "label", "prompt")) for question in questions):
        questions = default_presentation["questions"]
    presentation = {
        name: _as_str(raw_presentation.get(name), default_presentation[name])
        for name in ("title", "welcome_heading", "welcome_description", "composer_placeholder")
    }
    presentation["questions"] = questions

    return RuntimeConfig(
        version=version,
        api_base=api_base,
        ui_preset=ui_preset,
        identity_mode=identity_mode,
        features=features,
        tools=tools,
        presentation=presentation,
    )


__all__ = [
    "DEFAULT_RUNTIME_CONFIG",
    "RUNTIME_CONFIG_VERSION",
    "RuntimeConfig",
    "build_runtime_config",
    "parse_runtime_config",
]
