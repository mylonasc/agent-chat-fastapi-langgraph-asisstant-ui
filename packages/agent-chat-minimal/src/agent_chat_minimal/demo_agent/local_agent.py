"""Local demo agent that answers without any LLM or API key.

The graph below mirrors the shape of the OpenAI demo in
:mod:`agent_chat_minimal.demo_agent.get_graph` (an ``agent`` node, a
``tools`` node, ``messages`` state with :func:`add_messages`), except the
``agent`` node is a small rule-based router instead of a chat model. That
makes the packaged app work out of the box: no ``OPENAI_API_KEY``, no
network calls.

It is also the reference implementation for custom agents: any LangGraph
graph that keeps the same ``messages`` state contract renders in the
bundled UI (see the package README, "Creating a compatible agent").
"""

import re
import uuid
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from .tools.graph_tool import render_graph
from .tools.weather_tool import get_weather

_WEATHER_HINTS = ("weather", "temperature", "forecast", "rain", "sunny", "cloud")
_CITY_RE = re.compile(
    r"weather\s+(?:in|for)\s+([A-Za-z][A-Za-z .'\-]*)|"
    r"temperature\s+(?:in|for)\s+([A-Za-z][A-Za-z .'\-]*)|"
    r"forecast\s+(?:in|for)\s+([A-Za-z][A-Za-z .'\-]*)",
    re.IGNORECASE,
)


class LocalAgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def _last_human_text(state: LocalAgentState) -> str:
    for message in reversed(state["messages"]):
        if isinstance(message, HumanMessage):
            content = message.content
            if isinstance(content, list):
                return " ".join(
                    part.get("text", "")
                    for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                )
            return str(content)
    return ""


def _extract_city(text: str) -> str:
    match = _CITY_RE.search(text)
    if match:
        city = next((group for group in match.groups() if group), "")
        return city.strip().rstrip("?.!") or "London"
    return "London"


def _tool_call(name: str, args: dict) -> dict:
    return {
        "name": name,
        "args": args,
        "id": f"call_{uuid.uuid4().hex[:12]}",
        "type": "tool_call",
    }


def _route(state: LocalAgentState):
    """Decide between a tool call and a direct reply (no LLM involved)."""
    text = _last_human_text(state)
    lowered = text.lower()

    if "graph" in lowered:
        return {
            "messages": [
                AIMessage(
                    content="I'll render a small demo graph for you.",
                    tool_calls=[
                        _tool_call(
                            "render_graph",
                            {
                                "nodes": [
                                    {"id": "london", "label": "London", "weight": 70},
                                    {"id": "paris", "label": "Paris", "weight": 50},
                                    {"id": "berlin", "label": "Berlin", "weight": 30},
                                ],
                                "edges": [
                                    {"source": "london", "target": "paris"},
                                    {"source": "paris", "target": "berlin"},
                                ],
                                "directed": True,
                            },
                        )
                    ],
                )
            ]
        }

    if any(hint in lowered for hint in _WEATHER_HINTS):
        city = _extract_city(text)
        return {
            "messages": [
                AIMessage(
                    content=f"I'll look up the weather in {city}.",
                    tool_calls=[_tool_call("get_weather", {"city": city})],
                )
            ]
        }

    return {
        "messages": [
            AIMessage(
                content=(
                    f'You said: "{text}"\n\n'
                    "I run fully offline, with no API key. "
                    "Ask me about the weather in a city, or ask for a graph "
                    "to see the interactive visualization."
                )
            )
        ]
    }


def _respond(state: LocalAgentState):
    """Turn tool results into a user-facing reply."""
    results = [
        str(message.content)
        for message in state["messages"]
        if message.type == "tool" and str(message.content)
    ]
    if any("°C" in result for result in results):
        summary = " ".join(results)
    else:
        summary = "I've rendered the graph below."
    return {"messages": [AIMessage(content=summary)]}


def make_local_agent():
    """Build the default key-free demo agent."""
    tools = [get_weather, render_graph]
    workflow = StateGraph(LocalAgentState)
    workflow.add_node("agent", _route)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_node("respond", _respond)
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", tools_condition)
    workflow.add_edge("tools", "respond")
    workflow.add_edge("respond", END)
    return workflow.compile()
