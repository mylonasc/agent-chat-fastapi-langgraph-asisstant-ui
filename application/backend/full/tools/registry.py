from .web_rag.tool import WebRAGTool
from .web_rag.status_tool import WebRAGStatusTool
from .web_search.tool import WebSearchTool


class ToolRegistry:
    def __init__(self):
        self.tools = {
            "web_rag": WebRAGTool(),
            "web_rag_status": WebRAGStatusTool(),
            "web_search": WebSearchTool(),
        }

    def get_routers(self):
        return [t.get_router() for t in self.tools.values() if hasattr(t, "get_router")]

    def get_langchain_tools(self, names=None):
        if names:
            return [self.tools[n].get_langchain_tool() for n in names]
        return [t.get_langchain_tool() for t in self.tools.values()]


TOOL_REGISTRY = ToolRegistry()
