import os

from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from tools.registry import TOOL_REGISTRY
from .rag_graph import build_enforced_rag_graph


def make_web_rag_search_agent(
    model_name: str = "gpt-4o-mini",
    checkpointer=None,
    mode: str | None = None,
):
    """
    Factory constructor for an agent that supports:
    - web_search tool
    - web_rag tool (hybrid RAG)

    Modes:
        - "react" (default): tool-driven ReAct agent
        - "enforced_rag": retrieval-first graph
    """

    if checkpointer is None:
        checkpointer = MemorySaver()

    agent_mode = mode or os.getenv("AGENT_MODE", "react")

    if agent_mode == "enforced_rag":
        return build_enforced_rag_graph(
            model_name=model_name,
            checkpointer=checkpointer,
        )

    # Default: ReAct agent with both tools
    tools = TOOL_REGISTRY.get_langchain_tools(
        names=["web_rag", "web_search", "web_rag_status"]
    )

    return create_react_agent(
        model=model_name,
        tools=tools,
        checkpointer=checkpointer,
    )
