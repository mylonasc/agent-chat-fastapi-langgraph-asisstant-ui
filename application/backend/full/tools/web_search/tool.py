import asyncio
import json
import logging
from typing import Any, cast

import requests
from fastapi import APIRouter
from langchain_core.callbacks.manager import adispatch_custom_event
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from tools.config import CONFIG_STORE
from tools.web_rag.background_jobs import INDEXING_MANAGER
from tools.web_rag.retrieval_manager import RETRIEVAL_MANAGER

from .service import SerperSearchService


logger = logging.getLogger(__name__)


class WebSearchArgs(BaseModel):
    query: str = Field(description="Search query to run on the web.")
    max_results: int = Field(default=5, ge=1, le=10)
    as_documents: bool = Field(
        default=True,
        description="Include compact document objects from search results.",
    )
    as_rag_chunks: bool = Field(
        default=False,
        description="Also index top result URLs and return retrieved RAG chunks.",
    )
    auto_index: bool = Field(
        default=True,
        description=(
            "Automatically index top search result URLs into web_rag store, "
            "even when as_rag_chunks is false."
        ),
    )
    user_id: str = Field(default="default_user", description="RAG user namespace.")
    rag_urls_to_index: int = Field(default=2, ge=1, le=5)
    rag_k: int = Field(default=5, ge=1, le=20)
    wait_for_indexing: bool = Field(
        default=True,
        description=(
            "If true, poll the background indexing job and stream progress updates "
            "until completion or timeout."
        ),
    )
    indexing_wait_timeout_s: int = Field(default=20, ge=1, le=120)
    indexing_poll_interval_s: float = Field(default=1.0, ge=0.2, le=5.0)


class WebSearchTool:
    name = "web_search"

    def __init__(self):
        self.router = APIRouter(prefix="/tools/web_search")
        self._register_routes()

    @staticmethod
    def _get_search_config() -> dict:
        return CONFIG_STORE.get("web_search")

    @staticmethod
    def _get_rag_config() -> dict:
        return CONFIG_STORE.get("web_rag") or {
            "embedding_provider": "fastembed",
            "pdf_parser": "pypdf",
        }

    async def _search_with_optional_rag(
        self,
        query: str,
        max_results: int = 5,
        as_documents: bool = True,
        as_rag_chunks: bool = False,
        auto_index: bool = True,
        user_id: str = "default_user",
        rag_urls_to_index: int = 2,
        rag_k: int = 5,
        wait_for_indexing: bool = True,
        indexing_wait_timeout_s: int = 20,
        indexing_poll_interval_s: float = 1.0,
        config: RunnableConfig | None = None,
    ) -> str:
        search_cfg = {**self._get_search_config(), "max_results": max_results}

        try:
            await adispatch_custom_event(
                "tool_progress",
                {
                    "tool": self.name,
                    "stage": "search",
                    "status": "started",
                    "query": query,
                },
                config=config,
            )
        except Exception:
            pass

        try:
            service = SerperSearchService(search_cfg)
            results = await asyncio.to_thread(service.search, query)
        except RuntimeError as e:
            logger.warning("web_search unavailable: %s", e)
            return json.dumps(
                {
                    "status": "error",
                    "error": str(e),
                    "hint": "Set SERPER_API_KEY in backend environment.",
                },
                ensure_ascii=True,
            )
        except requests.RequestException as e:
            logger.exception("web_search request failed")
            return json.dumps(
                {"status": "error", "error": f"SERPER request failed: {e}"},
                ensure_ascii=True,
            )

        response: dict = {"status": "ok", "query": query, "results": results}

        if as_documents:
            response["documents"] = [
                {
                    "title": r.get("title"),
                    "snippet": str(r.get("snippet", ""))[:260],
                    "url": r.get("link"),
                }
                for r in results
            ]

        try:
            await adispatch_custom_event(
                "tool_progress",
                {
                    "tool": self.name,
                    "stage": "search",
                    "status": "completed",
                    "results": len(results),
                },
                config=config,
            )
        except Exception:
            pass

        if auto_index or as_rag_chunks:
            rag_config = self._get_rag_config()
            links = [cast(str, r.get("link")) for r in results if r.get("link")]
            selected_links = links[:rag_urls_to_index]

            job_id = INDEXING_MANAGER.start_job(rag_config, user_id, selected_links)

            try:
                await adispatch_custom_event(
                    "tool_progress",
                    {
                        "tool": self.name,
                        "stage": "rag_index",
                        "status": "queued",
                        "job_id": job_id,
                        "total": len(selected_links),
                        "sources": [
                            {"url": u, "status": "queued"} for u in selected_links
                        ],
                    },
                    config=config,
                )
            except Exception:
                pass

            indexing_payload = {
                "indexer_tool": "web_rag",
                "parser": {
                    "pdf_parser": rag_config.get("pdf_parser", "pypdf"),
                    "docling_device": rag_config.get("docling_device", "cpu"),
                },
                "job_id": job_id,
                "queued_urls": len(selected_links),
                "sources": [{"url": u, "status": "queued"} for u in selected_links],
                "status_endpoint": f"/tools/web_rag/jobs/{job_id}",
            }

            if wait_for_indexing:
                final_job = await self._wait_for_indexing_job(
                    job_id=job_id,
                    timeout_s=indexing_wait_timeout_s,
                    poll_interval_s=indexing_poll_interval_s,
                    config=config,
                )
                if final_job:
                    indexing_payload["status"] = final_job.get("status")
                    indexing_payload["completed_urls"] = final_job.get(
                        "completed_urls", 0
                    )
                    indexing_payload["failed_urls"] = final_job.get("failed_urls", 0)
                    indexing_payload["total_urls"] = final_job.get("total_urls", 0)
                    indexing_payload["sources"] = final_job.get("items", [])

            if as_rag_chunks:
                try:
                    retriever = await asyncio.to_thread(
                        RETRIEVAL_MANAGER.get_retriever,
                        rag_config,
                        user_id,
                        rag_k,
                    )
                    rag_docs = await asyncio.to_thread(
                        cast(Any, retriever).invoke, query
                    )
                    response["rag"] = {
                        "indexing": indexing_payload,
                        "chunks": [d.page_content for d in rag_docs],
                        "sources": [
                            d.metadata.get("source") for d in rag_docs if d.metadata
                        ],
                    }
                except Exception as e:
                    response["rag"] = {
                        "indexing": indexing_payload,
                        "error": str(e),
                    }
            else:
                response["indexing"] = indexing_payload

        ordered: dict[str, Any] = {
            "status": response.get("status"),
            "query": response.get("query"),
        }
        if "indexing" in response:
            ordered["indexing"] = response["indexing"]
        if "rag" in response:
            ordered["rag"] = response["rag"]
        if "results" in response:
            ordered["results"] = response["results"]
        if "documents" in response:
            ordered["documents"] = response["documents"]
        if "error" in response:
            ordered["error"] = response["error"]

        return json.dumps(ordered, ensure_ascii=True)

    async def _wait_for_indexing_job(
        self,
        job_id: str,
        timeout_s: int,
        poll_interval_s: float,
        config: RunnableConfig | None,
    ) -> dict | None:
        deadline = asyncio.get_running_loop().time() + timeout_s
        last_signature: tuple | None = None

        while asyncio.get_running_loop().time() < deadline:
            job = INDEXING_MANAGER.get_job(job_id)
            if not job:
                return None

            signature = (
                job.get("status"),
                job.get("completed_urls"),
                job.get("failed_urls"),
                job.get("total_urls"),
                tuple(
                    (it.get("url"), it.get("status"), it.get("stage"))
                    for it in (job.get("items") or [])
                ),
            )
            if signature != last_signature:
                last_signature = signature
                try:
                    await adispatch_custom_event(
                        "tool_progress",
                        {
                            "tool": self.name,
                            "stage": "rag_index",
                            "status": job.get("status"),
                            "job_id": job_id,
                            "completed_urls": job.get("completed_urls", 0),
                            "failed_urls": job.get("failed_urls", 0),
                            "total_urls": job.get("total_urls", 0),
                            "sources": job.get("items", []),
                        },
                        config=config,
                    )
                except Exception:
                    pass

            if job.get("status") in {"completed", "completed_with_errors"}:
                return job

            await asyncio.sleep(poll_interval_s)

        return INDEXING_MANAGER.get_job(job_id)

    def _register_routes(self):
        @self.router.get("/configuration")
        def get_config():
            return CONFIG_STORE.get(self.name)

        @self.router.post("/configuration")
        def set_config(config: dict):
            CONFIG_STORE.set(self.name, config)
            return {"status": "ok"}

        @self.router.post("/tools")
        async def execute(payload: dict):
            query = payload.get("query")
            if not query:
                return {"error": "query is required"}

            max_results = int(payload.get("max_results", 5))
            cfg = {**self._get_search_config(), "max_results": max_results}
            try:
                service = SerperSearchService(cfg)
                results = await asyncio.to_thread(service.search, query)
                return {"status": "ok", "results": results}
            except RuntimeError as e:
                return {
                    "status": "error",
                    "error": str(e),
                    "hint": "Set SERPER_API_KEY in backend environment.",
                }
            except requests.RequestException as e:
                return {"status": "error", "error": f"SERPER request failed: {e}"}

    def get_router(self):
        return self.router

    def get_langchain_tool(self):
        async def arun(
            query: str,
            max_results: int = 5,
            as_documents: bool = True,
            as_rag_chunks: bool = False,
            auto_index: bool = True,
            user_id: str = "default_user",
            rag_urls_to_index: int = 2,
            rag_k: int = 5,
            wait_for_indexing: bool = True,
            indexing_wait_timeout_s: int = 20,
            indexing_poll_interval_s: float = 1.0,
            config: RunnableConfig | None = None,
        ) -> str:
            return await self._search_with_optional_rag(
                query=query,
                max_results=max_results,
                as_documents=as_documents,
                as_rag_chunks=as_rag_chunks,
                auto_index=auto_index,
                user_id=user_id,
                rag_urls_to_index=rag_urls_to_index,
                rag_k=rag_k,
                wait_for_indexing=wait_for_indexing,
                indexing_wait_timeout_s=indexing_wait_timeout_s,
                indexing_poll_interval_s=indexing_poll_interval_s,
                config=config,
            )

        def run(
            query: str,
            max_results: int = 5,
            as_documents: bool = True,
            as_rag_chunks: bool = False,
            auto_index: bool = True,
            user_id: str = "default_user",
            rag_urls_to_index: int = 2,
            rag_k: int = 5,
            wait_for_indexing: bool = True,
            indexing_wait_timeout_s: int = 20,
            indexing_poll_interval_s: float = 1.0,
        ) -> str:
            return asyncio.run(
                self._search_with_optional_rag(
                    query=query,
                    max_results=max_results,
                    as_documents=as_documents,
                    as_rag_chunks=as_rag_chunks,
                    auto_index=auto_index,
                    user_id=user_id,
                    rag_urls_to_index=rag_urls_to_index,
                    rag_k=rag_k,
                    wait_for_indexing=wait_for_indexing,
                    indexing_wait_timeout_s=indexing_wait_timeout_s,
                    indexing_poll_interval_s=indexing_poll_interval_s,
                )
            )

        return StructuredTool.from_function(
            func=run,
            coroutine=arun,
            name="web_search",
            description=(
                "Search the web and return document-style results. "
                "By default it also indexes top URLs into web_rag store; "
                "set as_rag_chunks=true to include retrieved chunks in the same call. "
                "It proactively streams indexing progress and waits for completion by default. "
                "When reporting to the user, call web_rag_status with the same user_id."
            ),
            args_schema=WebSearchArgs,
        )
