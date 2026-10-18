"""Route tests for POST /threads/{id}/a2ui-action (A2UI-08)."""

from fastapi.testclient import TestClient

from agent_chat_minimal import a2ui_actions, create_app
from agent_chat_minimal.demo_agent.tools.a2ui import is_a2ui_envelope  # noqa: F401


class ToyGraph:
    async def astream(self, *args, **kwargs):
        if False:  # pragma: no cover - keep async-generator shape
            yield ()


def _client(**kwargs):
    kwargs.setdefault("graph", ToyGraph())
    return TestClient(create_app(**kwargs))


OWNER = {"x-agent-chat-subject": "action-owner"}
OTHER = {"x-agent-chat-subject": "action-other"}

ACTION = {
    "surface_id": "demo-card",
    "component_id": "submit-btn",
    "action": {"name": "confirm_booking", "context": {"surfaceId": "demo-card"}},
    "action_id": "act-1",
}


def test_action_stored_as_canonical_user_message():
    client = _client()
    client.post("/threads", json={"localId": "t1"}, headers=OWNER)
    res = client.post("/threads/t1/a2ui-action", json=ACTION, headers=OWNER)
    assert res.status_code == 200
    body = res.json()
    assert body == {
        "ok": True,
        "message_id": "act-1",
        "text": '[a2ui-action confirm_booking] {"name":"confirm_booking","context":{"surfaceId":"demo-card"}}',
    }
    stored = client.get("/threads/t1/messages", headers=OWNER).json()["messages"]
    assert len(stored) == 1
    assert stored[0]["role"] == "user"
    assert stored[0]["content"] == [{"type": "text", "text": body["text"]}]


def test_action_retry_is_idempotent():
    client = _client()
    client.post("/threads", json={"localId": "t1"}, headers=OWNER)
    first = client.post("/threads/t1/a2ui-action", json=ACTION, headers=OWNER)
    retry = client.post("/threads/t1/a2ui-action", json=ACTION, headers=OWNER)
    assert retry.status_code == 200
    assert retry.json()["message_id"] == first.json()["message_id"]
    stored = client.get("/threads/t1/messages", headers=OWNER).json()["messages"]
    assert len(stored) == 1


def test_action_rejects_unknown_foreign_and_bad_shapes():
    client = _client()
    assert (
        client.post("/threads/missing/a2ui-action", json=ACTION, headers=OWNER).status_code
        == 404
    )
    client.post("/threads", json={"localId": "t1"}, headers=OWNER)
    assert (
        client.post("/threads/t1/a2ui-action", json=ACTION, headers=OTHER).status_code
        in (403, 404)
    )
    bad_name = dict(ACTION, action={"name": "", "context": {}})
    assert (
        client.post("/threads/t1/a2ui-action", json=bad_name, headers=OWNER).status_code
        == 422
    )
    bad_context = dict(ACTION, action={"name": "x", "context": [1]})
    assert (
        client.post("/threads/t1/a2ui-action", json=bad_context, headers=OWNER).status_code
        == 422
    )
    huge = dict(
        ACTION,
        action_id="act-huge",
        action={"name": "x", "context": {"blob": "y" * 9000}},
    )
    assert (
        client.post("/threads/t1/a2ui-action", json=huge, headers=OWNER).status_code
        == 422
    )


def test_builders_match_stored_format():
    text = a2ui_actions.format_action_text("n", {"name": "n", "context": {}})
    assert text == '[a2ui-action n] {"name":"n","context":{}}'
    msg = a2ui_actions.build_action_message(name="n", action={"name": "n"}, message_id="m")
    assert msg == {
        "id": "m",
        "role": "user",
        "content": [{"type": "text", "text": '[a2ui-action n] {"name":"n"}'}],
    }


def test_openapi_documents_action_and_feedback_routes():
    # Regression pin: inserting the action route once swallowed the GET
    # feedback decorator, removing the route without any import error.
    spec = _client().get("/openapi.json").json()
    assert "/threads/{thread_id}/a2ui-action" in spec["paths"]
    feedback = spec["paths"]["/threads/{thread_id}/messages/{message_id}/feedback"]
    assert set(feedback) >= {"get", "put", "delete"}
