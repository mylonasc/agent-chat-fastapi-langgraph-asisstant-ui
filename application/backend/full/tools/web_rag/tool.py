from fastapi import APIRouter
from langchain_core.tools import Tool
from tools.config import CONFIG_STORE
from .indexer import WebRAGIndexer
from .retrieval_manager import RETRIEVAL_MANAGER


class WebRAGTool:
    name = "web_rag"

    def __init__(self):
        self.router = APIRouter(prefix="/tools/web_rag")
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
            action = payload.get("action")
            user_id = payload.get("user_id", "default_user")
            config = CONFIG_STORE.get(self.name)

            if action == "index":
                indexer = WebRAGIndexer(config, user_id)
                indexer.index_url(payload["url"])
                return {"status": "indexed"}

            if action == "query":
                retriever = RETRIEVAL_MANAGER.get_retriever(
                    config=config,
                    user_id=user_id,
                    k=payload.get("k", 5),
                )
                docs = retriever.invoke(payload["query"])
                return {"results": [d.page_content for d in docs]}

            return {"error": "invalid action"}

    def get_router(self):
        return self.router

    def get_langchain_tool(self):
        def run(query: str, user_id: str = "default_user"):
            config = CONFIG_STORE.get(self.name)
            retriever = RETRIEVAL_MANAGER.get_retriever(
                config=config,
                user_id=user_id,
            )
            docs = retriever.invoke(query)
            return "\n".join([d.page_content for d in docs])

        return Tool(name="web_rag", description="Hybrid local RAG", func=run)
