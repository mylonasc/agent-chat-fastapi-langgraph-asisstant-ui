"""Async in-memory reference implementations of persistence ports."""

import asyncio
from copy import deepcopy

from ..domain import Feedback, Session, SessionStatus, StoredMessage


class InMemorySessionRepository:
    def __init__(self) -> None:
        self._items: dict[str, Session] = {}
        self._lock = asyncio.Lock()

    async def add(self, session: Session) -> None:
        async with self._lock:
            if session.id in self._items:
                raise ValueError(f"session {session.id!r} already exists")
            self._items[session.id] = deepcopy(session)

    async def get(self, session_id: str) -> Session | None:
        async with self._lock:
            return deepcopy(self._items.get(session_id))

    async def list_by_owner(
        self, owner_subject: str, *, include_archived: bool = False
    ) -> list[Session]:
        async with self._lock:
            items = [
                item
                for item in self._items.values()
                if item.owner_subject == owner_subject
                and (include_archived or item.status is SessionStatus.ACTIVE)
            ]
            return deepcopy(sorted(items, key=lambda item: item.created_at))

    async def update(self, session: Session) -> None:
        async with self._lock:
            if session.id not in self._items:
                raise ValueError(f"session {session.id!r} does not exist")
            self._items[session.id] = deepcopy(session)

    async def delete(self, session_id: str) -> bool:
        async with self._lock:
            return self._items.pop(session_id, None) is not None


class InMemoryTranscriptRepository:
    def __init__(self) -> None:
        self._items: dict[str, StoredMessage] = {}
        self._lock = asyncio.Lock()

    async def add(self, message: StoredMessage) -> None:
        async with self._lock:
            if message.id in self._items:
                raise ValueError(f"message {message.id!r} already exists")
            if any(
                item.session_id == message.session_id
                and item.sequence == message.sequence
                for item in self._items.values()
            ):
                raise ValueError(
                    f"message sequence {message.sequence} already exists in session"
                )
            self._items[message.id] = deepcopy(message)

    async def get(self, message_id: str) -> StoredMessage | None:
        async with self._lock:
            return deepcopy(self._items.get(message_id))

    async def list_by_session(self, session_id: str) -> list[StoredMessage]:
        async with self._lock:
            items = [
                item for item in self._items.values() if item.session_id == session_id
            ]
            return deepcopy(sorted(items, key=lambda item: item.sequence))

    async def delete_by_session(self, session_id: str) -> None:
        async with self._lock:
            self._items = {
                key: item
                for key, item in self._items.items()
                if item.session_id != session_id
            }


class InMemoryFeedbackRepository:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], Feedback] = {}
        self._lock = asyncio.Lock()

    async def upsert(self, feedback: Feedback) -> Feedback:
        key = (feedback.session_id, feedback.message_id)
        async with self._lock:
            existing = self._items.get(key)
            if existing is not None and existing.id != feedback.id:
                raise ValueError("feedback upsert must preserve its stable id")
            self._items[key] = deepcopy(feedback)
            return deepcopy(feedback)

    async def get_for_message(
        self, session_id: str, message_id: str
    ) -> Feedback | None:
        async with self._lock:
            return deepcopy(self._items.get((session_id, message_id)))

    async def list_by_session(self, session_id: str) -> list[Feedback]:
        async with self._lock:
            items = [
                item for item in self._items.values() if item.session_id == session_id
            ]
            return deepcopy(sorted(items, key=lambda item: item.created_at))

    async def delete_for_message(self, session_id: str, message_id: str) -> bool:
        async with self._lock:
            return self._items.pop((session_id, message_id), None) is not None

    async def delete_by_session(self, session_id: str) -> None:
        async with self._lock:
            self._items = {
                key: item
                for key, item in self._items.items()
                if item.session_id != session_id
            }


class InMemoryRepositories:
    """Convenient bundle for composition roots and tests."""

    def __init__(self) -> None:
        self.sessions = InMemorySessionRepository()
        self.transcripts = InMemoryTranscriptRepository()
        self.feedback = InMemoryFeedbackRepository()


__all__ = [
    "InMemoryFeedbackRepository",
    "InMemoryRepositories",
    "InMemorySessionRepository",
    "InMemoryTranscriptRepository",
]
