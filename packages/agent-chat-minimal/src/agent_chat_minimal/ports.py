"""Async ports for identity and application persistence."""

from typing import Protocol, TypeVar

from .domain import Feedback, Principal, Session, StoredMessage


ContextT = TypeVar("ContextT", contravariant=True)


class PrincipalResolver(Protocol[ContextT]):
    """Resolve an untrusted transport context into a trusted principal."""

    async def resolve(self, context: ContextT) -> Principal: ...


class SessionRepository(Protocol):
    async def add(self, session: Session) -> None: ...

    async def get(self, session_id: str) -> Session | None: ...

    async def list_by_owner(
        self, owner_subject: str, *, include_archived: bool = False
    ) -> list[Session]: ...

    async def update(self, session: Session) -> None: ...

    async def delete(self, session_id: str) -> bool: ...


class TranscriptRepository(Protocol):
    async def add(self, message: StoredMessage) -> None: ...

    async def get(self, message_id: str) -> StoredMessage | None: ...

    async def list_by_session(self, session_id: str) -> list[StoredMessage]: ...

    async def delete_by_session(self, session_id: str) -> None: ...


class FeedbackRepository(Protocol):
    async def upsert(self, feedback: Feedback) -> Feedback: ...

    async def get_for_message(
        self, session_id: str, message_id: str
    ) -> Feedback | None: ...

    async def list_by_session(self, session_id: str) -> list[Feedback]: ...

    async def delete_for_message(self, session_id: str, message_id: str) -> bool: ...

    async def delete_by_session(self, session_id: str) -> None: ...


class CheckpointDeleter(Protocol):
    """Optional separate-lifecycle port implemented by PUIR-06."""

    async def delete_session(self, session_id: str) -> None: ...


__all__ = [
    "CheckpointDeleter",
    "FeedbackRepository",
    "PrincipalResolver",
    "SessionRepository",
    "TranscriptRepository",
]
