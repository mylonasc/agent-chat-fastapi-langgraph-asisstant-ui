from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from .tools.graph_tool import render_graph
from .tools.weather_tool import get_weather


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def make_agent_with_weather_tool(model="gpt-4o-mini") -> StateGraph:
    tools = [get_weather, render_graph]
    tool_node = ToolNode(tools)
    chat_model = ChatOpenAI(model="gpt-4o-mini", streaming=True).bind_tools(tools)

    def call_model(state: AgentState):
        response = chat_model.invoke(state["messages"])
        state["messages"].append(response)
        return {"messages": [response]}

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", tool_node)
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", tools_condition)
    workflow.add_edge("tools", "agent")
    return workflow.compile()
