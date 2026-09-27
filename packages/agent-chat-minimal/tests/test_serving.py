import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing import Annotated, TypedDict

from agent_chat_minimal import create_app


class _EchoState(TypedDict):
    messages: Annotated[list, add_messages]


def _make_marker_agent(marker: str):
    workflow = StateGraph(_EchoState)
    workflow.add_node("reply", lambda state: {"messages": [AIMessage(content=marker)]})
    workflow.set_entry_point("reply")
    workflow.add_edge("reply", END)
    return workflow.compile()


def _chat_payload(text: str):
    return {
        "state": {"messages": []},
        "commands": [
            {
                "type": "add-message",
                "message": {
                    "id": "test-1",
                    "parts": [{"type": "text", "text": text}],
                },
            }
        ],
    }


def test_api_and_static_serving_without_network(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("MINIMAL_AGENT_FACTORY", raising=False)
    web_dir = tmp_path / "web"
    asset = web_dir / "_next" / "static" / "test.js"
    asset.parent.mkdir(parents=True)
    (web_dir / "index.html").write_text("<html>minimal fixture</html>")
    asset.write_text("fixture asset")

    client = TestClient(create_app(web_dir=web_dir))

    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/").text == "<html>minimal fixture</html>"
    assert client.get("/_next/static/test.js").text == "fixture asset"
    assert client.get("/unknown/spa/path").text == "<html>minimal fixture</html>"

    # The default agent answers with no API key configured.
    response = client.post("/assistant", json=_chat_payload("hello offline"))
    assert response.status_code == 200
    assert "hello offline" in response.text


def test_weather_and_graph_intents_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("MINIMAL_AGENT_FACTORY", raising=False)
    client = TestClient(create_app(web_dir=None))

    weather = client.post("/assistant", json=_chat_payload("weather in Paris"))
    assert weather.status_code == 200
    assert "Paris" in weather.text

    graph = client.post("/assistant", json=_chat_payload("show me a graph"))
    assert graph.status_code == 200
    assert "render_graph" in graph.text


def test_custom_graph_factory():
    client = TestClient(
        create_app(
            web_dir=None,
            graph_factory=lambda: _make_marker_agent("custom-marker-123"),
        )
    )

    response = client.post("/assistant", json=_chat_payload("hi"))
    assert response.status_code == 200
    assert "custom-marker-123" in response.text


def test_agent_factory_env_var(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv(
        "MINIMAL_AGENT_FACTORY",
        "agent_chat_minimal.demo_agent.local_agent:make_local_agent",
    )
    client = TestClient(create_app(web_dir=None))

    response = client.post("/assistant", json=_chat_payload("hello env"))
    assert response.status_code == 200
    assert "hello env" in response.text


def test_agent_factory_env_var_rejects_bad_values(monkeypatch):
    monkeypatch.setenv("MINIMAL_AGENT_FACTORY", "not-a-factory-path")
    with pytest.raises(ValueError, match="MINIMAL_AGENT_FACTORY"):
        create_app(web_dir=None)

    monkeypatch.setenv("MINIMAL_AGENT_FACTORY", "agent_chat_minimal:__version__")
    with pytest.raises(TypeError, match="not callable"):
        create_app(web_dir=None)
