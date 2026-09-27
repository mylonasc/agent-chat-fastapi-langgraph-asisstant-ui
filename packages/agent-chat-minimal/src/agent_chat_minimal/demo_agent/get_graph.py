from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import tool
from langgraph.graph import StateGraph

from .agent_factory import AgentState, make_tool_agent
from .tools.graph_tool import render_graph


__all__ = ["AgentState", "get_weather", "make_agent_with_weather_tool"]


@tool
def get_weather(city: str):
    """Use this to look up the weather for a specific city."""
    if "london" in city.lower():
        return "It's 15°C and cloudy in London."
    return f"The weather in {city} is sunny and 25°C."


def make_agent_with_weather_tool(
    model: str | BaseChatModel = "openai:gpt-4o-mini",
    checkpointer=None,
) -> StateGraph:
    """Build the weather demo agent for any provider model spec/instance.

    Examples:
        make_agent_with_weather_tool("openai:gpt-4o-mini")  # default
        make_agent_with_weather_tool("anthropic:claude-sonnet-4-5")
        make_agent_with_weather_tool("ollama:llama3.1")
        make_agent_with_weather_tool(GenericFakeChatModel(messages=iter([...])))
    """
    if model == "gpt-4o-mini":  # backward compat: bare legacy default
        model = "openai:gpt-4o-mini"
    tools = [get_weather, render_graph]
    return make_tool_agent(model, tools, checkpointer=checkpointer)
