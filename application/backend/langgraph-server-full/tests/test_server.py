import pytest
from httpx import AsyncClient, ASGITransport 
import uuid

from server import app, thread_manager  # Adjust 'main' to your filename

@pytest.fixture
def anyio_backend():
    return "asyncio"

transport = ASGITransport(app = app)

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
                    "parts": [{"type": "text", "text": "Hello, bot!"}]
                }
            }
        ],
        "user_id": user_id
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
        await ac.post("/assistant", json={
            "commands": [{
                "type": "add-message", 
                "message": {"parts": [{"type": "text", "text": "My name is Charlie."}]}
            }],
            "thread_id": thread_id,
            "user_id": user_id
        })

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
        response = await ac.post("/assistant", json={
            "commands": "not a list",
            "thread_id": "123"
        })
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
