"""Graph-level integration: a2ui tools fire through ToolNode and stay valid."""

import json

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, ToolMessage

from agent_chat_minimal.demo_agent.get_graph import make_agent_with_weather_tool
from agent_chat_minimal.demo_agent.tools.a2ui import (
    extract_a2ui_messages,
    is_a2ui_envelope,
)


class BindableFake(GenericFakeChatModel):
    def bind_tools(self, *args, **kwargs):
        return self


def _tool_call_msg(tool_name, args):
    return AIMessage(
        content="",
        tool_calls=[{"name": tool_name, "args": args, "id": "call-1", "type": "tool_call"}],
    )


def test_render_a2ui_demo_flows_through_graph():
    fake = BindableFake(
        messages=iter(
            [
                _tool_call_msg("render_a2ui_demo", {"title": "T", "body": "B"}),
                AIMessage(content="done"),
            ]
        )
    )
    graph = make_agent_with_weather_tool(fake)
    result = graph.invoke({"messages": [{"role": "user", "content": "show a card"}]})
    tool_msgs = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert tool_msgs, "expected ToolNode to execute render_a2ui_demo"
    payload = tool_msgs[0].content
    envelope = json.loads(payload) if isinstance(payload, str) else payload
    assert is_a2ui_envelope(envelope)
    assert extract_a2ui_messages(payload) is not None


def test_render_network_a2ui_flows_through_graph():
    fake = BindableFake(
        messages=iter(
            [
                _tool_call_msg(
                    "render_network_a2ui",
                    {"nodes": [{"id": "a"}], "edges": [], "directed": False},
                ),
                AIMessage(content="done"),
            ]
        )
    )
    graph = make_agent_with_weather_tool(fake)
    result = graph.invoke({"messages": [{"role": "user", "content": "show a graph"}]})
    tool_msgs = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert tool_msgs, "expected ToolNode to execute render_network_a2ui"
    payload = tool_msgs[0].content
    envelope = json.loads(payload) if isinstance(payload, str) else payload
    assert is_a2ui_envelope(envelope)
    components = envelope["messages"][1]["updateComponents"]["components"]
    assert any(c.get("component") == "NetworkGraph" for c in components)
