"""Capabilities exposed by an assembled application."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class CapabilityProvider:
    """Describe the UI preset and features wired by the composition root."""

    preset: Literal["minimal", "full"]
    enabled: frozenset[str]

    @classmethod
    def for_preset(
        cls, preset: Literal["minimal", "full"]
    ) -> "CapabilityProvider":
        # Both current presets use the same compatibility API. Later composition
        # roots can remove capabilities when their backing services are absent.
        return cls(
            preset=preset,
            enabled=frozenset({"agents", "assistant", "threads", "transcripts"}),
        )

    def supports(self, capability: str) -> bool:
        return capability in self.enabled

    def agent_listing(self, agent_ids: list[str], default: str) -> dict[str, object]:
        if not self.supports("agents"):
            return {"agents": [], "default": None}
        return {"agents": sorted(agent_ids), "default": default}

    def as_dict(self) -> dict[str, object]:
        """Return the provider shape intended for future runtime UI config."""
        return {"preset": self.preset, "enabled": sorted(self.enabled)}
