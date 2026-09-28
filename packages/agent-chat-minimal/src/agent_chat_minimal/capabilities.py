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
        """Return the provider shape served by the runtime UI config."""
        return {"preset": self.preset, "enabled": sorted(self.enabled)}

    def tool_capabilities(self) -> dict[str, dict[str, object]]:
        """Describe optional tool UIs and where their status lives.

        Names absent from ``enabled`` report ``enabled: False`` so a UI can
        discover unsupported features before mounting their widgets
        (PUIR-13 owns visual gating).
        """
        return {
            name: {
                "enabled": name in self.enabled,
                "status_path": f"/tools/{name}/status" if name == "web_rag" else None,
            }
            for name in ("web_rag", "admin", "sharing", "attachments")
        }
