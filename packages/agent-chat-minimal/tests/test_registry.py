from fastapi.testclient import TestClient
from langchain_core.messages.ai import AIMessageChunk

from agent_chat_minimal import create_app
from agent_chat_minimal import registry
from agent_chat_minimal.demo_agent.calculator import add, divide, multiply, subtract
from agent_chat_minimal.registry import AGENT_REGISTRY


class ToyGraph:
    def __init__(self, text="toy hi"):
        self.text = text

    async def astream(self, *args, **kwargs):
        yield (), "messages", (AIMessageChunk(content=self.text), {})


def test_registry_contains_weather_and_calculator():
    assert set(AGENT_REGISTRY) >= {"weather", "calculator"}


def test_calculator_tools_offline():
    assert add.invoke({"a": 2, "b": 3}) == 5
    assert subtract.invoke({"a": 10, "b": 4}) == 6
    assert multiply.invoke({"a": 6, "b": 7}) == 42
    assert divide.invoke({"a": 20, "b": 4}) == 5


def test_agents_endpoint_and_per_agent_route():
    client = TestClient(
        create_app(agents={"a": lambda: ToyGraph("A"), "b": lambda: ToyGraph("B")})
    )
    body = client.get("/agents").json()
    assert body["agents"] == ["a", "b"]
    assert body["default"] == "a"

    for agent_id, expected in (("a", "A"), ("b", "B")):
        response = client.post(
            f"/assistant/{agent_id}",
            json={"state": {"messages": []}, "commands": []},
        )
        assert response.status_code == 200, agent_id


def test_unknown_agent_404():
    client = TestClient(create_app(agents={"a": lambda: ToyGraph()}))
    response = client.post(
        "/assistant/nope", json={"state": {"messages": []}, "commands": []}
    )
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "unknown_agent"


def test_custom_agents_map_default_alias():
    client = TestClient(
        create_app(
            agents={"calc": lambda: ToyGraph("calc hi")}, default_agent="calc"
        )
    )
    response = client.post(
        "/assistant", json={"state": {"messages": []}, "commands": []}
    )
    assert response.status_code == 200


def test_invalid_default_agent_fails_at_app_creation():
    try:
        create_app(agents={"calc": lambda: ToyGraph()}, default_agent="missing")
    except ValueError as exc:
        assert "default_agent 'missing' is not registered" in str(exc)
    else:  # pragma: no cover - assertion helper
        raise AssertionError("create_app accepted an invalid default agent")


def test_empty_agents_map_fails_at_app_creation():
    try:
        create_app(agents={})
    except ValueError as exc:
        assert str(exc) == "agents must contain at least one factory"
    else:  # pragma: no cover - assertion helper
        raise AssertionError("create_app accepted an empty agents mapping")


def test_non_openai_weather_agent_is_not_blocked_without_openai_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("MODEL", "ollama:llama3.1")
    monkeypatch.setattr(
        registry, "discover_agents", lambda: {"weather": lambda: ToyGraph()}
    )

    client = TestClient(create_app())
    response = client.post(
        "/assistant", json={"state": {"messages": []}, "commands": []}
    )

    assert response.status_code == 200


def test_agent_factory_error_reports_selected_provider_failure():
    def broken_anthropic():
        raise RuntimeError("ANTHROPIC_API_KEY is missing")

    client = TestClient(
        create_app(agents={"anthropic": broken_anthropic})
    )
    response = client.post(
        "/assistant", json={"state": {"messages": []}, "commands": []}
    )

    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "agent_not_ready"
    assert "ANTHROPIC_API_KEY" in response.json()["detail"]["hint"]
