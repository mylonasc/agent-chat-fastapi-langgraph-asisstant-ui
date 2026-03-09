import pytest
from httpx import AsyncClient, ASGITransport
import uuid

from fastlang.server.server import (
    app,
    thread_manager,
    _append_tool_update,
    _append_updates_from_graph_chunk,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


transport = ASGITransport(app=app)


@pytest.fixture(autouse=True)
def clear_threads():
    """Clears the thread manager before each test to ensure isolation."""
    thread_manager._threads = {}


@pytest.mark.anyio
async def test_create_thread_on_chat():
    """Test that sending a message creates a record in the thread manager."""
    user_id = "test_user_1"
    # We leave thread_id empty to trigger auto-creation
    payload = {
        "commands": [
            {
                "type": "add-message",
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "text": "Hello, bot!"}],
                },
            }
        ],
        "user_id": user_id,
    }

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/assistant", json=payload)
        assert response.status_code == 200

        # Verify thread was created in the manager
        threads = await ac.get(f"/threads?user_id={user_id}")
        assert len(threads.json()) == 1
        assert threads.json()[0]["user_id"] == user_id


@pytest.mark.anyio
async def test_message_persistence_in_langgraph():
    """Test that LangGraph checkpointer actually remembers the conversation context."""
    thread_id = f"test-thread-{uuid.uuid4()}"
    user_id = "test_user_2"

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Tell the bot my name
        await ac.post(
            "/assistant",
            json={
                "commands": [
                    {
                        "type": "add-message",
                        "message": {
                            "parts": [{"type": "text", "text": "My name is Charlie."}]
                        },
                    }
                ],
                "thread_id": thread_id,
                "user_id": user_id,
            },
        )

        # 2. Retrieve history and verify it exists in the checkpointer
        history_resp = await ac.get(f"/threads/{thread_id}/messages")
        assert history_resp.status_code == 200
        messages = history_resp.json()["messages"]
        # Look for the human message in history
        assert any("Charlie" in m["content"] for m in messages if m["type"] == "human")


@pytest.mark.anyio
async def test_scoped_chat_request_invalid_data():
    """Verify that Pydantic validation works for the ScopedChatRequest."""
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Sending 'commands' as a string instead of a list should trigger 422 Unprocessable Entity
        response = await ac.post(
            "/assistant", json={"commands": "not a list", "thread_id": "123"}
        )
        assert response.status_code == 422


@pytest.mark.anyio
async def test_list_threads_filtering():
    """Verify that user_id filtering works in the thread manager."""
    thread_manager.create_thread("user_A", "Title A")
    thread_manager.create_thread("user_B", "Title B")

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/threads?user_id=user_A")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Title A"


@pytest.mark.anyio
async def test_rename_thread_endpoint_updates_title():
    thread = thread_manager.create_thread("user_rename", "New Chat")

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.patch(
            f"/threads/{thread.id}", json={"title": "RAG Debug Session"}
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["title"] == "RAG Debug Session"


@pytest.mark.anyio
async def test_archive_and_delete_thread_endpoints_persist_changes():
    thread = thread_manager.create_thread("user_archive", "Session To Archive")

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        archive_resp = await ac.post(f"/threads/{thread.id}/archive")
        assert archive_resp.status_code == 200
        assert archive_resp.json()["is_archived"] is True

        list_resp = await ac.get("/threads?user_id=user_archive")
        assert list_resp.status_code == 200
        assert list_resp.json() == []

        list_all_resp = await ac.get(
            "/threads?user_id=user_archive&include_archived=true"
        )
        assert list_all_resp.status_code == 200
        assert len(list_all_resp.json()) == 1

        delete_resp = await ac.delete(f"/threads/{thread.id}")
        assert delete_resp.status_code == 200
        assert delete_resp.json()["ok"] is True

        fetch_resp = await ac.get(f"/threads/{thread.id}")
        assert fetch_resp.status_code == 404


@pytest.mark.anyio
async def test_tools_overview_endpoint_returns_tool_and_docling_info():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/tools/overview?user_id=default_user")
        assert resp.status_code == 200
        payload = resp.json()

        assert "tools" in payload
        assert "available" in payload["tools"]
        assert "web_rag" in payload["tools"]["available"]
        assert payload["docling"]["is_standalone_tool"] is False
        assert payload["docling"]["owner_tool"] == "web_rag"


def test_append_tool_update_keeps_recent_entries_only():
    state = {"tool_updates": []}

    for i in range(250):
        _append_tool_update(state, {"i": i})

    assert len(state["tool_updates"]) == 200
    assert state["tool_updates"][0]["i"] == 50
    assert state["tool_updates"][-1]["i"] == 249


def test_append_updates_from_graph_chunk_tracks_requested_and_completed_tools():
    class DummyAI:
        type = "ai"
        tool_calls = [{"name": "web_search", "id": "call_1"}]

    class DummyTool:
        type = "tool"
        name = "web_search"
        tool_call_id = "call_1"

    state = {"tool_updates": []}

    _append_updates_from_graph_chunk(state, {"agent": {"messages": [DummyAI()]}})
    _append_updates_from_graph_chunk(state, {"tools": {"messages": [DummyTool()]}})

    assert state["tool_updates"][0]["status"] == "requested"
    assert state["tool_updates"][1]["status"] == "completed"
    assert state["tool_updates"][1]["tool"] == "web_search"
