import os
from typing import Annotated, TypedDict
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

# 1. Define the State
class AgentState(TypedDict):
    # add_messages ensures new messages are appended to history rather than overwriting it
    messages: Annotated[list[BaseMessage], add_messages]

# 2. Define Tools
@tool
def get_weather(city: str):
    """Use this to look up the weather for a specific city."""
    if "london" in city.lower():
        return "It's 15°C and cloudy in London."
    return f"The weather in {city} is sunny and 25°C."

def make_agent_with_weather_tool(model = 'gpt-4o-mini') -> StateGraph:

    tools = [get_weather]
    tool_node = ToolNode(tools)

    # 3. Define the Model
    # Replace with your API Key or set as environment variable
    model = ChatOpenAI(model="gpt-4o-mini", streaming=True).bind_tools(tools)

    # 4. Define Logic Functions
    def call_model(state: AgentState):
        
        response = model.invoke(state["messages"])
        state['messages'].append(response)
        
        return {"messages": [response]}

    # 5. Build the Graph
    workflow = StateGraph(AgentState)

    # Add Nodes
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", tool_node)

    # Set Entry Point
    workflow.set_entry_point("agent")

    # Add Conditional Edges
    # This logic determines if the model wants to call a tool or finish
    workflow.add_conditional_edges(
        "agent",
        tools_condition,
    )

    # Link tools back to the agent to process tool results
    workflow.add_edge("tools", "agent")

    # Compile
    app = workflow.compile()
    return app