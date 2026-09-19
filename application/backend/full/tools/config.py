import os
from typing import Dict


def default_web_rag_config() -> dict:
    config = {
        "embedding_provider": os.getenv("EMBEDDING_PROVIDER", "fastembed"),
        "pdf_parser": "pypdf",
    }
    embedding_model = os.getenv("EMBEDDING_MODEL", "").strip()
    if embedding_model:
        config["embedding_model"] = embedding_model
    return config


class ToolConfigStore:
    """Runtime configuration registry for tools."""

    def __init__(self):
        self._configs: Dict[str, dict] = {"web_rag": default_web_rag_config()}

    def get(self, tool_name: str) -> dict:
        return self._configs.get(tool_name, {})

    def set(self, tool_name: str, config: dict):
        self._configs[tool_name] = config


CONFIG_STORE = ToolConfigStore()
