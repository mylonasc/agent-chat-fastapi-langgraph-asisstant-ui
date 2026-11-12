import asyncio

from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import HumanMessage

import server


def test_chat_without_tools(monkeypatch):
    monkeypatch.setattr(server, "resolve_model", lambda model: FakeListChatModel(responses=["Hello locally!"]))
    graph = server.make_chat_agent("ollama:test")
    result = asyncio.run(graph.ainvoke({"messages": [HumanMessage(content="Hello")]}))
    assert result["messages"][-1].content == "Hello locally!"


def test_local_defaults():
    settings = server.Settings.from_yaml(
        server.Path(__file__).with_name("agent_chat.yaml"), environ={}
    )
    assert settings.model == "ollama:llama3.2:latest"
    assert settings.host == "127.0.0.1"
    assert settings.persistence_enabled
    assert server.Path(settings.database_path).parent == server.Path(__file__).parent / "data"


def test_app_config_and_agent(monkeypatch):
    monkeypatch.setattr(server, "resolve_model", lambda model: FakeListChatModel(responses=["Hello!"]))
    settings = server.Settings(default_agent="chat", app_title="Local Ollama Chat")
    with TestClient(server.create_app(settings)) as client:
        assert client.get("/health").status_code == 200
        config = client.get("/api/config").json()
        assert config["presentation"]["title"] == "Local Ollama Chat"
        assert client.get("/agents").status_code == 200
        response = client.post("/assistant/chat", json={
            "state": {"messages": []},
            "commands": [{"type": "add-message", "message": {
                "role": "user", "parts": [{"type": "text", "text": "Hi"}],
            }}],
        })
        assert response.status_code == 200
        assert "Hello!" in response.text


def test_persistence_creates_data_directory(tmp_path):
    settings = server.Settings(
        default_agent="chat", persistence_enabled=True,
        database_path=str(tmp_path / "data" / "chat.db"),
        checkpoint_database_path=str(tmp_path / "data" / "checkpoints.db"),
    )
    with TestClient(server.create_app(settings)) as client:
        assert client.get("/health").status_code == 200
    assert (tmp_path / "data" / "chat.db").is_file()
