"""PUIR-07 compatibility contract: same HTTP behavior on every backend.

The in-memory and SQLite configurations run one shared assertion suite over
the compatibility routes (threads, messages, scoped assistant). Ownership
always comes from the resolved principal: the ``x-agent-chat-subject`` header
selects the subject (``default_user`` fallback) and legacy ``user_id`` values
that disagree with it are rejected with 403.
"""

import asyncio
import os
from pathlib import Path
from tempfile import mkstemp

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages.ai import AIMessageChunk

from agent_chat_minimal import create_app
from agent_chat_minimal.adapters import InMemoryRepositories
from agent_chat_minimal.adapters.sqlite import SQLiteRepositories, sqlite_url
from agent_chat_minimal.services import SessionService, TranscriptService

SUBJECT_HEADER = "x-agent-chat-subject"


class ToyGraph:
    async def astream(self, *args, **kwargs):
        yield (), "messages", (AIMessageChunk(content="hi"), {})


def _services(repositories, checkpoint_deleter=None):
    sessions = SessionService(
        repositories.sessions,
        repositories.transcripts,
        repositories.feedback,
        checkpoint_deleter,
    )
    transcripts = TranscriptService(
        repositories.sessions, repositories.transcripts
    )
    return sessions, transcripts


def _memory_client(**kwargs):
    repositories = InMemoryRepositories()
    kwargs.setdefault("graph", ToyGraph())
    return TestClient(
        create_app(
            repositories=repositories,
            session_service=kwargs.pop("session_service", None)
            or _services(repositories)[0],
            transcript_service=kwargs.pop("transcript_service", None)
            or _services(repositories)[1],
            **kwargs,
        )
    ), repositories


def _sqlite_client(tmp_path, **kwargs):
    path = tmp_path / "compat.db"
    repositories = asyncio.run(SQLiteRepositories.open(sqlite_url(path)))
    sessions, transcripts = _services(
        repositories, kwargs.pop("checkpoint_deleter", None)
    )
    client = TestClient(
        create_app(
            repositories=repositories,
            session_service=sessions,
            transcript_service=transcripts,
            graph=kwargs.pop("graph", ToyGraph()),
            **kwargs,
        )
    )
    return client, repositories


@pytest.fixture(params=["memory", "sqlite"])
def backend(request, tmp_path):
    if request.param == "memory":
        client, repositories = _memory_client()
        yield client, repositories, None
    else:
        client, repositories = _sqlite_client(tmp_path)
        yield client, repositories, tmp_path
        asyncio.run(repositories.dispose())


def _as(subject):
    return {SUBJECT_HEADER: subject} if subject else {}


def test_thread_crud_lifecycle(backend):
    client, _, _ = backend
    assert client.get("/threads").json() == []

    created = client.post("/threads", json={"localId": "t1", "title": "First"}).json()
    assert created["id"] == "t1"
    assert created["user_id"] == "default_user"
    assert created["is_archived"] is False

    again = client.post("/threads", json={"localId": "t1"}).json()
    assert again["id"] == "t1"

    assert client.get("/threads/t1").json()["title"] == "First"
    renamed = client.patch("/threads/t1", json={"title": "Renamed"}).json()
    assert renamed["title"] == "Renamed"
    assert client.patch("/threads/t1", json={"title": "  "}).status_code == 400

    client.post("/threads/t1/archive")
    assert client.get("/threads").json() == []
    assert len(client.get("/threads", params={"include_archived": True}).json()) == 1
    client.post("/threads/t1/unarchive")
    assert len(client.get("/threads").json()) == 1

    assert client.get("/threads/missing").status_code == 404
    assert client.delete("/threads/t1").json() == {"ok": True}
    assert client.delete("/threads/t1").status_code == 404


def test_cross_principal_access_is_rejected(backend):
    client, _, _ = backend
    assert (
        client.post("/threads", json={"localId": "alice-t"}, headers=_as("alice")).status_code
        == 200
    )

    # Bob cannot read, rename, archive, message, or delete Alice's session.
    assert client.get("/threads/alice-t", headers=_as("bob")).status_code == 403
    assert (
        client.patch("/threads/alice-t", json={"title": "stolen"}, headers=_as("bob")).status_code
        == 403
    )
    assert client.post("/threads/alice-t/archive", headers=_as("bob")).status_code == 403
    assert (
        client.post(
            "/threads/alice-t/messages",
            json={"message": {"role": "user", "text": "hi"}},
            headers=_as("bob"),
        ).status_code
        == 403
    )
    assert client.delete("/threads/alice-t", headers=_as("bob")).status_code == 403

    # Legacy user_id values that disagree with the principal are rejected.
    assert client.get("/threads", params={"user_id": "alice"}, headers=_as("bob")).status_code == 403
    assert (
        client.post(
            "/threads",
            json={"localId": "t2", "user_id": "alice"},
            headers=_as("bob"),
        ).status_code
        == 403
    )

    # Sessions are isolated per subject.
    assert client.get("/threads", headers=_as("alice")).json()[0]["id"] == "alice-t"
    assert client.get("/threads", headers=_as("bob")).json() == []

    # The owner can still delete after the rejected attempts.
    assert client.delete("/threads/alice-t", headers=_as("alice")).json() == {"ok": True}


def test_messages_round_trip_and_delete_cascades(backend):
    client, _, _ = backend
    client.post("/threads", json={"localId": "t1"})
    assert client.get("/threads/t1/messages").json() == {"messages": []}

    msg = {"id": "m1", "role": "user", "parts": [{"type": "text", "text": "hi"}]}
    assert client.post("/threads/t1/messages", json={"message": msg}).json() == {"ok": True}
    assert client.get("/threads/t1/messages").json() == {"messages": [msg]}

    # Unknown sessions have no transcript to append to.
    assert (
        client.post("/threads/missing/messages", json={"message": msg}).status_code == 404
    )

    client.delete("/threads/t1")
    client.post("/threads", json={"localId": "t1"})
    assert client.get("/threads/t1/messages").json() == {"messages": []}


def test_session_delete_invokes_checkpoint_port(tmp_path):
    deleted = []

    class Checkpoints:
        async def delete_session(self, session_id):
            deleted.append(session_id)

    client, repositories = _sqlite_client(tmp_path, checkpoint_deleter=Checkpoints())
    try:
        client.post("/threads", json={"localId": "t1"})
        msg = {"id": "m1", "role": "user", "parts": [{"type": "text", "text": "hi"}]}
        client.post("/threads/t1/messages", json={"message": msg})
        assert client.delete("/threads/t1").json() == {"ok": True}
        assert deleted == ["t1"]
        assert asyncio.run(repositories.transcripts.list_by_session("t1")) == []
    finally:
        asyncio.run(repositories.dispose())


def test_session_delete_invokes_checkpoint_port_memory():
    deleted = []

    class Checkpoints:
        async def delete_session(self, session_id):
            deleted.append(session_id)

    repositories = InMemoryRepositories()
    sessions, transcripts = _services(repositories, Checkpoints())
    client = TestClient(
        create_app(
            repositories=repositories,
            session_service=sessions,
            transcript_service=transcripts,
            graph=ToyGraph(),
        )
    )
    client.post("/threads", json={"localId": "t1"})
    assert client.delete("/threads/t1").json() == {"ok": True}
    assert deleted == ["t1"]


def test_scoped_assistant_auto_creates_owned_session(backend):
    client, _, _ = backend
    response = client.post(
        "/assistant",
        json={"thread_id": "t-new", "user_id": "default_user", "state": {}, "commands": []},
    )
    assert response.status_code == 200
    assert client.get("/threads/t-new").json()["user_id"] == "default_user"

    # The legacy body user_id never determines ownership.
    response = client.post(
        "/assistant",
        json={"thread_id": "t-alice", "user_id": "someone-else", "state": {}, "commands": []},
        headers=_as("alice"),
    )
    assert response.status_code == 200
    assert client.get("/threads/t-alice", headers=_as("alice")).json()["user_id"] == "alice"
    assert client.get("/threads/t-alice", headers=_as("bob")).status_code == 403


def test_archived_sessions_reject_message_writes(backend):
    client, _, _ = backend
    client.post("/threads", json={"localId": "t1"})
    client.post("/threads/t1/archive")
    msg = {"id": "m1", "role": "user", "parts": [{"type": "text", "text": "hi"}]}
    assert client.post("/threads/t1/messages", json={"message": msg}).status_code == 409
    client.post("/threads/t1/unarchive")
    assert client.post("/threads/t1/messages", json={"message": msg}).json() == {"ok": True}


def test_openapi_documents_thread_routes(backend):
    client, _, _ = backend
    spec = client.get("/openapi.json").json()
    for path in (
        "/threads",
        "/threads/{thread_id}",
        "/threads/{thread_id}/messages",
        "/assistant",
    ):
        assert path in spec["paths"], path


def test_unsupported_tool_capabilities_refuse_as_json(backend):
    client, _, _ = backend
    response = client.get("/tools/web_rag/status?user_id=default_user")
    assert response.status_code == 501
    assert response.json()["detail"]["error"] == "capability_disabled"
    assert (
        client.post("/tools/web_rag/tools", json={}).status_code == 501
    )
