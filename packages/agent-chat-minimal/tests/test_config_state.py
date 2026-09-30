from fastapi.testclient import TestClient
from langchain_core.messages.ai import AIMessageChunk

from agent_chat_minimal import ScopedChatRequest, create_app, resolve_thread_id
from agent_chat_minimal.config import Settings
from agent_chat_minimal.server import default_prepare_state


class ToyGraph:
    def __init__(self):
        self.seen_configs = []

    async def astream(self, *args, **kwargs):
        self.seen_configs.append(kwargs.get("config"))
        yield (), "messages", (AIMessageChunk(content="hi"), {})


def _cmd(text="hello"):
    return {
        "state": {"messages": []},
        "commands": [
            {
                "type": "add-message",
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "text": text}],
                },
            }
        ],
    }


def test_default_prepare_state_folds_commands():
    msgs = default_prepare_state(
        {"messages": []},
        type(
            "R",
            (),
            {
                "commands": [
                    type(
                        "C",
                        (),
                        {
                            "type": "add-message",
                            "message": type(
                                "M",
                                (),
                                {
                                    "parts": [
                                        type("P", (), {"type": "text", "text": "hi"})()
                                    ],
                                    "id": "m1",
                                },
                            )(),
                        },
                    )()
                ]
            },
        )(),
    )
    assert msgs and msgs[0]["content"] == "hi"
    assert msgs[0]["id"] == "m1"


def test_default_prepare_state_mints_unique_non_integer_human_ids():
    # Human echo ids must never be bare integers: integer-like ids repeat in
    # every conversation (transcript 409s across threads) and the Assistant
    # UI runtime reorders integer-like keys before string keys (users grouped
    # before assistants in multi-turn threads).
    state = {
        "messages": [
            {"type": "human", "id": "u-aaa", "content": "first"},
            {"type": "ai", "id": "tool-call", "content": ""},
            {"type": "tool", "tool_call_id": "call-1", "content": "2"},
            {"type": "ai", "id": "final", "content": "done"},
        ]
    }
    request = ScopedChatRequest.model_validate(_cmd("second"))

    first = default_prepare_state(state, request)
    second = default_prepare_state(state, request)

    for folded in (first, second):
        echo_id = folded[-1]["id"]
        assert echo_id.startswith("u-")
        # Hex suffix: unique per message and never a bare integer index.
        int(echo_id.removeprefix("u-"), 16)
    assert first[-1]["id"] != second[-1]["id"]


def test_custom_prepare_state_hook_used(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    graph = ToyGraph()
    calls = []

    def custom(state, request):
        calls.append(True)
        return [{"role": "user", "content": "injected"}]

    client = TestClient(create_app(graph=graph, prepare_state=custom))
    assert (
        client.post("/assistant", json={"state": {}, "commands": []}).status_code
        == 200
    )
    assert calls


def test_thread_id_passed_as_configurable():
    graph = ToyGraph()
    client = TestClient(create_app(graph=graph))
    response = client.post(
        "/assistant",
        json={"state": {"thread_id": "t-123"}, "commands": []},
    )
    assert response.status_code == 200
    assert graph.seen_configs
    assert graph.seen_configs[0]["configurable"]["thread_id"] == "t-123"


def test_runconfig_thread_id_passed_as_configurable():
    graph = ToyGraph()
    client = TestClient(create_app(graph=graph))
    response = client.post(
        "/assistant",
        json={"state": {}, "runConfig": {"thread_id": "t-run"}, "commands": []},
    )
    assert response.status_code == 200
    assert graph.seen_configs[0]["configurable"]["thread_id"] == "t-run"


def test_resolve_thread_id_defaults_and_runconfig():
    class R:
        def __init__(self, state, runConfig):
            self.state = state
            self.runConfig = runConfig

    assert resolve_thread_id(R({}, None)) == "default"
    assert resolve_thread_id(R({}, None), default="generated") == "generated"
    assert resolve_thread_id(R({"thread_id": "a"}, None)) == "a"
    assert resolve_thread_id(R({}, {"thread_id": "b"})) == "b"


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("PORT", "9999")
    monkeypatch.setenv("MODEL", "ollama:llama3.1")
    monkeypatch.setenv("DEFAULT_AGENT", "calculator")
    monkeypatch.setenv("DATABASE_PATH", "data/chat.db")
    monkeypatch.setenv("CHECKPOINT_DATABASE_PATH", "data/checkpoints.db")
    monkeypatch.setenv("AUTO_MIGRATE", "false")
    settings = Settings.from_env()
    assert (settings.port, settings.model, settings.default_agent) == (
        9999,
        "ollama:llama3.1",
        "calculator",
    )
    assert settings.resolved_database_url().endswith("/data/chat.db")
    assert settings.resolved_checkpoint_database_url().endswith(
        "/data/checkpoints.db"
    )
    assert settings.auto_migrate is False


def test_settings_from_yaml_applies_only_present_environment_values(tmp_path):
    config = tmp_path / "agent_chat.yaml"
    config.write_text(
        "version: 1\nmodel: ollama:llama3.1:8b\nport: 9000\n"
        "database_path: data/chat.db\npersistence_enabled: true\n"
    )

    settings = Settings.from_yaml(config, environ={"PORT": "9001"})

    assert settings.model == "ollama:llama3.1:8b"
    assert settings.port == 9001
    assert settings.database_path == str(tmp_path / "data/chat.db")
    assert settings.persistence_enabled is True


def test_settings_from_yaml_rejects_unknown_or_missing_config(tmp_path):
    missing = tmp_path / "missing.yaml"
    try:
        Settings.from_yaml(missing)
    except ValueError as exc:
        assert "does not exist" in str(exc)
    else:  # pragma: no cover - assertion helper
        raise AssertionError("missing configuration was accepted")

    config = tmp_path / "agent_chat.yaml"
    config.write_text("version: 1\nmodeel: typo\n")
    try:
        Settings.from_yaml(config)
    except ValueError as exc:
        assert "unknown configuration field" in str(exc)
    else:  # pragma: no cover - assertion helper
        raise AssertionError("unknown configuration field was accepted")


def test_settings_from_yaml_parses_questions_and_preserves_explicit_empty_list(tmp_path):
    config = tmp_path / "agent_chat.yaml"
    config.write_text(
        "version: 1\nui:\n  title: Example\n  questions:\n"
        "    - id: weather\n      label: Weather\n      prompt: What is the weather in London?\n"
        "      agents: [weather]\n"
    )
    settings = Settings.from_yaml(config, environ={})
    assert settings.app_title == "Example"
    assert settings.proposed_questions[0].agents == ("weather",)

    config.write_text("version: 1\nui:\n  questions: []\n")
    assert Settings.from_yaml(config, environ={}).proposed_questions == ()


def test_post_assistant_still_streams_with_command():
    client = TestClient(create_app(graph=ToyGraph()))
    assert client.post("/assistant", json=_cmd()).status_code == 200
