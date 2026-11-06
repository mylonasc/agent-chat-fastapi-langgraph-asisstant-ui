"""Assert model-facing history, not just transport input, for issue #72."""

import asyncio
import uuid
from typing import TypedDict

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph

from agent_chat_minimal import Settings
from agent_chat_minimal.composition import create_configured_app
from agent_chat_minimal.demo_agent.agent_factory import AgentState
from agent_chat_minimal.graph_history import authoritative_graph_input


def _request(client, history, text=None, *, snapshot=True):
    commands = (
        []
        if text is None
        else [
            {
                "type": "add-message",
                "message": {"role": "user", "parts": [{"type": "text", "text": text}]},
            }
        ]
    )
    state = {"thread_id": "branch-history"}
    if snapshot:
        state["messages"] = history
    response = client.post(
        "/assistant",
        json={
            "state": state,
            "commands": commands,
        },
    )
    assert response.status_code == 200, response.text
    assert "answer-" in response.text, response.text


def _contents(messages):
    return [(message["type"], message["content"]) for message in messages]


def _store_branch(client, history, start=0):
    """Persist the same parent links as the full UI transcript synchronizer."""
    for index, message in enumerate(history[start:], start=start):
        payload = {
            "id": message["id"],
            "role": "user" if message["type"] == "human" else "assistant",
            "content": [{"type": "text", "text": message["content"]}],
            "metadata": {
                "custom": {
                    "branchParentId": history[index - 1]["id"] if index else None,
                    "graphMessages": [message],
                }
            },
        }
        response = client.post(
            "/threads/branch-history/messages", json={"message": payload}
        )
        assert response.status_code == 200, response.text


def _restore_branch(rows, head_id):
    by_id = {row["id"]: row for row in rows}
    history = []
    while head_id is not None:
        row = by_id[head_id]
        history[0:0] = row["metadata"]["custom"]["graphMessages"]
        head_id = row["metadata"]["custom"]["branchParentId"]
    return history


@pytest.mark.parametrize("durable", [False, True], ids=["memory", "sqlite"])
@pytest.mark.parametrize("edit_index", [0, 1, 2], ids=["first", "middle", "latest"])
def test_selected_branch_is_authoritative_at_model_input(tmp_path, durable, edit_index):
    seen = []
    answers = []

    def make_graph(checkpointer=None):
        async def answer(state):
            # The recording boundary stands in for the model. LangGraph has
            # already loaded its checkpoint and applied its message reducer.
            seen.append([message.model_dump() for message in state["messages"]])
            result = AIMessage(
                content=f"answer-{uuid.uuid4().hex}", id=f"ai-{uuid.uuid4().hex}"
            )
            answers.append(result.model_dump())
            return {"messages": [result]}

        builder = StateGraph(AgentState)
        builder.add_node("model", answer)
        builder.add_edge(START, "model")
        builder.add_edge("model", END)
        return builder.compile(checkpointer=checkpointer)

    settings = Settings(
        persistence_enabled=durable,
        database_path=str(tmp_path / "app.db"),
        checkpoint_database_path=str(tmp_path / "checkpoints.db"),
    )

    def app():
        return create_configured_app(settings, graph_factory=make_graph)

    def run(client, history, text=None):
        _request(client, history, text)
        return [*seen[-1], answers[-1]]

    with TestClient(app()) as client:
        original = []
        for text in ["KEEP_FIRST", "ORIGINAL_SECOND", "ABANDONED_THIRD"]:
            original = run(client, original, text)
        _store_branch(client, original)

        prefix = original[: 2 * edit_index]
        edited = run(client, prefix, "REPLACEMENT")
        assert _contents(seen[-1]) == [*_contents(prefix), ("human", "REPLACEMENT")]
        # Omitted assistants and descendants must be absent too, not just users.
        assert seen[-1][:-1] == prefix
        # Only new messages need appending; the original prefix is immutable.
        _store_branch(client, edited, start=2 * edit_index)

        rows = client.get("/threads/branch-history/messages").json()["messages"]

        # Regeneration receives the prompt but not its previous answer.
        run(client, edited[:-1])
        assert seen[-1] == edited[:-1]

        def continue_both(active_client, stored):
            restored_original = _restore_branch(stored, original[-1]["id"])
            restored_edited = _restore_branch(stored, edited[-1]["id"])
            assert restored_original == original
            assert restored_edited == edited
            run(active_client, restored_original, "CONTINUE_ORIGINAL")
            assert _contents(seen[-1]) == [
                *_contents(original),
                ("human", "CONTINUE_ORIGINAL"),
            ]
            run(active_client, restored_edited, "CONTINUE_EDITED")
            assert _contents(seen[-1]) == [
                *_contents(edited),
                ("human", "CONTINUE_EDITED"),
            ]

        continue_both(client, rows)

        # An explicitly empty branch is authoritative too, even with no command.
        run(client, [])
        assert seen[-1] == []

        # Omitting messages is the legacy delta API, distinct from explicit [].
        _request(client, [], "DELTA_ONE", snapshot=False)
        assert [m["content"] for m in seen[-1] if m["type"] == "human"] == ["DELTA_ONE"]
        _request(client, [], "DELTA_TWO", snapshot=False)
        assert [m["content"] for m in seen[-1] if m["type"] == "human"] == [
            "DELTA_ONE",
            "DELTA_TWO",
        ]

    if durable:
        # New app, graph, connections, and checkpoint saver: no process-local
        # branch cache can make the SQLite restart assertions pass.
        with TestClient(app()) as restarted:
            restored = restarted.get("/threads/branch-history/messages").json()[
                "messages"
            ]
            assert restored == rows
            continue_both(restarted, restored)


def test_last_value_messages_and_custom_graph_protocol_keep_plain_lists():
    class PlainState(TypedDict):
        messages: list[dict]

    builder = StateGraph(PlainState)
    builder.add_node("model", lambda state: {})
    builder.add_edge(START, "model")
    builder.add_edge("model", END)
    graph = builder.compile()
    messages = [{"type": "human", "content": "replacement"}]
    assert authoritative_graph_input(graph, messages) == {"messages": messages}
    assert (
        asyncio.run(graph.ainvoke(authoritative_graph_input(graph, messages)))[
            "messages"
        ]
        == messages
    )
    assert authoritative_graph_input(object(), messages) == {"messages": messages}


def test_reconciliation_preserves_other_state_channels_and_checkpoint_snapshots():
    from langgraph.checkpoint.memory import InMemorySaver

    class Stateful(AgentState):
        visits: int

    async def scenario():
        saver = InMemorySaver()
        builder = StateGraph(Stateful)
        builder.add_node("model", lambda state: {"visits": state.get("visits", 0) + 1})
        builder.add_edge(START, "model")
        builder.add_edge("model", END)
        graph = builder.compile(checkpointer=saver)
        config = {"configurable": {"thread_id": "stateful"}}
        await graph.ainvoke(
            authoritative_graph_input(graph, [{"role": "user", "content": "old"}]),
            config,
        )
        original = await graph.aget_state(config)
        result = await graph.ainvoke(
            authoritative_graph_input(graph, [{"role": "user", "content": "new"}]),
            config,
        )
        assert [message.content for message in result["messages"]] == ["new"]
        assert result["visits"] == 2
        old_checkpoint = await graph.aget_state(original.config)
        assert [message.content for message in old_checkpoint.values["messages"]] == [
            "old"
        ]

    asyncio.run(scenario())
