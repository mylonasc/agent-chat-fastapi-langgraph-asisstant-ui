"""Shared helpers for building provider-agnostic tool agents (#12)."""

from typing import Annotated, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def resolve_llm(model: str | BaseChatModel) -> BaseChatModel:
    """Resolve a model spec or instance to a chat model.

    Accepts ``openai:gpt-4o-mini``-style specs (bare ``gpt-4o-mini`` infers
    OpenAI), or an already-instantiated ``BaseChatModel`` (e.g.
    ``GenericFakeChatModel`` in tests). Imported lazily so non-OpenAI
    providers don't require ``langchain-openai``.
    """
    if isinstance(model, BaseChatModel):
        return model
    from langchain.chat_models import init_chat_model

    return init_chat_model(model, streaming=True)


def make_tool_agent(
    model: str | BaseChatModel,
    tools: list,
    system_prompt: str | None = None,
) -> StateGraph:
    """Build a compiled ``agent <-> tools`` graph for any tool list."""
    llm = resolve_llm(model).bind_tools(tools)
    tool_node = ToolNode(tools)

    def call_model(state: AgentState):
        messages = state["messages"]
        if system_prompt:
            messages = [
                {"role": "system", "content": system_prompt},
                *messages,
            ]
        response = llm.invoke(messages)
        return {"messages": [response]}

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", tool_node)
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", tools_condition)
    workflow.add_edge("tools", "agent")
    return workflow.compile()
