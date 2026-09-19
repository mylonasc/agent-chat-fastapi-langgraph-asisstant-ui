from typing import List, Optional, TypedDict

from langchain_core.tools import tool


class GraphNode(TypedDict, total=False):
    id: str
    label: Optional[str]
    weight: int


class GraphEdge(TypedDict, total=False):
    source: str
    target: str
    label: Optional[str]
    weight: int


class GraphPayload(TypedDict, total=False):
    directed: bool
    nodes: List[GraphNode]
    edges: List[GraphEdge]


def _clamp_0_100(x, default: int) -> int:
    try:
        value = int(x)
    except Exception:
        return default
    return max(0, min(100, value))


@tool("render_graph")
def render_graph(
    nodes: List[GraphNode],
    edges: List[GraphEdge],
    directed: bool = False,
) -> dict:
    """
    Render an interactive graph in the UI.

    nodes: [{id, label?, weight? (0..100)}]
    edges: [{source, target, label?, weight? (0..100)}]
    directed: if true, show arrows (directed edges)
    """
    clean_nodes = []
    seen = set()
    for node in nodes or []:
        node_id = node.get("id")
        if not node_id or node_id in seen:
            continue
        seen.add(node_id)
        clean_nodes.append(
            {
                "id": str(node_id),
                "label": node.get("label"),
                "weight": _clamp_0_100(node.get("weight"), default=50),
            }
        )

    clean_edges = []
    for edge in edges or []:
        source, target = edge.get("source"), edge.get("target")
        if not source or not target:
            continue
        clean_edges.append(
            {
                "source": str(source),
                "target": str(target),
                "label": edge.get("label"),
                "weight": _clamp_0_100(edge.get("weight"), default=50),
            }
        )

    return {"directed": bool(directed), "nodes": clean_nodes, "edges": clean_edges}
