"""Shared helpers for building provider-agnostic tool agents (#12)."""

from typing import Annotated, Any, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from ..models import ModelConfig, resolve_model


class ToolsNotSupportedError(RuntimeError):
    """A model rejected the tools bound to a tool agent.

    Tool binding itself is client-side: unsupported models fail only when the
    provider receives the request (e.g. Ollama 400 ``does not support
    tools``), so graph construction and ``--check`` succeed and the failure
    surfaces at invoke time. The original provider error is chained.
    """


_TOOL_SUPPORT_PATTERNS = (
    "does not support tools",
    "do not support tools",
    "tools are not supported",
    "tools not supported",
    "tool calls are not supported",
    "tool calling is not supported",
    "tool calling not supported",
    "does not support function calling",
    "function calling is not supported",
)


def _describe_model(model: str | ModelConfig | BaseChatModel) -> str:
    if isinstance(model, ModelConfig):
        return model.spec
    if isinstance(model, BaseChatModel):
        return type(model).__name__
    return model


def _tools_error_or_original(
    model: str | ModelConfig | BaseChatModel, exc: Exception
) -> Exception:
    """Convert tool-support rejections into an actionable error.

    Only provider errors that actually complain about tool support are
    converted; every other failure is returned unchanged.
    """
    detail = str(exc)
    if not any(pattern in detail.lower() for pattern in _TOOL_SUPPORT_PATTERNS):
        return exc
    return ToolsNotSupportedError(
        f"model {_describe_model(model)!r} does not support tool calling: "
        f"{detail}. Use a tool-capable model for this provider "
        "(e.g. 'ollama:llama3.1' instead of 'ollama:llama3'), "
        "or build the agent without tools."
    )


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
    try:
        llm = resolve_llm(model).bind_tools(tools)
    except Exception as exc:
        converted = _tools_error_or_original(model, exc)
        if converted is exc:
            raise
        raise converted from exc
    tool_node = ToolNode(tools)

    def call_model(state: AgentState):
        messages = state["messages"]
        if system_prompt:
            messages = [
                {"role": "system", "content": system_prompt},
                *messages,
            ]
        try:
            response = llm.invoke(messages)
        except Exception as exc:
            converted = _tools_error_or_original(model, exc)
            if converted is exc:
                raise
            raise converted from exc
        return {"messages": [response]}

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", tool_node)
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", tools_condition)
    workflow.add_edge("tools", "agent")
    return workflow.compile(checkpointer=checkpointer)
