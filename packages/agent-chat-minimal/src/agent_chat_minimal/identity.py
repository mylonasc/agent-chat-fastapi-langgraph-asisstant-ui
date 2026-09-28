"""Trusted principal resolution for HTTP composition (PUIR-07).

Request bodies and query strings never determine ownership. Routes resolve a
:class:`~agent_chat_minimal.domain.Principal` from the request through an
injected resolver and pass it to the application services, which enforce
ownership on every session resource.

The default resolver implements anonymous convenience isolation: browsers send
no credentials and share ``default_user``; deployments that need real
multi-user isolation inject a resolver reading a gateway/JWT/proxy header.
"""

from __future__ import annotations

from typing import Any

from .domain import Principal

SUBJECT_HEADER = "x-agent-chat-subject"
DEFAULT_SUBJECT = "default_user"


class DefaultPrincipalResolver:
    """Resolve the principal from a subject header with anonymous fallback.

    Reads ``x-agent-chat-subject`` (case-insensitive). A missing or blank
    header resolves to ``default_user``, preserving single-user behavior for
    existing clients. This is convenience isolation, not authentication.
    """

    def __init__(
        self,
        header: str = SUBJECT_HEADER,
        default_subject: str = DEFAULT_SUBJECT,
    ) -> None:
        if not header.strip():
            raise ValueError("header must not be empty")
        if not default_subject.strip():
            raise ValueError("default_subject must not be empty")
        self._header = header
        self._default_subject = default_subject

    async def resolve(self, request: Any) -> Principal:
        raw = request.headers.get(self._header)
        subject = (raw or "").strip() or self._default_subject
        return Principal(subject=subject)


__all__ = ["DEFAULT_SUBJECT", "SUBJECT_HEADER", "DefaultPrincipalResolver"]
