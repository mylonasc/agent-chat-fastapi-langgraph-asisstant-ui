"""Classify model-provider failures into stable, UI-safe error codes (#68).

Mid-stream provider errors (missing API key, invalid key, exhausted credits,
rate limits) used to propagate raw into the SSE stream: prod leaked provider
internals into the UI, debug showed an unstructured blob. This module maps an
exception to ``{error, message, hint}`` using dependency-light heuristics on
the exception class name + message (no provider SDK imports), and formats the
stream error payload honoring ``SERVER_MODE``:

- ``debug`` (dev mode): code + provider detail + fix hint;
- ``prod``: stable code + generic message, no provider internals.
"""

from __future__ import annotations

import json
import re

GENERIC_MESSAGE = "The assistant failed while generating a response."

_MISSING_KEY = re.compile(r"api[_ -]?key", re.IGNORECASE)
_MISSING_MARK = re.compile(
    r"missing|not provided|not found|not set|required|must be (set|provided)|"
    r"environment|no .*key",
    re.IGNORECASE,
)
_UNAUTHORIZED = re.compile(
    r"\b401\b|unauthorized|incorrect (api )?key|invalid (api )?key|"
    r"invalid_api_key|authentication",
    re.IGNORECASE,
)
_QUOTA = re.compile(
    r"insufficient|quota|billing|out of credit|credits? (exhausted|depleted|"
    r"expired|finished)|ran out|you exceeded",
    re.IGNORECASE,
)
_RATE_LIMIT = re.compile(
    r"\b429\b|rate.?limit|too many requests|ratelimit",
    re.IGNORECASE,
)


def classify_provider_error(exc: BaseException) -> dict[str, str]:
    """Map a provider exception to ``{error, message, hint}`` (always safe)."""
    signature = f"{type(exc).__name__}: {exc}"
    if _MISSING_KEY.search(signature) and _MISSING_MARK.search(signature):
        return {
            "error": "auth_missing_key",
            "message": "Model API key is missing.",
            "hint": (
                "Set the provider key (e.g. OPENAI_API_KEY for the default "
                "model) and restart the server."
            ),
        }
    if _QUOTA.search(signature):
        return {
            "error": "quota_exhausted",
            "message": "Model provider credits are exhausted.",
            "hint": (
                "Check provider billing / quota, top up credits, then retry."
            ),
        }
    if _UNAUTHORIZED.search(signature):
        return {
            "error": "auth_invalid_key",
            "message": "Model provider rejected the API key.",
            "hint": "Verify the provider API key is correct and active.",
        }
    if _RATE_LIMIT.search(signature):
        return {
            "error": "rate_limited",
            "message": "Model provider rate limit hit.",
            "hint": "Wait briefly and retry; back off on repeated hits.",
        }
    first_line = str(exc).strip().splitlines()[0] if str(exc).strip() else ""
    return {
        "error": "provider_error",
        "message": first_line[:300] or "Model provider call failed.",
        "hint": "Retry; check server logs for the provider traceback.",
    }


def format_stream_error(exc: BaseException, *, debug: bool) -> str:
    """JSON error text forwarded into the stream (``str`` reaches the UI).

    Debug carries code + detail + hint; prod carries only the stable code
    and a generic message so provider internals never reach the browser.
    """
    classified = classify_provider_error(exc)
    if debug:
        return json.dumps(classified, separators=(",", ":"))
    return json.dumps(
        {"error": classified["error"], "message": GENERIC_MESSAGE},
        separators=(",", ":"),
    )
