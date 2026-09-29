"""Shared helpers for building provider-agnostic tool agents (#12)."""

from typing import Annotated, Any, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from ..models import ModelConfig, resolve_model


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def resolve_llm(model: str | ModelConfig | BaseChatModel) -> BaseChatModel:
    """Resolve a model spec or instance to a chat model.

    Accepts legacy specs, :class:`~agent_chat_minimal.models.ModelConfig`, or
    an already-instantiated ``BaseChatModel`` (e.g. a fake in tests).
    """
    return resolve_model(model)


def make_tool_agent(
    model: str | ModelConfig | BaseChatModel,
    tools: list,
    system_prompt: str | None = None,
    checkpointer: Any | None = None,
) -> StateGraph:
    """Build a compiled ``agent <-> tools`` graph for any tool list.

    Args:
        model: ``provider:name`` spec (see :mod:`docs/providers`) or a chat
            model instance.
        tools: LangChain tools bound to the model and served by a ``ToolNode``.
        system_prompt: Optional system message prepended at invoke time.
        checkpointer: Optional LangGraph checkpointer (e.g. ``MemorySaver()``).
            Compiling with one enables per-``thread_id`` persistence: pass
            ``config={"configurable": {"thread_id": ...}}`` at invoke time.
    """
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
    return workflow.compile(checkpointer=checkpointer)
