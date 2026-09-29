"""Configured custom-agent composition (AGS-06)."""

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages.ai import AIMessageChunk

from agent_chat_minimal import (
    ModelConfig,
    Settings,
    bundled_ui_dir,
    create_app,
    create_configured_app,
    is_ui_bundle,
    resolve_ui_dir,
)
from agent_chat_minimal import registry


class ToyGraph:
    def __init__(self, text="custom hi"):
        self.text = text

    async def astream(self, *args, **kwargs):
        yield (), "messages", (AIMessageChunk(content=self.text), {})


def _chat(client):
    return client.post("/assistant", json={"state": {"messages": []}, "commands": []})


def test_configured_app_serves_custom_agents_in_memory():
    settings = Settings(default_agent="custom")
    app = create_configured_app(settings, agents={"custom": lambda: ToyGraph()})
    with TestClient(app) as client:
        assert client.get("/agents").json() == {"agents": ["custom"], "default": "custom"}
        assert _chat(client).status_code == 200


def test_configured_app_rejects_unknown_default_agent():
    settings = Settings(default_agent="missing")
    with pytest.raises(ValueError, match="default_agent 'missing' is not registered"):
        create_configured_app(settings, agents={"custom": lambda: ToyGraph()})


def test_configured_durable_app_composes_custom_agents(tmp_path):
    settings = Settings(
        default_agent="custom",
        database_path=str(tmp_path / "app.db"),
        checkpoint_database_path=str(tmp_path / "checkpoints.db"),
        persistence_enabled=True,
    )
    seen = {}

    def custom_factory(checkpointer=None):
        seen["checkpointer"] = checkpointer
        return ToyGraph("durable custom")

    app = create_configured_app(settings, agents={"custom": custom_factory})
    assert app.state.repositories is not None
    assert app.state.checkpoints is not None
    headers = {"x-agent-chat-subject": "custom-test"}
    with TestClient(app) as client:
        assert _chat(client).status_code == 200
        created = client.post(
            "/threads", json={"localId": "t1", "title": "T"}, headers=headers
        )
        assert created.status_code == 200
    # The lazy factory ran after lifespan startup with a real saver, not None.
    assert seen["checkpointer"] is not None
    assert (tmp_path / "app.db").is_file()
    assert (tmp_path / "checkpoints.db").is_file()


def test_builtin_factories_receive_explicit_model_without_env_mutation(monkeypatch):
    monkeypatch.setenv("MODEL", "openai:env-model")
    captured = {}

    def fake_weather(model, checkpointer=None):
        captured["weather"] = model
        return ToyGraph()

    def fake_calculator(model, checkpointer=None):
        captured["calculator"] = model
        return ToyGraph()

    monkeypatch.setattr(
        "agent_chat_minimal.demo_agent.get_graph.make_agent_with_weather_tool",
        fake_weather,
    )
    monkeypatch.setattr(
        "agent_chat_minimal.demo_agent.calculator.make_calculator_agent",
        fake_calculator,
    )
    explicit = ModelConfig(provider="ollama", model="llama3.1:8b")
    factories = registry.discover_agents(model=explicit)
    factories["weather"]()
    factories["calculator"]()
    assert captured == {"weather": explicit, "calculator": explicit}


def test_independent_apps_keep_distinct_models_without_env_crosstalk(monkeypatch):
    monkeypatch.delenv("MODEL", raising=False)
    first = create_configured_app(
        Settings(model="openai:gpt-4o-mini", default_agent="a"),
        agents={"a": lambda: ToyGraph("A")},
    )
    second = create_configured_app(
        Settings(model="ollama:llama3.1:8b", default_agent="b"),
        agents={"b": lambda: ToyGraph("B")},
    )
    assert first.state.settings.model == "openai:gpt-4o-mini"
    assert second.state.settings.model == "ollama:llama3.1:8b"
    assert "MODEL" not in __import__("os").environ
    with TestClient(first) as client:
        assert client.get("/agents").json() == {"agents": ["a"], "default": "a"}
    with TestClient(second) as client:
        assert client.get("/agents").json() == {"agents": ["b"], "default": "b"}


def test_preset_change_alone_does_not_enable_persistence():
    app = create_configured_app(Settings(ui_preset="full"))
    assert not hasattr(app.state, "repositories")
    assert not hasattr(app.state, "checkpoints")


def test_bundled_ui_accessors_and_api_only_override(tmp_path):
    assert bundled_ui_dir("minimal").name == "web"
    assert bundled_ui_dir("full").name == "web_full"
    with pytest.raises(ValueError, match="preset"):
        bundled_ui_dir("unknown")

    assert resolve_ui_dir(None, "minimal") == bundled_ui_dir("minimal")
    assert resolve_ui_dir("", "minimal") == bundled_ui_dir("minimal")
    custom = tmp_path / "custom-ui"
    assert resolve_ui_dir(str(custom), "minimal") == custom
    with pytest.raises(ValueError, match="must not be blank"):
        resolve_ui_dir("   ", "minimal")

    assert is_ui_bundle(tmp_path) is False
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<html>fixture</html>")
    assert is_ui_bundle(web) is True

    # Missing override degrades to API-only mode without breaking API routes.
    settings = Settings(default_agent="custom", web_dir=str(tmp_path / "absent"))
    app = create_app(settings=settings, agents={"custom": lambda: ToyGraph()})
    client = TestClient(app)
    assert client.get("/api/config").status_code == 200
    assert client.get("/health").json() == {"status": "ok"}
