from typing import TypedDict, Optional, List, Literal
from langchain_core.tools import tool

class GraphNode(TypedDict, total=False):
    id: str
    label: Optional[str]
    weight: int  # 0..100

class GraphEdge(TypedDict, total=False):
    source: str
    target: str
    label: Optional[str]
    weight: int  # 0..100

class GraphPayload(TypedDict, total=False):
    directed: bool
    nodes: List[GraphNode]
    edges: List[GraphEdge]

def _clamp_0_100(x, default: int) -> int:
    try:
        v = int(x)
    except Exception:
        return default
    return max(0, min(100, v))

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
    for n in nodes or []:
        node_id = n.get("id")
        if not node_id or node_id in seen:
            continue
        seen.add(node_id)
        clean_nodes.append(
            {
                "id": str(node_id),
                "label": n.get("label"),
                "weight": _clamp_0_100(n.get("weight"), default=50),
            }
        )

    clean_edges = []
    for e in edges or []:
        s, t = e.get("source"), e.get("target")
        if not s or not t:
            continue
        clean_edges.append(
            {
                "source": str(s),
                "target": str(t),
                "label": e.get("label"),
                "weight": _clamp_0_100(e.get("weight"), default=50),
            }
        )

    return {"directed": bool(directed), "nodes": clean_nodes, "edges": clean_edges}
