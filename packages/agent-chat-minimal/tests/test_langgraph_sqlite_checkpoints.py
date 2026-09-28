import asyncio
import operator
from contextlib import asynccontextmanager
from typing import Annotated, TypedDict

import pytest
from langgraph.graph import END, START, StateGraph

from agent_chat_minimal.adapters.langgraph_sqlite import (
    LangGraphSQLiteCheckpoints,
)

from checkpoint_contract import TemporaryCheckpointAdapterContract


class TestLangGraphSQLiteCheckpointContract(TemporaryCheckpointAdapterContract):
    adapter_type = LangGraphSQLiteCheckpoints


class TurnState(TypedDict):
    turns: Annotated[list[str], operator.add]


def _graph(checkpointer):
    builder = StateGraph(TurnState)
    builder.add_node("record", lambda state: {})
    builder.add_edge(START, "record")
    builder.add_edge("record", END)
    return builder.compile(checkpointer=checkpointer)


def test_multiturn_graph_state_survives_server_equivalent_restart(tmp_path):
    async def scenario():
        path = tmp_path / "checkpoints.db"
        config = {"configurable": {"thread_id": "stable-session"}}

        first = await LangGraphSQLiteCheckpoints.open(f"sqlite+aiosqlite:///{path}")
        try:
            graph = _graph(first.checkpointer)
            assert (await graph.ainvoke({"turns": ["one"]}, config))["turns"] == [
                "one"
            ]
            assert (await graph.ainvoke({"turns": ["two"]}, config))["turns"] == [
                "one",
                "two",
            ]
        finally:
            await first.dispose()

        second = await LangGraphSQLiteCheckpoints.open(path)
        try:
            restarted_graph = _graph(second.checkpointer)
            result = await restarted_graph.ainvoke({"turns": ["three"]}, config)
            assert result["turns"] == ["one", "two", "three"]
        finally:
            await second.dispose()

    asyncio.run(scenario())


def test_open_failure_closes_connection(monkeypatch):
    closed = []

    class FailingSaver:
        async def setup(self):
            raise RuntimeError("setup failed")

    @asynccontextmanager
    async def failing_context(database):
        try:
            yield FailingSaver()
        finally:
            closed.append(database)

    monkeypatch.setattr(
        "agent_chat_minimal.adapters.langgraph_sqlite.AsyncSqliteSaver.from_conn_string",
        failing_context,
    )

    async def scenario():
        with pytest.raises(RuntimeError, match="setup failed"):
            await LangGraphSQLiteCheckpoints.open("failed.db")

    asyncio.run(scenario())
    assert len(closed) == 1


def test_dispose_is_idempotent_and_blocks_use(tmp_path):
    async def scenario():
        adapter = await LangGraphSQLiteCheckpoints.open(tmp_path / "checkpoints.db")
        await adapter.dispose()
        await adapter.dispose()
        with pytest.raises(RuntimeError, match="disposed"):
            _ = adapter.checkpointer
        with pytest.raises(RuntimeError, match="disposed"):
            await adapter.delete_session("session")

    asyncio.run(scenario())


def test_delete_rejects_unvalidated_session_id(tmp_path):
    async def scenario():
        adapter = await LangGraphSQLiteCheckpoints.open(tmp_path / "checkpoints.db")
        try:
            with pytest.raises(ValueError, match="session id"):
                await adapter.delete_session("  ")
        finally:
            await adapter.dispose()

    asyncio.run(scenario())


def test_in_memory_connection_string_is_preserved():
    async def scenario():
        adapter = await LangGraphSQLiteCheckpoints.open(":memory:")
        try:
            assert adapter.checkpointer is not None
        finally:
            await adapter.dispose()

    asyncio.run(scenario())
