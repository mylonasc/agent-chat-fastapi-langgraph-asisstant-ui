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


def test_default_prepare_state_matches_ui_fallback_message_ids():
    state = {
        "messages": [
            {"type": "human", "id": "0", "content": "first"},
            {"type": "ai", "id": "tool-call", "content": ""},
            {"type": "tool", "tool_call_id": "call-1", "content": "2"},
            {"type": "ai", "id": "final", "content": "done"},
        ]
    }
    request = ScopedChatRequest.model_validate(_cmd("second"))

    messages = default_prepare_state(state, request)

    assert messages[-1]["id"] == "2"


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


def test_resolve_thread_id_defaults_and_runconfig():
    class R:
        def __init__(self, state, runConfig):
            self.state = state
            self.runConfig = runConfig

    assert resolve_thread_id(R({}, None)) == "default"
    assert resolve_thread_id(R({"thread_id": "a"}, None)) == "a"
    assert resolve_thread_id(R({}, {"thread_id": "b"})) == "b"


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("PORT", "9999")
    monkeypatch.setenv("MODEL", "ollama:llama3.1")
    monkeypatch.setenv("DEFAULT_AGENT", "calculator")
    settings = Settings.from_env()
    assert (settings.port, settings.model, settings.default_agent) == (
        9999,
        "ollama:llama3.1",
        "calculator",
    )


def test_post_assistant_still_streams_with_command():
    client = TestClient(create_app(graph=ToyGraph()))
    assert client.post("/assistant", json=_cmd()).status_code == 200
