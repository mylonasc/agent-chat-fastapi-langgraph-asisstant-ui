from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessageChunk

from agent_chat_minimal import ScopedChatRequest, create_app
from agent_chat_minimal.transport import (
    append_graph_event,
    create_response,
    create_run,
)


FIXTURES = Path(__file__).parent / "fixtures"


def _golden(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _client_for(callback) -> TestClient:
    app = FastAPI()

    @app.get("/stream")
    async def stream():
        return create_response(create_run(callback, state=callback.initial_state))

    return TestClient(app)


def test_state_data_framing_content_type_and_clean_completion():
    async def callback(controller):
        controller.state["status"] = "running"
        controller.state["items"].append({"id": 1})
        controller.append_text("hello")
        controller.add_data({"progress": 1})

    callback.initial_state = {"status": "idle", "items": []}
    response = _client_for(callback).get("/stream")

    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    # 0.0.2 signals successful completion with EOF, not a completion frame.
    assert response.text == _golden("protocol_state.txt")


def test_incremental_message_merge_and_graph_update_golden():
    async def callback(controller):
        append_graph_event(
            controller.state,
            (),
            "messages",
            (AIMessageChunk(content="Hel", id="m1"), {}),
        )
        append_graph_event(
            controller.state,
            (),
            "messages",
            (AIMessageChunk(content="lo", id="m1"), {}),
        )
        append_graph_event(
            controller.state,
            (),
            "updates",
            {"node": {"answer": 42, "messages": []}},
        )

    callback.initial_state = {"messages": []}
    response = _client_for(callback).get("/stream")

    assert response.text == _golden("protocol_graph.txt")


def test_tool_framing_golden():
    async def callback(controller):
        tool = await controller.add_tool_call("weather", "call_1")
        tool.append_args_text('{"city":')
        tool.append_args_text('"Athens"}')
        tool.set_response({"temperature": 24})

    callback.initial_state = {}
    response = _client_for(callback).get("/stream")

    assert response.text == _golden("protocol_tool.txt")


def test_explicit_error_framing_and_completion():
    async def callback(controller):
        controller.add_error("expected failure")

    callback.initial_state = {}
    response = _client_for(callback).get("/stream")

    assert response.text == '3:"expected failure"\n'


class CustomUpdateGraph:
    async def astream(self, *args, **kwargs):
        yield (), "custom", {"tool": "search", "status": "running"}
        yield (), "updates", {"node": {"score": 7}}


def test_canonical_custom_and_update_state_golden():
    response = TestClient(create_app(graph=CustomUpdateGraph())).post(
        "/assistant", json={"state": {"messages": []}, "commands": []}
    )

    assert response.text == _golden("protocol_custom.txt")


def test_scoped_request_remains_public_and_accepts_transport_fields():
    request = ScopedChatRequest.model_validate(
        {
            "commands": [],
            "state": {},
            "thread_id": "thread-1",
            "user_id": "user-1",
        }
    )

    assert request.thread_id == "thread-1"
    assert request.user_id == "user-1"
