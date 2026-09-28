"""Framework-independent chat persistence domain models."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TypeAlias
from uuid import uuid4

Metadata: TypeAlias = dict[str, Any]


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(timezone.utc)


def new_id() -> str:
    """Return an opaque, stable identifier suitable for persisted entities."""
    return str(uuid4())


def _require_text(value: str, name: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{name} must not be empty")


def _require_utc(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    if value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError(f"{name} must use UTC")


@dataclass(frozen=True, slots=True)
class Principal:
    """Trusted actor identity produced by a composition-root resolver."""

    subject: str
    claims: Metadata = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.subject, "principal subject")


class SessionStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


@dataclass(frozen=True, slots=True)
class Session:
    id: str
    owner_subject: str
    title: str
    created_at: datetime
    updated_at: datetime
    status: SessionStatus = SessionStatus.ACTIVE
    archived_at: datetime | None = None
    metadata: Metadata = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.id, "session id")
        _require_text(self.owner_subject, "session owner")
        _require_text(self.title, "session title")
        _require_utc(self.created_at, "created_at")
        _require_utc(self.updated_at, "updated_at")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        if self.archived_at is not None:
            _require_utc(self.archived_at, "archived_at")
        if self.status is SessionStatus.ARCHIVED and self.archived_at is None:
            raise ValueError("archived sessions require archived_at")
        if self.status is SessionStatus.ACTIVE and self.archived_at is not None:
            raise ValueError("active sessions cannot have archived_at")


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


@dataclass(frozen=True, slots=True)
class StoredMessage:
    """A transport-neutral transcript entry with caller-supplied JSON payload."""

    id: str
    session_id: str
    sequence: int
    role: MessageRole
    payload: Any
    created_at: datetime
    metadata: Metadata = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.id, "message id")
        _require_text(self.session_id, "message session id")
        if self.sequence < 1:
            raise ValueError("message sequence must be positive")
        _require_utc(self.created_at, "created_at")


class FeedbackRating(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"


@dataclass(frozen=True, slots=True)
class Feedback:
    id: str
    session_id: str
    message_id: str
    owner_subject: str
    rating: FeedbackRating
    created_at: datetime
    updated_at: datetime
    comment: str | None = None
    metadata: Metadata = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.id, "feedback id")
        _require_text(self.session_id, "feedback session id")
        _require_text(self.message_id, "feedback message id")
        _require_text(self.owner_subject, "feedback owner")
        _require_utc(self.created_at, "created_at")
        _require_utc(self.updated_at, "updated_at")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")


__all__ = [
    "Feedback",
    "FeedbackRating",
    "MessageRole",
    "Metadata",
    "Principal",
    "Session",
    "SessionStatus",
    "StoredMessage",
    "new_id",
    "utc_now",
]
