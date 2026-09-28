import asyncio

import pytest

from agent_chat_minimal.adapters import InMemoryRepositories
from agent_chat_minimal.domain import FeedbackRating, MessageRole, Principal
from agent_chat_minimal.services import (
    ConflictError,
    FeedbackService,
    ForbiddenError,
    NotFoundError,
    SessionService,
    TranscriptService,
)


def _services(checkpoint_deleter=None):
    repos = InMemoryRepositories()
    sessions = SessionService(
        repos.sessions,
        repos.transcripts,
        repos.feedback,
        checkpoint_deleter,
    )
    transcripts = TranscriptService(repos.sessions, repos.transcripts)
    feedback = FeedbackService(repos.sessions, repos.transcripts, repos.feedback)
    return repos, sessions, transcripts, feedback


def test_services_authorize_every_session_resource_from_principal():
    class Checkpoints:
        deleted = []

        async def delete_session(self, session_id):
            self.deleted.append(session_id)

    async def scenario():
        checkpoints = Checkpoints()
        _, sessions, transcripts, feedback = _services(checkpoints)
        owner = Principal("owner")
        intruder = Principal("intruder")
        session = await sessions.create(owner, session_id="s1")
        message = await transcripts.append(
            owner, session.id, role=MessageRole.ASSISTANT, payload={"text": "hi"}
        )

        operations = (
            sessions.get(intruder, session.id),
            sessions.rename(intruder, session.id, "stolen"),
            transcripts.list(intruder, session.id),
            transcripts.append(
                intruder, session.id, role=MessageRole.USER, payload={}
            ),
            feedback.upsert(
                intruder,
                session.id,
                message.id,
                rating=FeedbackRating.POSITIVE,
            ),
            feedback.get(intruder, session.id, message.id),
            sessions.delete(intruder, session.id),
        )
        for operation in operations:
            with pytest.raises(ForbiddenError):
                await operation

        with pytest.raises(NotFoundError):
            await sessions.get(owner, "missing")
        assert checkpoints.deleted == []

    asyncio.run(scenario())


def test_archived_sessions_are_readable_but_not_mutable():
    async def scenario():
        _, sessions, transcripts, _ = _services()
        owner = Principal("owner")
        await sessions.create(owner, session_id="s1")
        archived = await sessions.set_archived(owner, "s1", True)
        assert await sessions.get(owner, "s1") == archived
        assert await sessions.list(owner) == []
        assert await sessions.list(owner, include_archived=True) == [archived]
        with pytest.raises(ConflictError, match="archived"):
            await transcripts.append(
                owner, "s1", role=MessageRole.USER, payload={"text": "no"}
            )

    asyncio.run(scenario())


def test_feedback_upsert_is_idempotent_and_updates_in_place():
    async def scenario():
        _, sessions, transcripts, feedback = _services()
        owner = Principal("owner")
        await sessions.create(owner, session_id="s1")
        message = await transcripts.append(
            owner,
            "s1",
            role=MessageRole.ASSISTANT,
            payload={"text": "answer"},
            message_id="m1",
        )
        first = await feedback.upsert(
            owner,
            "s1",
            message.id,
            rating=FeedbackRating.POSITIVE,
            comment="Useful",
            metadata={"source": "ui"},
        )
        same = await feedback.upsert(
            owner,
            "s1",
            message.id,
            rating=FeedbackRating.POSITIVE,
            comment="Useful",
            metadata={"source": "ui"},
        )
        changed = await feedback.upsert(
            owner, "s1", message.id, rating=FeedbackRating.NEGATIVE
        )

        assert same == first
        assert changed.id == first.id
        assert changed.created_at == first.created_at
        assert changed.rating is FeedbackRating.NEGATIVE
        assert changed.comment is None

    asyncio.run(scenario())


def test_session_delete_removes_transcript_feedback_and_calls_checkpoint_port():
    class Checkpoints:
        deleted = []

        async def delete_session(self, session_id):
            self.deleted.append(session_id)

    async def scenario():
        checkpoints = Checkpoints()
        repos, sessions, transcripts, feedback = _services(checkpoints)
        owner = Principal("owner")
        await sessions.create(owner, session_id="s1")
        message = await transcripts.append(
            owner, "s1", role=MessageRole.ASSISTANT, payload={}, message_id="m1"
        )
        await feedback.upsert(
            owner, "s1", message.id, rating=FeedbackRating.POSITIVE
        )

        await sessions.delete(owner, "s1")

        assert await repos.sessions.get("s1") is None
        assert await repos.transcripts.list_by_session("s1") == []
        assert await repos.feedback.list_by_session("s1") == []
        assert checkpoints.deleted == ["s1"]
        with pytest.raises(NotFoundError):
            await sessions.delete(owner, "s1")

    asyncio.run(scenario())
