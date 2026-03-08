def _make_demo_agent(model_name, checkpointer=None, tool_names=None):
    from langgraph.prebuilt import create_react_agent
    from tools.registry import TOOL_REGISTRY
    import os
    from .rag_graph import build_enforced_rag_graph

    agent_mode = os.getenv("AGENT_MODE", "react")

    if agent_mode == "enforced_rag":
        return build_enforced_rag_graph(
            model_name=model_name,
            checkpointer=checkpointer,
        )

    # Default: ReAct tool-based agent
    tools = TOOL_REGISTRY.get_langchain_tools(tool_names)

    agent = create_react_agent(
        model=model_name,
        tools=tools,
        checkpointer=checkpointer,
    )
    return agent
