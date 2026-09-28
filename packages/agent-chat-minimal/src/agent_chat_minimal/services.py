"""Authorization-enforcing application services."""

from dataclasses import replace
from typing import Any

from .domain import (
    Feedback,
    FeedbackRating,
    MessageRole,
    Principal,
    Session,
    SessionStatus,
    StoredMessage,
    new_id,
    utc_now,
)
from .ports import (
    CheckpointDeleter,
    FeedbackRepository,
    SessionRepository,
    TranscriptRepository,
)


class ServiceError(Exception):
    """Base error suitable for mapping at a transport boundary."""


class NotFoundError(ServiceError):
    pass


class ForbiddenError(ServiceError):
    pass


class ConflictError(ServiceError):
    pass


class SessionService:
    def __init__(
        self,
        sessions: SessionRepository,
        transcripts: TranscriptRepository,
        feedback: FeedbackRepository,
        checkpoint_deleter: CheckpointDeleter | None = None,
    ) -> None:
        self._sessions = sessions
        self._transcripts = transcripts
        self._feedback = feedback
        self._checkpoint_deleter = checkpoint_deleter

    async def create(
        self,
        principal: Principal,
        *,
        title: str = "New Chat",
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Session:
        identifier = session_id or new_id()
        if await self._sessions.get(identifier) is not None:
            raise ConflictError(f"session {identifier!r} already exists")
        now = utc_now()
        session = Session(
            id=identifier,
            owner_subject=principal.subject,
            title=title,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        try:
            await self._sessions.add(session)
        except ValueError as exc:
            raise ConflictError(str(exc)) from exc
        return session

    async def get(self, principal: Principal, session_id: str) -> Session:
        return await self._owned(principal, session_id)

    async def list(
        self, principal: Principal, *, include_archived: bool = False
    ) -> list[Session]:
        return await self._sessions.list_by_owner(
            principal.subject, include_archived=include_archived
        )

    async def rename(
        self, principal: Principal, session_id: str, title: str
    ) -> Session:
        session = await self._mutable(principal, session_id)
        updated = replace(session, title=title, updated_at=utc_now())
        try:
            await self._sessions.update(updated)
        except ValueError as exc:
            raise ConflictError(str(exc)) from exc
        return updated

    async def set_archived(
        self, principal: Principal, session_id: str, archived: bool
    ) -> Session:
        session = await self._owned(principal, session_id)
        target = SessionStatus.ARCHIVED if archived else SessionStatus.ACTIVE
        if session.status is target:
            return session
        now = utc_now()
        updated = replace(
            session,
            status=target,
            archived_at=now if archived else None,
            updated_at=now,
        )
        try:
            await self._sessions.update(updated)
        except ValueError as exc:
            raise ConflictError(str(exc)) from exc
        return updated

    async def delete(self, principal: Principal, session_id: str) -> None:
        await self._owned(principal, session_id)
        if self._checkpoint_deleter is not None:
            await self._checkpoint_deleter.delete_session(session_id)
        await self._feedback.delete_by_session(session_id)
        await self._transcripts.delete_by_session(session_id)
        if not await self._sessions.delete(session_id):
            raise ConflictError(f"session {session_id!r} changed during deletion")

    async def _owned(self, principal: Principal, session_id: str) -> Session:
        session = await self._sessions.get(session_id)
        if session is None:
            raise NotFoundError(f"session {session_id!r} was not found")
        if session.owner_subject != principal.subject:
            raise ForbiddenError(f"principal cannot access session {session_id!r}")
        return session

    async def _mutable(self, principal: Principal, session_id: str) -> Session:
        session = await self._owned(principal, session_id)
        if session.status is SessionStatus.ARCHIVED:
            raise ConflictError(f"session {session_id!r} is archived")
        return session


class TranscriptService:
    def __init__(
        self, sessions: SessionRepository, transcripts: TranscriptRepository
    ) -> None:
        self._sessions = sessions
        self._transcripts = transcripts

    async def list(
        self, principal: Principal, session_id: str
    ) -> list[StoredMessage]:
        await _require_owned(self._sessions, principal, session_id)
        return await self._transcripts.list_by_session(session_id)

    async def append(
        self,
        principal: Principal,
        session_id: str,
        *,
        role: MessageRole,
        payload: Any,
        message_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StoredMessage:
        session = await _require_owned(self._sessions, principal, session_id)
        if session.status is SessionStatus.ARCHIVED:
            raise ConflictError(f"session {session_id!r} is archived")
        current = await self._transcripts.list_by_session(session_id)
        message = StoredMessage(
            id=message_id or new_id(),
            session_id=session_id,
            sequence=current[-1].sequence + 1 if current else 1,
            role=role,
            payload=payload,
            created_at=utc_now(),
            metadata=metadata or {},
        )
        try:
            await self._transcripts.add(message)
        except ValueError as exc:
            raise ConflictError(str(exc)) from exc
        return message


class FeedbackService:
    def __init__(
        self,
        sessions: SessionRepository,
        transcripts: TranscriptRepository,
        feedback: FeedbackRepository,
    ) -> None:
        self._sessions = sessions
        self._transcripts = transcripts
        self._feedback = feedback

    async def upsert(
        self,
        principal: Principal,
        session_id: str,
        message_id: str,
        *,
        rating: FeedbackRating,
        comment: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Feedback:
        session = await _require_owned(self._sessions, principal, session_id)
        if session.status is SessionStatus.ARCHIVED:
            raise ConflictError(f"session {session_id!r} is archived")
        message = await self._transcripts.get(message_id)
        if message is None or message.session_id != session_id:
            raise NotFoundError(f"message {message_id!r} was not found")
        existing = await self._feedback.get_for_message(session_id, message_id)
        requested_metadata = metadata or {}
        if (
            existing is not None
            and existing.rating is rating
            and existing.comment == comment
            and existing.metadata == requested_metadata
        ):
            return existing
        now = utc_now()
        candidate = Feedback(
            id=existing.id if existing else new_id(),
            session_id=session_id,
            message_id=message_id,
            owner_subject=principal.subject,
            rating=rating,
            created_at=existing.created_at if existing else now,
            updated_at=now,
            comment=comment,
            metadata=requested_metadata,
        )
        try:
            return await self._feedback.upsert(candidate)
        except ValueError as exc:
            raise ConflictError(str(exc)) from exc

    async def get(
        self, principal: Principal, session_id: str, message_id: str
    ) -> Feedback | None:
        await _require_owned(self._sessions, principal, session_id)
        return await self._feedback.get_for_message(session_id, message_id)

    async def delete(
        self, principal: Principal, session_id: str, message_id: str
    ) -> bool:
        await _require_owned(self._sessions, principal, session_id)
        return await self._feedback.delete_for_message(session_id, message_id)


async def _require_owned(
    sessions: SessionRepository, principal: Principal, session_id: str
) -> Session:
    session = await sessions.get(session_id)
    if session is None:
        raise NotFoundError(f"session {session_id!r} was not found")
    if session.owner_subject != principal.subject:
        raise ForbiddenError(f"principal cannot access session {session_id!r}")
    return session


__all__ = [
    "ConflictError",
    "FeedbackService",
    "ForbiddenError",
    "NotFoundError",
    "ServiceError",
    "SessionService",
    "TranscriptService",
]
