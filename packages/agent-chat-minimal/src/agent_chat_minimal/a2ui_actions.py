"""Server-side contract for A2UI component actions (A2UI-08).

An action arrives as structured data ``{surface_id, component_id, action,
action_id?}`` and is stored as ONE canonical user message so transcripts stay
byte-identical no matter which client (or client version) dispatched it:

    [a2ui-action {name}] {"name": ..., "context": {...}, ...}

The endpoint (:func:`create_app <agent_chat_minimal.server.create_app>` route
``POST /threads/{id}/a2ui-action``) persists first and returns the stored
message id; the UI then mirrors that exact message locally, preserving the
existing run behavior. Retries with the same ``action_id`` are idempotent via
the transcript store's stable-ID dedupe. Unknown/foreign/archived sessions
are rejected exactly like verbatim message appends.
"""

from __future__ import annotations

import json
from typing import Any

MAX_NAME_LEN = 128
MAX_ID_LEN = 128
MAX_CONTEXT_BYTES = 8 * 1024


def format_action_text(name: str, action: dict[str, Any]) -> str:
    """Canonical transcript text for a dispatched action."""
    return f"[a2ui-action {name}] {json.dumps(action, separators=(',', ':'))}"


def build_action_message(
    *,
    name: str,
    action: dict[str, Any],
    message_id: str,
) -> dict[str, Any]:
    """Verbatim assistant-ui user message carrying a dispatched action."""
    return {
        "id": message_id,
        "role": "user",
        "content": [{"type": "text", "text": format_action_text(name, action)}],
    }


def check_action_shape(
    *,
    name: str,
    surface_id: str,
    component_id: str,
    context: dict[str, Any],
) -> None:
    """Raise :class:`ValueError` when an action exceeds the stored contract."""
    if not name or len(name) > MAX_NAME_LEN:
        raise ValueError(f"action name must be 1..{MAX_NAME_LEN} chars")
    for label, value in (("surface_id", surface_id), ("component_id", component_id)):
        if not value or len(value) > MAX_ID_LEN:
            raise ValueError(f"{label} must be 1..{MAX_ID_LEN} chars")
    if len(json.dumps(context, separators=(",", ":")).encode()) > MAX_CONTEXT_BYTES:
        raise ValueError(f"action context exceeds {MAX_CONTEXT_BYTES} bytes")
