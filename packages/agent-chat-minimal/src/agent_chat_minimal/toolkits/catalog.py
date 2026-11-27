"""Tool metadata is shared by validation, agent composition, and the settings UI.

Importing the catalogue never imports an optional web/embedding dependency.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Knob:
    label: str
    kind: str
    default: Any
    minimum: int | None = None
    maximum: int | None = None
    choices: tuple[str, ...] = ()
    scope: str = "conversation"
    effect: str = "next_turn"

    def validate(self, value):
        if self.kind == "boolean":
            valid = type(value) is bool
        elif self.kind == "integer":
            valid = type(value) is int
        else:
            valid = isinstance(value, str) and value in self.choices
        if not valid:
            raise ValueError(f"{self.label}: invalid {self.kind} value")
        if self.kind == "integer" and not self.minimum <= value <= self.maximum:
            raise ValueError(
                f"{self.label}: must be between {self.minimum} and {self.maximum}"
            )
        return value

    def public(self):
        return {
            "label": self.label,
            "type": self.kind,
            "default": self.default,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "choices": list(self.choices),
            "scope": self.scope,
            "effect": self.effect,
        }


@dataclass(frozen=True)
class ToolSpec:
    name: str
    title: str
    knobs: dict[str, Knob] = field(default_factory=dict)


@dataclass(frozen=True)
class Toolkit:
    id: str
    title: str
    description: str
    tools: tuple[ToolSpec, ...]
    dependencies: tuple[str, ...] = ()


PRECISION = Knob("Decimal places", "integer", 6, 0, 12)
CATALOG = (
    Toolkit(
        "calculator",
        "Calculator",
        "Basic arithmetic; no network access.",
        tuple(
            ToolSpec(name, name.capitalize(), {"precision": PRECISION})
            for name in ("add", "subtract", "multiply", "divide")
        ),
    ),
    Toolkit(
        "weather",
        "Demo weather",
        "Simulated weather, not a live weather service.",
        (
            ToolSpec(
                "get_weather",
                "Weather",
                {
                    "units": Knob(
                        "Units", "enum", "celsius", choices=("celsius", "fahrenheit")
                    )
                },
            ),
        ),
    ),
    Toolkit(
        "graph",
        "Graphs",
        "Render graphs in either interface.",
        (
            ToolSpec(
                "render_graph",
                "Render graph",
                {"max_nodes": Knob("Maximum nodes", "integer", 100, 1, 500)},
            ),
        ),
    ),
    Toolkit(
        "web_search",
        "Web search",
        "Search with Serper. Requires backend SERPER_API_KEY.",
        (
            ToolSpec(
                "web_search",
                "Web search",
                {
                    "max_results": Knob("Maximum results", "integer", 5, 1, 10),
                    "auto_index": Knob(
                        "Index search results", "boolean", False, scope="admin"
                    ),
                    "wait_for_indexing": Knob("Wait for indexing", "boolean", True),
                },
            ),
        ),
        ("requests",),
    ),
    Toolkit(
        "web_rag",
        "Web RAG",
        "Hybrid FAISS/BM25 retrieval. Web bootstrap requires web_search too.",
        (
            ToolSpec(
                "web_rag",
                "Retrieve documents",
                {
                    "k": Knob("Retrieved chunks", "integer", 5, 1, 20),
                    "auto_bootstrap_web": Knob(
                        "Bootstrap an empty index from the web",
                        "boolean",
                        False,
                        scope="admin",
                    ),
                    "chunk_size": Knob(
                        "Index chunk size (characters)",
                        "integer",
                        800,
                        200,
                        4000,
                        scope="startup",
                        effect="reindex",
                    ),
                    "embedding_provider": Knob(
                        "Embedding provider",
                        "enum",
                        "fastembed",
                        choices=("fastembed", "openai"),
                        scope="startup",
                        effect="reindex",
                    ),
                },
            ),
            ToolSpec("web_rag_status", "Index status"),
        ),
        ("faiss", "fastembed", "rank_bm25", "langchain_community"),
    ),
)
TOOLKITS = {item.id: item for item in CATALOG}
TOOLS = {tool.name: tool for item in CATALOG for tool in item.tools}
BASIC = ("calculator", "weather", "graph")


def installation_extras(toolsets):
    selected = ids(toolsets)
    if "web_rag" in selected:
        return ("web",)
    return ("web-search",) if "web_search" in selected else ()


def ids(value):
    """Strict list parser shared by settings and CLI/environment adapters."""
    if isinstance(value, str):
        value = [] if not value.strip() else [part.strip() for part in value.split(",")]
    if not isinstance(value, (list, tuple)) or any(
        not isinstance(item, str) for item in value
    ):
        raise ValueError("toolsets must be a list of toolset IDs")
    if len(value) != len(set(value)):
        raise ValueError("duplicate toolset IDs")
    unknown = set(value) - TOOLKITS.keys()
    if unknown:
        raise ValueError(f"Unknown toolsets: {', '.join(sorted(unknown))}")
    return tuple(value)
