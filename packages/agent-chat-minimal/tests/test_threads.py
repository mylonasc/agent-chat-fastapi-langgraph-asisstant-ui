"""Tests for full-stack thread support in the portable server."""

from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.messages.ai import AIMessageChunk
from langgraph.checkpoint.memory import MemorySaver

from agent_chat_minimal import create_app
from agent_chat_minimal.demo_agent.calculator import make_calculator_agent
from agent_chat_minimal.threads import ThreadManager, ThreadMessageStore


class ToyGraph:
    def __init__(self, text="hi"):
        self.text = text

    async def astream(self, *args, **kwargs):
        yield (), "messages", (AIMessageChunk(content=self.text), {})


def _client(**kwargs):
    kwargs.setdefault("graph", ToyGraph())
    return TestClient(create_app(**kwargs))


def test_thread_crud_lifecycle():
    client = _client()
    assert client.get("/threads").json() == []

    created = client.post(
        "/threads", json={"localId": "t1", "title": "First"}
    ).json()
    assert created["id"] == "t1"

    # idempotent re-register returns existing
    again = client.post("/threads", json={"localId": "t1"}).json()
    assert again["id"] == "t1"

    assert client.get("/threads/t1").json()["title"] == "First"
    renamed = client.patch("/threads/t1", json={"title": "Renamed"}).json()
    assert renamed["title"] == "Renamed"
    assert client.patch("/threads/t1", json={"title": "  "}).status_code == 400

    client.post("/threads/t1/archive")
    assert client.get("/threads").json() == []
    assert len(client.get("/threads", params={"include_archived": True}).json()) == 1
    client.post("/threads/t1/unarchive")
    assert len(client.get("/threads").json()) == 1

    assert client.get("/threads/missing").status_code == 404
    assert client.delete("/threads/t1").json() == {"ok": True}
    assert client.delete("/threads/t1").status_code == 404


def test_thread_messages_persist_and_clear_on_delete():
    client = _client()
    client.post("/threads", json={"localId": "t1"})
    assert client.get("/threads/t1/messages").json() == {"messages": []}
    msg = {"id": "m1", "role": "user", "parts": [{"type": "text", "text": "hi"}]}
    assert client.post("/threads/t1/messages", json={"message": msg}).json() == {
        "ok": True
    }
    assert client.get("/threads/t1/messages").json() == {"messages": [msg]}

    client.delete("/threads/t1")
    client.post("/threads", json={"localId": "t1"})
    assert client.get("/threads/t1/messages").json() == {"messages": []}


def test_message_feedback_is_owned_idempotent_and_retractable():
    client = _client()
    headers = {"x-agent-chat-subject": "feedback-owner"}
    client.post("/threads", json={"localId": "t1"}, headers=headers)
    client.post(
        "/threads/t1/messages",
        json={"message": {"id": "m1", "role": "assistant", "content": []}},
        headers=headers,
    )
    body = {"rating": "positive", "comment": "Useful", "metadata": {"ui": True}}
    first = client.put("/threads/t1/messages/m1/feedback", json=body, headers=headers)
    assert first.status_code == 200
    retry = client.put("/threads/t1/messages/m1/feedback", json=body, headers=headers)
    assert retry.json()["id"] == first.json()["id"]
    changed = client.put(
        "/threads/t1/messages/m1/feedback",
        json={"rating": "negative"},
        headers=headers,
    )
    assert changed.json()["rating"] == "negative"
    assert client.get("/threads/t1/messages/m1/feedback", headers=headers).status_code == 200
    assert client.get(
        "/threads/t1/messages/m1/feedback",
        headers={"x-agent-chat-subject": "other"},
    ).status_code == 403
    assert client.delete("/threads/t1/messages/m1/feedback", headers=headers).json() == {"ok": True}
    assert client.get("/threads/t1/messages/m1/feedback", headers=headers).status_code == 404

def test_checkpointer_fallback_for_thread_messages():
    class StatefulGraph(ToyGraph):
        def get_state(self, config):
            m = AIMessage(content="from-checkpointer")
            return type("S", (), {"values": {"messages": [m]}})()

    client = TestClient(create_app(graph=StatefulGraph()))
    assert client.get("/threads/any/messages").json()["messages"][0][
        "content"
    ] == "from-checkpointer"


def test_scoped_assistant_auto_creates_thread_and_streams():
    client = _client()
    response = client.post(
        "/assistant",
        json={
            "thread_id": "t-new",
            "user_id": "default_user",
            "state": {"thread_id": "t-new"},
            "commands": [],
        },
    )
    assert response.status_code == 200
    assert client.get("/threads/t-new").json()["id"] == "t-new"


def test_per_agent_scoped_route():
    client = TestClient(
        create_app(agents={"calc": lambda: ToyGraph("calc hi")})
    )
    response = client.post(
        "/assistant/calc",
        json={"thread_id": "t-calc", "state": {}, "commands": []},
    )
    assert response.status_code == 200
    assert client.get("/threads/t-calc").json()["id"] == "t-calc"


def test_checkpointer_backed_demo_graph_keeps_history():
    class Bindable(GenericFakeChatModel):
        def bind_tools(self, *args, **kwargs):
            return self

    checkpointer = MemorySaver()
    graph = make_calculator_agent(
        Bindable(messages=iter([AIMessage(content="r1"), AIMessage(content="r2")])),
        checkpointer=checkpointer,
    )
    config = {"configurable": {"thread_id": "t-hist"}}
    graph.invoke({"messages": [{"role": "user", "content": "2+2"}]}, config)
    state = graph.get_state(config)
    assert state.values["messages"]
    second = graph.invoke({"messages": [{"role": "user", "content": "3+3"}]}, config)
    assert len(second["messages"]) > 2  # history carried by the checkpointer


def test_thread_manager_unit():
    manager = ThreadManager()
    store = ThreadMessageStore()
    manager.create_thread("u1", thread_id="t1")
    assert manager.list_user_threads("u1")[0].id == "t1"
    manager.archive("t1")
    assert manager.list_user_threads("u1") == []
    manager.unarchive("t1")
    manager.update_title("t1", "Hi")
    assert manager.get("t1").title == "Hi"
    store.append("t1", {"a": 1})
    assert store.list("t1") == [{"a": 1}]
    store.drop("t1")
    manager.delete("t1")
    assert manager.get("t1") is None
