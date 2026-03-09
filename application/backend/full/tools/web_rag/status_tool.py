import asyncio
import json

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from tools.config import CONFIG_STORE

from .background_jobs import INDEXING_MANAGER
from .status import get_index_status


class WebRAGStatusArgs(BaseModel):
    user_id: str = Field(default="default_user", description="RAG user namespace.")


class WebRAGStatusTool:
    name = "web_rag_status"

    @staticmethod
    def _get_config() -> dict:
        return CONFIG_STORE.get("web_rag") or {"embedding_provider": "fastembed"}

    async def _status_async(
        self,
        user_id: str = "default_user",
        config: RunnableConfig | None = None,
    ) -> str:
        rag_cfg = self._get_config()
        index = await asyncio.to_thread(get_index_status, rag_cfg, user_id)
        jobs = await asyncio.to_thread(
            INDEXING_MANAGER.list_jobs, user_id=user_id, limit=10
        )
        payload = {
            "indexer_tool": "web_rag",
            "parser": {
                "pdf_parser": rag_cfg.get("pdf_parser", "pypdf"),
                "docling_device": rag_cfg.get("docling_device", "cpu"),
            },
            "index": index,
            "jobs": jobs,
        }
        return json.dumps(payload, ensure_ascii=True)

    def get_langchain_tool(self):
        async def arun(
            user_id: str = "default_user",
            config: RunnableConfig | None = None,
        ) -> str:
            return await self._status_async(user_id=user_id, config=config)

        def run(user_id: str = "default_user") -> str:
            return asyncio.run(self._status_async(user_id=user_id))

        return StructuredTool.from_function(
            func=run,
            coroutine=arun,
            name=self.name,
            description=(
                "Inspect web RAG index/job status for a user. "
                "Use this to inform the user about indexing progress and readiness."
            ),
            args_schema=WebRAGStatusArgs,
        )
