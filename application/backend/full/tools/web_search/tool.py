from fastapi import APIRouter
from langchain_core.tools import Tool
from tools.config import CONFIG_STORE
from .service import SerperSearchService


class WebSearchTool:
    name = "web_search"

    def __init__(self):
        self.router = APIRouter(prefix="/tools/web_search")
        self._register_routes()

    def _register_routes(self):
        @self.router.get("/configuration")
        def get_config():
            return CONFIG_STORE.get(self.name)

        @self.router.post("/configuration")
        def set_config(config: dict):
            CONFIG_STORE.set(self.name, config)
            return {"status": "ok"}

        @self.router.post("/tools")
        def execute(payload: dict):
            config = CONFIG_STORE.get(self.name)
            service = SerperSearchService(config)
            results = service.search(payload["query"])
            return {"results": results}

    def get_router(self):
        return self.router

    def get_langchain_tool(self):
        def run(query: str):
            config = CONFIG_STORE.get(self.name)
            service = SerperSearchService(config)
            results = service.search(query)
            return "\n".join([r["link"] for r in results])

        return Tool(name="web_search", description="SERPER web search", func=run)
