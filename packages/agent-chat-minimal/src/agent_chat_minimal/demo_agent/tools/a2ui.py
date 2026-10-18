"""A2UI (v0.9) envelope helpers and demo tools.

Resilience choices (deliberate, see docs):
- Protocol ``v0.9`` stable only (not v1.0-candidate, not v0.8-legacy).
- One self-contained envelope per tool call: ``createSurface`` +
  ``updateComponents`` (+ optional ``updateDataModel``) with a per-call
  ``surfaceId``. No shared mutable surface across turns, so transcript
  replay (stored verbatim by the UI) re-renders deterministically.
- Actions round-trip as ordinary user chat text over the existing
  ``/assistant`` transport. No dedicated ``/a2ui-action`` endpoint.
- Custom components (e.g. D3 network graphs) are catalog extensions:
  the agent only emits ``{"component": "NetworkGraph", ...}`` literals
  and the frontend registry decides how to render them.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from langchain_core.tools import tool
from typing_extensions import TypedDict

A2UI_VERSION = "v0.9"
BASIC_CATALOG_ID = "https://a2ui.org/specification/v0_9/basic_catalog.json"
CUSTOM_CATALOG_ID = "https://example.com/catalogs/agent-chat/v1.json"

_SURFACE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def make_surface_id(*parts: str) -> str:
    """Build a safe per-tool-call surface id from opaque parts."""
    slug = "-".join(re.sub(r"[^A-Za-z0-9_.-]+", "-", p).strip("-") for p in parts)
    slug = slug.strip("-") or "surface"
    if not _SURFACE_ID_RE.match(slug):
        slug = "surface-" + re.sub(r"[^A-Za-z0-9_.-]+", "-", slug).strip("-")
    return slug[:128]


def is_a2ui_envelope(payload: Any) -> bool:
    """Return True when *payload* looks like an A2UI envelope we can render."""
    if not isinstance(payload, dict):
        return False
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        return False
    return all(isinstance(m, dict) and m.get("version") in {"v0.9", "v0.9.1"} for m in messages)


def extract_a2ui_messages(payload: Any) -> Optional[list[dict]]:
    """Return the A2UI message list, parsing JSON strings defensively."""
    if isinstance(payload, str):
        import json

        try:
            payload = json.loads(payload)
        except Exception:
            return None
    if not isinstance(payload, dict):
        return None
    messages = payload.get("messages")
    if not is_a2ui_envelope(payload):
        return None
    return list(messages)  # type: ignore[return-value]


def build_demo_card_envelope(
    *,
    surface_id: str = "demo-card",
    title: str = "Book Your Table",
    body: str = "Pick a date, then confirm.",
) -> dict:
    """Smallest valid v0.9 envelope using only the basic catalog."""
    surface_id = make_surface_id(surface_id)
    return {
        "a2ui_version": A2UI_VERSION,
        "surfaceId": surface_id,
        "catalogId": BASIC_CATALOG_ID,
        "messages": [
            {
                "version": A2UI_VERSION,
                "createSurface": {
                    "surfaceId": surface_id,
                    "catalogId": BASIC_CATALOG_ID,
                },
            },
            {
                "version": A2UI_VERSION,
                "updateComponents": {
                    "surfaceId": surface_id,
                    "components": [
                        {
                            "id": "root",
                            "component": "Column",
                            "children": ["title", "body", "submit-btn"],
                        },
                        {
                            "id": "title",
                            "component": "Text",
                            "text": title,
                            "variant": "h1",
                        },
                        {
                            "id": "body",
                            "component": "Text",
                            "text": body,
                            "variant": "body",
                        },
                        {
                            "id": "submit-label",
                            "component": "Text",
                            "text": "Confirm",
                        },
                        {
                            "id": "submit-btn",
                            "component": "Button",
                            "child": "submit-label",
                            # NOTE: @a2ui-sdk/react 0.9 dialect: flat
                            # {"name", "context?"} (NOT {"event": {"name"}}
                            # from the a2ui.org protocol docs) and
                            # "primary" instead of variant="primary".
                            "primary": True,
                            "action": {
                                "name": "confirm_booking",
                                "context": {"surfaceId": surface_id},
                            },
                        },
                    ],
                },
            },
            {
                "version": A2UI_VERSION,
                "updateDataModel": {
                    "surfaceId": surface_id,
                    "path": "/booking",
                    "value": {"title": title, "confirmed": False},
                },
            },
        ],
    }


class A2UINode(TypedDict, total=False):
    id: str
    label: Optional[str]


class A2UIEdge(TypedDict, total=False):
    source: str
    target: str
    label: Optional[str]


def build_network_envelope(
    nodes: list[dict],
    edges: list[dict],
    *,
    surface_id: str = "network-graph",
    directed: bool = False,
) -> dict:
    """Envelope for the custom ``NetworkGraph`` catalog extension.

    Props are ``{"path": ...}`` bindings into ``/graph`` (snapshot included
    as ``updateDataModel``), so later model updates re-render without
    regenerating layout. The frontend also tolerates literal props.
    """
    surface_id = make_surface_id(surface_id)
    clean_nodes = [
        {"id": str(n.get("id")), "label": n.get("label", str(n.get("id")))}
        for n in nodes or []
        if n.get("id")
    ]
    clean_edges = [
        {"source": str(e.get("source")), "target": str(e.get("target"))}
        for e in edges or []
        if e.get("source") and e.get("target")
    ]
    return {
        "a2ui_version": A2UI_VERSION,
        "surfaceId": surface_id,
        # Custom catalog extends the basic one with NetworkGraph.
        "catalogId": CUSTOM_CATALOG_ID,
        "messages": [
            {
                "version": A2UI_VERSION,
                "createSurface": {
                    "surfaceId": surface_id,
                    "catalogId": CUSTOM_CATALOG_ID,
                },
            },
            {
                "version": A2UI_VERSION,
                "updateComponents": {
                    "surfaceId": surface_id,
                    "components": [
                        {
                            "id": "root",
                            "component": "Column",
                            "children": ["graph-title", "graph"],
                        },
                        {
                            "id": "graph-title",
                            "component": "Text",
                            "text": f"Network ({len(clean_nodes)} nodes, "
                            f"{len(clean_edges)} edges)",
                            "variant": "h2",
                        },
                        {
                            "id": "graph",
                            "component": "NetworkGraph",
                            "nodes": {"path": "/graph/nodes"},
                            "edges": {"path": "/graph/edges"},
                            "directed": {"path": "/graph/directed"},
                        },
                    ],
                },
            },
            {
                "version": A2UI_VERSION,
                "updateDataModel": {
                    "surfaceId": surface_id,
                    "path": "/graph",
                    "value": {
                        "nodes": clean_nodes,
                        "edges": clean_edges,
                        "directed": bool(directed),
                    },
                },
            },
        ],
    }


@tool("render_a2ui_demo")
def render_a2ui_demo(
    title: str = "Book Your Table",
    body: str = "Pick a date, then confirm.",
) -> dict:
    """Render a small A2UI card (basic catalog: Text, Column, Button).

    Use this when the user asks for a booking card, confirmation panel,
    or any simple structured UI. The button dispatches a
    ``confirm_booking`` action which the UI sends back as normal chat text.
    """
    return build_demo_card_envelope(title=title, body=body)


@tool("render_network_a2ui")
def render_network_a2ui(
    nodes: list[A2UINode],
    edges: list[A2UIEdge],
    directed: bool = False,
) -> dict:
    """Render an interactive D3 network graph via the custom NetworkGraph component.

    nodes: [{"id": str, "label"?: str}].
    edges: [{"source": str, "target": str}].
    Prefer this over render_graph when the client advertises A2UI support.
    """
    return build_network_envelope(
        [dict(n) for n in nodes or []],
        [dict(e) for e in edges or []],
        directed=bool(directed),
    )
