"""Policy, authorization, persistence, and actual tool composition without LLMs."""

import asyncio
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from agent_chat_minimal import Settings, create_app
from agent_chat_minimal.composition import create_configured_app
from agent_chat_minimal.demo_agent.agent_factory import AgentState
from agent_chat_minimal.domain import Principal
from agent_chat_minimal.toolkits.api import ToolSettingsUpdate
from agent_chat_minimal.toolkits.engine import build_tools
from agent_chat_minimal.toolkits.manager import ToolkitManager
from agent_chat_minimal.toolkits.store import RevisionConflict
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph

ADMIN = {"Authorization": "Bearer test-admin"}
ALICE = {"x-agent-chat-subject": "alice"}
BOB = {"x-agent-chat-subject": "bob"}


@pytest.fixture
def settings(tmp_path):
    return Settings(
        ui_preset="full",
        toolsets=("calculator", "weather"),
        allowed_toolsets=("calculator", "weather", "graph"),
        tool_settings_path=str(tmp_path / "settings.sqlite3"),
        database_path=str(tmp_path / "chat.db"),
        checkpoint_database_path=str(tmp_path / "checkpoints.db"),
    )


@pytest.fixture(autouse=True)
def admin_token(monkeypatch):
    monkeypatch.setenv("AGENT_CHAT_ADMIN_TOKEN", "test-admin")


def body(snapshot, *, toolsets=None, tools=None):
    return {
        "revision": snapshot["revision"],
        "global_revision": snapshot["global_revision"],
        "toolsets": snapshot["toolsets"] if toolsets is None else toolsets,
        "tools": tools or {},
    }


def create_thread(client, id="thread", headers=ALICE):
    response = client.post("/threads", json={"localId": id}, headers=headers)
    assert response.status_code == 200, response.text


def test_startup_allowlist_and_strict_configuration(settings):
    with pytest.raises(ValueError, match="Unknown toolsets"):
        replace(settings, toolsets=("not-a-toolset",))
    with pytest.raises(ValueError, match="subset"):
        ToolkitManager(replace(settings, allowed_toolsets=("calculator",)))
    with pytest.raises(ValueError, match="Unknown setting"):
        ToolkitManager(
            replace(settings, tool_config={"add": {"api_key": "must-not-store"}})
        )
    with pytest.raises(ValueError, match="between"):
        ToolkitManager(replace(settings, tool_config={"add": {"precision": 99}}))
    with pytest.raises(ValueError, match="opaque"):
        create_app(settings=settings, graph=object())


def test_admin_authorization_and_server_allowlist(settings):
    with TestClient(create_app(settings=settings)) as client:
        snapshot = client.get("/tooling").json()
        assert client.get("/tooling/admin", headers=ALICE).status_code == 403
        assert (
            client.get(
                "/tooling/admin", headers={"x-agent-chat-role": "admin"}
            ).status_code
            == 403
        )
        assert (
            client.put("/tooling/admin", json=body(snapshot), headers=ALICE).status_code
            == 403
        )
        response = client.put(
            "/tooling/admin",
            json=body(snapshot, toolsets=["web_search"]),
            headers=ADMIN,
        )
        assert response.status_code == 422
        response = client.put(
            "/tooling/admin",
            json=body(snapshot, toolsets=["calculator"]),
            headers=ADMIN,
        )
        assert response.status_code == 200
        assert "get_weather" not in response.json()["enabled_tools"]
        assert (
            client.put("/tooling/admin", json=body(snapshot), headers=ADMIN).status_code
            == 409
        )
        assert "test-admin" not in json.dumps(response.json())
        assert "test-admin" not in client.get("/api/config").text


def test_trusted_resolver_can_grant_admin_without_client_token(settings):
    class Resolver:
        async def resolve(self, request):
            return Principal("trusted", claims={"role": "admin"})

    with TestClient(
        create_app(settings=settings, principal_resolver=Resolver())
    ) as client:
        assert client.get("/tooling/admin").status_code == 200


def test_thread_ownership_individual_tools_and_global_revocation(settings):
    with TestClient(create_app(settings=settings)) as client:
        create_thread(client)
        assert client.get("/threads/thread/tools", headers=BOB).status_code == 403
        snapshot = client.get("/threads/thread/tools", headers=ALICE).json()
        response = client.put(
            "/threads/thread/tools",
            headers=ALICE,
            json=body(
                snapshot,
                toolsets=["calculator"],
                tools={
                    "divide": {"enabled": False},
                    "add": {"config": {"precision": 2}},
                },
            ),
        )
        assert response.status_code == 200, response.text
        assert "divide" not in response.json()["enabled_tools"]
        assert response.json()["enabled_tools"]["add"]["precision"] == 2
        assert "get_weather" not in response.json()["enabled_tools"]
        assert (
            client.put(
                "/threads/thread/tools", headers=BOB, json=body(response.json())
            ).status_code
            == 403
        )
        global_state = client.get("/tooling").json()
        assert (
            client.put(
                "/tooling/admin", headers=ADMIN, json=body(global_state, toolsets=[])
            ).status_code
            == 200
        )
        assert (
            client.get("/threads/thread/tools", headers=ALICE).json()["enabled_tools"]
            == {}
        )
        assert client.put(
            "/threads/thread/tools", headers=ALICE, json=body(response.json())
        ).status_code in {409, 422}


def test_settings_and_conversation_choices_survive_restart(settings):
    settings = replace(settings, persistence_enabled=True)
    with TestClient(create_configured_app(settings)) as client:
        create_thread(client)
        global_state = client.get("/tooling").json()
        saved = client.put(
            "/tooling/admin",
            headers=ADMIN,
            json=body(global_state, toolsets=["calculator", "graph"]),
        ).json()
        thread_state = client.get("/threads/thread/tools", headers=ALICE).json()
        response = client.put(
            "/threads/thread/tools",
            headers=ALICE,
            json=body(
                thread_state,
                toolsets=["graph"],
                tools={"render_graph": {"config": {"max_nodes": 25}}},
            ),
        )
        assert response.status_code == 200, response.text
    with TestClient(create_configured_app(settings)) as client:
        assert client.get("/tooling").json()["revision"] == saved["revision"]
        state = client.get("/threads/thread/tools", headers=ALICE).json()
        assert list(state["enabled_tools"]) == ["render_graph"]
        assert state["enabled_tools"]["render_graph"]["max_nodes"] == 25
        assert client.delete("/threads/thread", headers=ALICE).status_code == 200
        create_thread(client)
        assert (
            client.get("/threads/thread/tools", headers=ALICE).json()["revision"] == 0
        )


def test_validation_and_optimistic_concurrency(settings):
    manager = ToolkitManager(settings)
    snapshot = manager.snapshot()
    with pytest.raises(ValueError):
        manager.update(
            ToolSettingsUpdate(
                **body(snapshot, tools={"add": {"config": {"precision": True}}})
            )
        )
    with pytest.raises(ValueError):
        manager.update(
            ToolSettingsUpdate(
                **body(snapshot, tools={"add": {"config": {"secret": "bad"}}})
            )
        )
    changed = manager.update(
        ToolSettingsUpdate(**body(snapshot, tools={"add": {"enabled": False}}))
    )
    with pytest.raises(RevisionConflict):
        manager.update(ToolSettingsUpdate(**body(snapshot)))
    assert changed["revision"] == 1
    assert manager.snapshot()["revision"] == 1


def test_real_basic_tool_knobs_and_empty_toolset(settings):
    manager = ToolkitManager(
        replace(
            settings,
            tool_config={
                "divide": {"precision": 2},
                "get_weather": {"units": "fahrenheit"},
            },
        )
    )
    tools = {
        tool.name: tool
        for tool in build_tools(manager.snapshot(), Principal("alice"), "unused")
    }
    assert asyncio.run(tools["divide"].ainvoke({"a": 1, "b": 3})) == 0.33
    assert "59°F" in asyncio.run(tools["get_weather"].ainvoke({"city": "London"}))
    empty = manager.snapshot()
    empty["enabled_tools"] = {}
    assert build_tools(empty, Principal("alice"), "unused") == []


def test_each_turn_binds_the_current_policy_and_inflight_snapshot_is_stable(
    settings, monkeypatch
):
    started, finish = threading.Event(), threading.Event()
    first = True

    def graph_factory(model, tools, checkpointer=None):
        names = sorted(tool.name for tool in tools)

        async def respond(state):
            nonlocal first
            if first:
                first = False
                started.set()
                await asyncio.to_thread(finish.wait, 10)
            return {"messages": [AIMessage(content="TOOLS=" + ",".join(names))]}

        graph = StateGraph(AgentState)
        graph.add_node("answer", respond)
        graph.add_edge(START, "answer")
        graph.add_edge("answer", END)
        return graph.compile(checkpointer=checkpointer)

    monkeypatch.setattr(
        "agent_chat_minimal.demo_agent.agent_factory.make_tool_agent", graph_factory
    )
    request = {
        "state": {"thread_id": "thread", "messages": []},
        "commands": [
            {
                "type": "add-message",
                "message": {"role": "user", "parts": [{"type": "text", "text": "Hi"}]},
            }
        ],
    }
    with (
        TestClient(create_app(settings=settings)) as client,
        ThreadPoolExecutor() as executor,
    ):
        pending = executor.submit(
            client.post, "/assistant", json=request, headers=ALICE
        )
        try:
            assert started.wait(5)
            state = client.get("/tooling").json()
            assert (
                client.put(
                    "/tooling/admin", headers=ADMIN, json=body(state, toolsets=[])
                ).status_code
                == 200
            )
        finally:
            finish.set()
        first_response = pending.result(timeout=10)
        assert first_response.status_code == 200
        assert "get_weather" in first_response.text
        response = client.post("/assistant", json=request, headers=ALICE)
        assert response.status_code == 200
        assert "get_weather" not in response.text
        assert "TOOLS=" in response.text


def test_startup_only_and_admin_only_fields_are_not_conversation_knobs(
    settings, monkeypatch
):
    monkeypatch.setattr(
        "agent_chat_minimal.toolkits.manager.find_spec", lambda name: True
    )
    manager = ToolkitManager(
        replace(settings, toolsets=("web_search", "web_rag"), allowed_toolsets=None)
    )
    state = manager.snapshot("thread")
    with pytest.raises(ValueError, match="not configurable per conversation"):
        manager.update(
            ToolSettingsUpdate(
                **body(state, tools={"web_search": {"config": {"auto_index": True}}})
            ),
            "thread",
        )
    state = manager.snapshot()
    with pytest.raises(ValueError, match="startup configuration"):
        manager.update(
            ToolSettingsUpdate(
                **body(
                    state,
                    tools={"web_rag": {"config": {"embedding_provider": "openai"}}},
                )
            )
        )


def test_renderer_capabilities_are_independent_of_layout(settings):
    for preset in ("minimal", "full"):
        with TestClient(
            create_app(settings=replace(settings, ui_preset=preset))
        ) as client:
            config = client.get("/api/config").json()
            assert config["ui_preset"] == preset
            assert "render_graph" in config["tooling"]["tool_names"]
            assert config["tools"]["web_rag"]["enabled"] is False


def test_missing_optional_dependencies_fail_at_startup(settings, monkeypatch):
    monkeypatch.setattr(
        "agent_chat_minimal.toolkits.manager.find_spec", lambda name: None
    )
    with pytest.raises(ValueError, match="optional dependencies"):
        ToolkitManager(replace(settings, toolsets=("web_rag",), allowed_toolsets=None))


def test_search_only_does_not_enable_rag_or_trust_a_model_namespace(monkeypatch):
    import hashlib
    import sys

    from agent_chat_minimal.web_tools.web_search.tool import (
        WebSearchArgs,
        WebSearchTool,
    )
    from langchain_core.tools import StructuredTool

    seen = {}

    async def fake_search(**arguments):
        seen.update(arguments)
        return "ok"

    tool = StructuredTool.from_function(
        coroutine=fake_search,
        name="web_search",
        description="test search",
        args_schema=WebSearchArgs,
    )
    monkeypatch.setattr(WebSearchTool, "get_langchain_tool", lambda self: tool)
    modules_before = set(sys.modules)
    snapshot = {
        "enabled_tools": {
            "web_search": {
                "auto_index": True,
                "wait_for_indexing": True,
                "max_results": 3,
            }
        }
    }
    bound = build_tools(snapshot, Principal("trusted-owner"), "unused")[0]
    assert (
        asyncio.run(
            bound.ainvoke(
                {"query": "test", "user_id": "../../other-owner", "as_rag_chunks": True}
            )
        )
        == "ok"
    )
    assert seen["user_id"] == hashlib.sha256(b"trusted-owner").hexdigest()
    assert seen["auto_index"] is False
    assert seen["as_rag_chunks"] is False
    assert seen["max_results"] == 3
    assert "agent_chat_minimal.web_tools.web_rag.indexer" not in (
        set(sys.modules) - modules_before
    )


def test_dormant_individual_preferences_survive_global_revocation(settings):
    manager = ToolkitManager(settings)
    state = manager.snapshot("thread")
    manager.update(
        ToolSettingsUpdate(**body(state, tools={"divide": {"enabled": False}})),
        "thread",
    )
    global_state = manager.snapshot()
    manager.update(
        ToolSettingsUpdate(**body(global_state, tools={"divide": {"enabled": False}}))
    )
    state = manager.snapshot("thread")
    manager.update(
        ToolSettingsUpdate(**body(state, tools={"add": {"config": {"precision": 2}}})),
        "thread",
    )
    global_state = manager.snapshot()
    manager.update(
        ToolSettingsUpdate(**body(global_state, tools={"divide": {"enabled": True}}))
    )
    assert "divide" not in manager.snapshot("thread")["enabled_tools"]


def test_web_configuration_is_task_local_and_propagates_to_worker_threads():
    from agent_chat_minimal.web_tools.config import CONFIG_STORE, tool_configuration

    async def lookup(value):
        with tool_configuration({"web_search": {"max_results": value}}):
            await asyncio.sleep(0)
            return await asyncio.to_thread(CONFIG_STORE.get, "web_search")

    async def run():
        return await asyncio.gather(lookup(2), lookup(9))

    assert asyncio.run(run()) == [{"max_results": 2}, {"max_results": 9}]
    assert CONFIG_STORE.get("web_search") == {}


def test_reduced_baked_allowlist_removes_stale_conversation_selections(settings):
    manager = ToolkitManager(settings)
    state = manager.snapshot("thread")
    manager.update(ToolSettingsUpdate(**body(state)), "thread")
    reduced = ToolkitManager(
        replace(settings, toolsets=("calculator",), allowed_toolsets=("calculator",))
    )
    state = reduced.snapshot("thread")
    assert state["toolsets"] == ["calculator"]
    assert "get_weather" not in state["enabled_tools"]
    # Hidden, formerly permitted choices must not make the editor unsaveable.
    reduced.update(ToolSettingsUpdate(**body(state)), "thread")
