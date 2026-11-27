"""Resolve tool factories once per turn; every closure owns an immutable policy."""

import hashlib

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool


def build_tools(snapshot, principal, data_path):
    active = snapshot["enabled_tools"]
    result = []
    for name, configuration in active.items():
        if name in {"add", "subtract", "multiply", "divide"}:
            from ..demo_agent import calculator

            original = getattr(calculator, name)
        elif name == "get_weather":
            from ..demo_agent.get_graph import get_weather

            original = get_weather
        elif name == "render_graph":
            from ..demo_agent.tools.graph_tool import render_graph

            original = render_graph
        else:
            # Optional integration is imported only when selected for this turn.
            if name == "web_search":
                from ..web_tools.web_search.tool import WebSearchTool

                original = WebSearchTool().get_langchain_tool()
            elif name == "web_rag":
                from ..web_tools.web_rag.tool import WebRAGTool

                original = WebRAGTool().get_langchain_tool()
            elif name == "web_rag_status":
                from ..web_tools.web_rag.status_tool import WebRAGStatusTool

                original = WebRAGStatusTool().get_langchain_tool()
            else:
                raise ValueError(f"No factory registered for tool {name}")
        result.append(
            _configured(original, configuration, active, principal, data_path)
        )
    return result


def _configured(original, settings, active, principal, data_path):
    name = original.name

    async def invoke(config: RunnableConfig, **arguments):
        if (
            name == "render_graph"
            and len(arguments.get("nodes", [])) > settings["max_nodes"]
        ):
            raise ValueError(
                f"Graph exceeds the configured limit of {settings['max_nodes']} nodes"
            )
        if name.startswith("web_"):
            from ..web_tools.config import tool_configuration

            namespace = hashlib.sha256(principal.subject.encode()).hexdigest()
            arguments["user_id"] = namespace
            if name == "web_search":
                arguments.update(settings)
                arguments["auto_index"] = settings["auto_index"] and "web_rag" in active
                # The model cannot bypass a disabled RAG tool via this argument.
                arguments["as_rag_chunks"] = (
                    arguments.get("as_rag_chunks", False) and "web_rag" in active
                )
            elif name == "web_rag":
                arguments["k"] = settings["k"]
                arguments["auto_bootstrap_web"] = (
                    settings["auto_bootstrap_web"] and "web_search" in active
                )
            rag_config = {**active.get("web_rag", {}), "base_path": data_path}
            with tool_configuration(
                {"web_rag": rag_config, "web_search": active.get("web_search", {})}
            ):
                return await original.ainvoke(arguments, config=config)
        value = await original.ainvoke(arguments, config=config)
        if name in {"add", "subtract", "multiply", "divide"}:
            return round(value, settings["precision"])
        if name == "get_weather" and settings["units"] == "fahrenheit":
            value = value.replace("15°C", "59°F").replace("25°C", "77°F")
        return value

    return StructuredTool.from_function(
        coroutine=invoke,
        name=name,
        description=original.description,
        args_schema=original.args_schema,
    )
