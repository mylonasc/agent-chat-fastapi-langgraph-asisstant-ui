import asyncio
import os
from datetime import timezone
from importlib import resources
from pathlib import Path
from tempfile import mkstemp

import pytest
from sqlalchemy import text

from agent_chat_minimal.adapters.sqlite import (
    SQLiteRepositories,
    create_sqlite_engine,
    current_database_revision,
    migration_head,
    sqlite_url,
    upgrade_database,
)
from agent_chat_minimal.domain import (
    Feedback,
    FeedbackRating,
    MessageRole,
    Session,
    StoredMessage,
    utc_now,
)

from repository_contract import RepositoryContract


def _database_path() -> Path:
    descriptor, path = mkstemp(suffix=".db")
    os.close(descriptor)
    Path(path).unlink()
    return Path(path)


def test_migration_resources_are_packaged():
    migration = resources.files("agent_chat_minimal").joinpath(
        "migrations", "versions", "0001_sessions_messages_feedback.py"
    )

    assert migration.is_file()


class TestSQLiteRepositoryContract(RepositoryContract):
    async def make_repositories(self):
        path = _database_path()
        repos = await SQLiteRepositories.open(sqlite_url(path))
        repos._test_path = path
        return repos

    async def close_repositories(self, repos):
        await repos.dispose()
        repos._test_path.unlink(missing_ok=True)


def test_empty_database_migrates_and_upgrade_is_idempotent():
    async def scenario():
        path = _database_path()
        engine = create_sqlite_engine(sqlite_url(path))
        try:
            assert await current_database_revision(engine) is None
            await upgrade_database(engine)
            assert await current_database_revision(engine) == migration_head()
            await upgrade_database(engine)
            assert await current_database_revision(engine) == migration_head()
        finally:
            await engine.dispose()
            path.unlink(missing_ok=True)

    asyncio.run(scenario())


def test_data_and_utc_timestamps_survive_dispose_and_reopen():
    async def scenario():
        path = _database_path()
        now = utc_now()
        first = await SQLiteRepositories.open(sqlite_url(path))
        try:
            session = Session(
                "stable-session",
                "owner",
                "Persistent",
                now,
                now,
                metadata={"nested": {"value": 1}},
            )
            await first.sessions.add(session)
            await first.transcripts.add(
                StoredMessage(
                    "stable-message",
                    session.id,
                    1,
                    MessageRole.USER,
                    {"parts": [{"text": "hello"}]},
                    now,
                    {"source": "test"},
                )
            )
        finally:
            await first.dispose()

        second = await SQLiteRepositories.open(sqlite_url(path))
        try:
            restored = await second.sessions.get("stable-session")
            assert restored == session
            assert restored.created_at.tzinfo is timezone.utc
            assert (await second.transcripts.get("stable-message")).payload == {
                "parts": [{"text": "hello"}]
            }
        finally:
            await second.dispose()
            path.unlink(missing_ok=True)

    asyncio.run(scenario())


def test_foreign_keys_cascades_pragmas_and_failed_write_rollback():
    async def scenario():
        path = _database_path()
        repos = await SQLiteRepositories.open(sqlite_url(path))
        now = utc_now()
        try:
            async with repos.engine.connect() as connection:
                assert await connection.scalar(text("PRAGMA foreign_keys")) == 1
                assert await connection.scalar(text("PRAGMA journal_mode")) == "wal"
                assert await connection.scalar(text("PRAGMA busy_timeout")) == 5000

            session = Session("s1", "owner", "Chat", now, now)
            message = StoredMessage(
                "m1", "s1", 1, MessageRole.ASSISTANT, {"text": "ok"}, now
            )
            feedback = Feedback(
                "f1",
                "s1",
                "m1",
                "owner",
                FeedbackRating.POSITIVE,
                now,
                now,
            )
            await repos.sessions.add(session)
            await repos.transcripts.add(message)
            await repos.feedback.upsert(feedback)

            with pytest.raises(ValueError, match="sequence"):
                await repos.transcripts.add(
                    StoredMessage(
                        "m2", "s1", 1, MessageRole.USER, {"text": "duplicate"}, now
                    )
                )
            assert await repos.transcripts.list_by_session("s1") == [message]

            with pytest.raises(ValueError, match="constraint"):
                await repos.feedback.upsert(
                    Feedback(
                        "f-orphan",
                        "s1",
                        "missing",
                        "owner",
                        FeedbackRating.NEGATIVE,
                        now,
                        now,
                    )
                )

            assert await repos.sessions.delete("s1") is True
            assert await repos.transcripts.get("m1") is None
            assert await repos.feedback.get_for_message("s1", "m1") is None
        finally:
            await repos.dispose()
            path.unlink(missing_ok=True)

    asyncio.run(scenario())
