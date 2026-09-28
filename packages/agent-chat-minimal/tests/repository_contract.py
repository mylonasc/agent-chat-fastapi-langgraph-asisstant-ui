"""Reusable persistence repository contracts for current and future adapters."""

import asyncio
from dataclasses import replace

import pytest

from agent_chat_minimal.domain import (
    Feedback,
    FeedbackRating,
    MessageRole,
    Session,
    SessionStatus,
    StoredMessage,
    utc_now,
)


class RepositoryContract:
    """Subclass and implement ``make_repositories`` to verify an adapter set."""

    def make_repositories(self):
        raise NotImplementedError

    def test_session_repository_lifecycle_and_owner_filter(self):
        async def scenario():
            repos = self.make_repositories()
            now = utc_now()
            first = Session("s1", "owner-a", "First", now, now)
            second = Session("s2", "owner-b", "Second", now, now)
            await repos.sessions.add(first)
            await repos.sessions.add(second)

            assert await repos.sessions.get("s1") == first
            assert await repos.sessions.list_by_owner("owner-a") == [first]
            archived = replace(
                first,
                status=SessionStatus.ARCHIVED,
                archived_at=now,
                updated_at=now,
            )
            await repos.sessions.update(archived)
            assert await repos.sessions.list_by_owner("owner-a") == []
            assert await repos.sessions.list_by_owner(
                "owner-a", include_archived=True
            ) == [archived]
            assert await repos.sessions.delete("s1") is True
            assert await repos.sessions.delete("s1") is False

        asyncio.run(scenario())

    def test_session_ids_are_unique(self):
        async def scenario():
            repos = self.make_repositories()
            now = utc_now()
            session = Session("s1", "owner", "First", now, now)
            await repos.sessions.add(session)
            with pytest.raises(ValueError, match="already exists"):
                await repos.sessions.add(session)

        asyncio.run(scenario())

    def test_transcript_is_ordered_and_enforces_id_and_sequence(self):
        async def scenario():
            repos = self.make_repositories()
            now = utc_now()
            second = StoredMessage(
                "m2", "s1", 2, MessageRole.ASSISTANT, {"text": "two"}, now
            )
            first = StoredMessage(
                "m1", "s1", 1, MessageRole.USER, {"text": "one"}, now
            )
            await repos.transcripts.add(second)
            await repos.transcripts.add(first)
            assert await repos.transcripts.list_by_session("s1") == [first, second]
            with pytest.raises(ValueError, match="already exists"):
                await repos.transcripts.add(first)
            duplicate_sequence = replace(second, id="m3")
            with pytest.raises(ValueError, match="sequence"):
                await repos.transcripts.add(duplicate_sequence)
            await repos.transcripts.delete_by_session("s1")
            assert await repos.transcripts.list_by_session("s1") == []

        asyncio.run(scenario())

    def test_feedback_upsert_is_unique_per_message_and_preserves_id(self):
        async def scenario():
            repos = self.make_repositories()
            now = utc_now()
            positive = Feedback(
                "f1",
                "s1",
                "m1",
                "owner",
                FeedbackRating.POSITIVE,
                now,
                now,
            )
            assert await repos.feedback.upsert(positive) == positive
            negative = replace(positive, rating=FeedbackRating.NEGATIVE)
            assert await repos.feedback.upsert(negative) == negative
            assert await repos.feedback.list_by_session("s1") == [negative]
            with pytest.raises(ValueError, match="stable id"):
                await repos.feedback.upsert(replace(negative, id="f2"))
            assert await repos.feedback.delete_for_message("s1", "m1") is True
            assert await repos.feedback.delete_for_message("s1", "m1") is False

        asyncio.run(scenario())
