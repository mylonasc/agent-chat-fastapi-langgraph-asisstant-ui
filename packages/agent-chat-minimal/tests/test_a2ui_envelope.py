"""Envelope contract tests for the A2UI demo tools."""

from agent_chat_minimal.demo_agent.tools.a2ui import (
    build_demo_card_envelope,
    build_network_envelope,
    extract_a2ui_messages,
    is_a2ui_envelope,
    make_surface_id,
)


def test_demo_card_envelope_is_valid_v09():
    env = build_demo_card_envelope()
    assert is_a2ui_envelope(env)
    kinds = {k for m in env["messages"] for k in m if k != "version"}
    assert {"createSurface", "updateComponents", "updateDataModel"} <= kinds


def test_network_envelope_uses_custom_component():
    env = build_network_envelope(
        [{"id": "a"}, {"id": "b"}], [{"source": "a", "target": "b"}]
    )
    assert is_a2ui_envelope(env)
    components = env["messages"][1]["updateComponents"]["components"]
    graph = next(c for c in components if c["id"] == "graph")
    assert graph["component"] == "NetworkGraph"
    assert graph["nodes"] == [
        {"id": "a", "label": "a"},
        {"id": "b", "label": "b"},
    ]


def test_extract_handles_json_string_and_rejects_junk():
    env = build_demo_card_envelope()
    import json

    assert extract_a2ui_messages(json.dumps(env)) == env["messages"]
    assert extract_a2ui_messages({"messages": []}) is None
    assert extract_a2ui_messages("not json") is None
    assert not is_a2ui_envelope({"messages": [{"version": "v1.0"}]})


def test_surface_ids_are_safe():
    assert make_surface_id("a b/c") == "a-b-c"
    assert make_surface_id("") == "surface"
