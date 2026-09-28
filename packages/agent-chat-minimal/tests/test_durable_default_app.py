"""Supported entry-point durable SQLite composition (#43)."""

import asyncio

from fastapi.testclient import TestClient

from agent_chat_minimal.composition import create_configured_app
from agent_chat_minimal.config import Settings


def _settings(tmp_path, *, auto_migrate=True):
    return Settings(
        ui_preset="full",
        database_path=str(tmp_path / "app.db"),
        checkpoint_database_path=str(tmp_path / "checkpoints.db"),
        persistence_enabled=True,
        auto_migrate=auto_migrate,
    )


def test_durable_configured_app_persists_owned_threads_and_messages(tmp_path):
    settings = _settings(tmp_path)
    headers = {"x-agent-chat-subject": "anon-test"}

    first = create_configured_app(settings)
    assert first.state.repositories is not None
    assert first.state.checkpoints is not None
    with TestClient(first) as client:
        created = client.post(
            "/threads", json={"localId": "thread-1", "title": "Durable"}, headers=headers
        )
        assert created.status_code == 200
        message = {
            "id": "message-1",
            "role": "user",
            "parts": [{"type": "text", "text": "persist me"}],
        }
        assert (
            client.post(
                "/threads/thread-1/messages", json={"message": message}, headers=headers
            ).status_code
            == 200
        )

        # Checkpoints have a separate database and saver lifecycle.
        saver = first.state.checkpoints.checkpointer
        asyncio.run(
            saver.aput(
                {"configurable": {"thread_id": "thread-1", "checkpoint_ns": ""}},
                {
                    "v": 4,
                    "ts": "2026-01-01T00:00:00+00:00",
                    "id": "checkpoint-1",
                    "channel_values": {"value": "persisted"},
                    "channel_versions": {"value": 1},
                    "versions_seen": {},
                },
                {},
                {},
            )
        )

    assert (tmp_path / "app.db").is_file()
    assert (tmp_path / "checkpoints.db").is_file()
    assert (tmp_path / "app.db") != (tmp_path / "checkpoints.db")

    second = create_configured_app(settings)
    with TestClient(second) as client:
        thread = client.get("/threads/thread-1", headers=headers)
        assert thread.status_code == 200
        assert thread.json()["title"] == "Durable"
        restored = client.get("/threads/thread-1/messages", headers=headers)
        assert restored.json() == {"messages": [message]}
        checkpoint = asyncio.run(
            second.state.checkpoints.checkpointer.aget(
                {"configurable": {"thread_id": "thread-1"}}
            )
        )
        assert checkpoint["channel_values"] == {"value": "persisted"}


def test_durable_factory_respects_disabled_auto_migrate(tmp_path):
    settings = _settings(tmp_path, auto_migrate=False)
    app = create_configured_app(settings)
    with TestClient(app):
        # Opening has not created an Alembic schema: AUTO_MIGRATE=false is
        # a policy guarantee, not a deferred implicit migration.
        assert not (tmp_path / "app.db").exists()


def test_in_memory_configured_app_remains_the_default():
    app = create_configured_app(Settings())
    assert not hasattr(app.state, "repositories")
    assert not hasattr(app.state, "checkpoints")
