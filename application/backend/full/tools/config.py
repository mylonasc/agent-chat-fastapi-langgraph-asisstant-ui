from typing import Dict


class ToolConfigStore:
    """Runtime configuration registry for tools."""

    def __init__(self):
        self._configs: Dict[str, dict] = {}

    def get(self, tool_name: str) -> dict:
        return self._configs.get(tool_name, {})

    def set(self, tool_name: str, config: dict):
        self._configs[tool_name] = config


CONFIG_STORE = ToolConfigStore()
