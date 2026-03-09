import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from langchain_core.callbacks.manager import adispatch_custom_event
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from tools.config import CONFIG_STORE
from tools.web_search.service import SerperSearchService
from .background_jobs import INDEXING_MANAGER
from .indexer import WebRAGIndexer
from .retrieval_manager import RETRIEVAL_MANAGER
from .status import get_index_status


logger = logging.getLogger(__name__)


def _compact_chunks(
    chunks: list[str], max_chunks: int = 8, max_chars: int = 800
) -> list[str]:
    return [str(c)[:max_chars] for c in chunks[:max_chunks]]


class WebRAGArgs(BaseModel):
    query: str = Field(description="Query to run against indexed RAG documents.")
    user_id: str = Field(default="default_user", description="RAG user namespace.")
    k: int = Field(default=5, ge=1, le=20, description="Number of chunks to retrieve.")
    auto_bootstrap_web: bool = Field(
        default=True,
        description=(
            "When index is empty, run a small web search and index top pages before retrying retrieval."
        ),
    )


class WebRAGTool:
    name = "web_rag"

    def __init__(self):
        self.router = APIRouter(prefix="/tools/web_rag")
        self._register_routes()

    @staticmethod
    def _get_config() -> dict:
        return CONFIG_STORE.get("web_rag") or {
            "embedding_provider": "fastembed",
            "pdf_parser": "pypdf",
        }

    async def _query_with_progress(
        self,
        query: str,
        user_id: str = "default_user",
        k: int = 5,
        auto_bootstrap_web: bool = True,
        config: RunnableConfig | None = None,
    ) -> str:
        cfg = self._get_config()
        parser_meta = {
            "pdf_parser": cfg.get("pdf_parser", "pypdf"),
            "docling_device": cfg.get("docling_device", "cpu"),
        }

        try:
            await adispatch_custom_event(
                "tool_progress",
                {"tool": self.name, "stage": "retriever_init", "status": "started"},
                config=config,
            )
        except Exception:
            pass

        try:
            retriever = await asyncio.to_thread(
                RETRIEVAL_MANAGER.get_retriever,
                cfg,
                user_id,
                k,
            )
            docs = await asyncio.to_thread(cast(Any, retriever).invoke, query)

            payload = {
                "status": "ok",
                "indexer_tool": "web_rag",
                "parser": parser_meta,
                "query": query,
                "user_id": user_id,
                "index_status": get_index_status(cfg, user_id),
                "sources": [d.metadata.get("source") for d in docs if d.metadata],
                "chunks": _compact_chunks([d.page_content for d in docs]),
            }

            try:
                await adispatch_custom_event(
                    "tool_progress",
                    {
                        "tool": self.name,
                        "stage": "retrieval",
                        "status": "completed",
                        "chunks": len(payload["chunks"]),
                    },
                    config=config,
                )
            except Exception:
                pass

            return json.dumps(payload, ensure_ascii=True)
        except ValueError as e:
            logger.warning("web_rag unavailable: %s", e)

            if auto_bootstrap_web:
                bootstrap = await self._bootstrap_from_web(
                    query=query,
                    user_id=user_id,
                    config=config,
                )

                if bootstrap.get("indexed_urls", 0) > 0:
                    try:
                        retriever = await asyncio.to_thread(
                            RETRIEVAL_MANAGER.get_retriever,
                            cfg,
                            user_id,
                            k,
                        )
                        docs = await asyncio.to_thread(
                            cast(Any, retriever).invoke, query
                        )
                        return json.dumps(
                            {
                                "status": "ok",
                                "indexer_tool": "web_rag",
                                "parser": parser_meta,
                                "query": query,
                                "user_id": user_id,
                                "index_status": get_index_status(cfg, user_id),
                                "bootstrap": bootstrap,
                                "sources": [
                                    d.metadata.get("source") for d in docs if d.metadata
                                ],
                                "chunks": _compact_chunks(
                                    [d.page_content for d in docs]
                                ),
                            },
                            ensure_ascii=True,
                        )
                    except Exception as retry_error:
                        logger.warning(
                            "web_rag retry after bootstrap failed: %s", retry_error
                        )

            return json.dumps(
                {
                    "status": "empty_index",
                    "indexer_tool": "web_rag",
                    "parser": parser_meta,
                    "index_status": get_index_status(cfg, user_id),
                    "message": "web_rag has no indexed documents yet.",
                    "hint": "Index URLs first via /tools/web_rag/tools with action='index'.",
                },
                ensure_ascii=True,
            )
        except Exception as e:
            logger.exception("web_rag execution failed")
            return json.dumps(
                {
                    "status": "error",
                    "indexer_tool": "web_rag",
                    "parser": parser_meta,
                    "index_status": get_index_status(cfg, user_id),
                    "error": f"web_rag failed: {e}",
                },
                ensure_ascii=True,
            )

    def _register_routes(self):
        @self.router.get("/configuration")
        def get_config():
            return self._get_config()

        @self.router.post("/configuration")
        def set_config(config: dict):
            CONFIG_STORE.set(self.name, config)
            return {"status": "ok"}

        @self.router.get("/status")
        async def status(user_id: str = "default_user"):
            config = self._get_config()
            index = await asyncio.to_thread(get_index_status, config, user_id)
            jobs = await asyncio.to_thread(
                INDEXING_MANAGER.list_jobs, user_id=user_id, limit=10
            )
            return {
                "index": index,
                "jobs": jobs,
            }

        @self.router.get("/jobs/{job_id}")
        async def get_job(job_id: str):
            job = await asyncio.to_thread(INDEXING_MANAGER.get_job, job_id)
            if not job:
                return {"error": "job not found", "job_id": job_id}
            return job

        @self.router.get("/chunks")
        async def get_chunks(
            user_id: str = "default_user", offset: int = 0, limit: int = 50
        ):
            config = self._get_config()
            base_path = config.get("base_path", "data/web_rag")
            docs_path = Path(base_path) / f"user_{user_id}" / "documents.json"

            if not docs_path.exists():
                return {"total": 0, "offset": offset, "limit": limit, "items": []}

            def _read_chunks() -> dict:
                try:
                    raw = json.loads(docs_path.read_text())
                    total = len(raw)
                    slice_ = raw[offset : offset + limit]
                    return {
                        "total": total,
                        "offset": offset,
                        "limit": limit,
                        "items": slice_,
                    }
                except Exception as e:
                    return {"error": f"failed to read chunks: {e}"}

            return await asyncio.to_thread(_read_chunks)

        @self.router.get("/raw")
        async def get_raw_sources(
            user_id: str = "default_user", offset: int = 0, limit: int = 20
        ):
            config = self._get_config()
            base_path = config.get("base_path", "data/web_rag")
            raw_path = Path(base_path) / f"user_{user_id}" / "raw_sources.jsonl"

            if not raw_path.exists():
                return {"total": 0, "offset": offset, "limit": limit, "items": []}

            def _read_raw() -> dict:
                items: list[dict] = []
                total = 0
                with raw_path.open("r", encoding="utf-8") as f:
                    for i, line in enumerate(f):
                        total += 1
                        if i < offset:
                            continue
                        if len(items) >= limit:
                            continue
                        try:
                            items.append(json.loads(line))
                        except Exception:
                            continue

                return {
                    "total": total,
                    "offset": offset,
                    "limit": limit,
                    "items": items,
                }

            return await asyncio.to_thread(_read_raw)

        @self.router.get("/download/chunks")
        async def download_chunks(user_id: str = "default_user"):
            config = self._get_config()
            base_path = config.get("base_path", "data/web_rag")
            docs_path = Path(base_path) / f"user_{user_id}" / "documents.json"
            if not docs_path.exists():
                return {"error": "chunks file not found"}
            data = await asyncio.to_thread(docs_path.read_text, encoding="utf-8")
            return JSONResponse(
                content={"user_id": user_id, "documents": json.loads(data)},
                headers={
                    "Content-Disposition": f'attachment; filename="web_rag_chunks_{user_id}.json"'
                },
            )

        @self.router.get("/download/raw")
        async def download_raw(user_id: str = "default_user"):
            config = self._get_config()
            base_path = config.get("base_path", "data/web_rag")
            raw_path = Path(base_path) / f"user_{user_id}" / "raw_sources.jsonl"
            if not raw_path.exists():
                return {"error": "raw sources file not found"}
            text = await asyncio.to_thread(raw_path.read_text, encoding="utf-8")
            lines = text.splitlines()
            parsed = []
            for line in lines:
                try:
                    parsed.append(json.loads(line))
                except Exception:
                    continue
            return JSONResponse(
                content={"user_id": user_id, "sources": parsed},
                headers={
                    "Content-Disposition": f'attachment; filename="web_rag_raw_{user_id}.json"'
                },
            )

        @self.router.post("/test-search")
        async def test_search(payload: dict):
            user_id = payload.get("user_id", "default_user")
            query = payload.get("query")
            k = int(payload.get("k", 5))
            if not query:
                return {"error": "query is required"}

            started = time.perf_counter()
            try:
                retriever = await asyncio.to_thread(
                    RETRIEVAL_MANAGER.get_retriever,
                    self._get_config(),
                    user_id,
                    k,
                )
                docs = await asyncio.to_thread(cast(Any, retriever).invoke, query)
                elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
                return {
                    "query": query,
                    "k": k,
                    "elapsed_ms": elapsed_ms,
                    "results": [
                        {
                            "content": d.page_content,
                            "metadata": d.metadata,
                        }
                        for d in docs
                    ],
                }
            except Exception as e:
                elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
                return {
                    "query": query,
                    "k": k,
                    "elapsed_ms": elapsed_ms,
                    "error": str(e),
                }

        @self.router.post("/tools")
        async def execute(payload: dict):
            action = payload.get("action")
            user_id = payload.get("user_id", "default_user")
            config = self._get_config()

            if action == "index":
                try:
                    url = str(payload["url"])
                    wait_for_completion = bool(
                        payload.get("wait_for_completion", False)
                    )

                    if wait_for_completion:
                        indexer = WebRAGIndexer(config, user_id)
                        stats = await asyncio.to_thread(indexer.index_url, url)
                        return {"status": "indexed", "url": url, "stats": stats}

                    job_id = await asyncio.to_thread(
                        INDEXING_MANAGER.start_job,
                        config,
                        user_id,
                        [url],
                    )
                    return {
                        "status": "queued",
                        "job_id": job_id,
                        "indexer_tool": "web_rag",
                        "status_endpoint": f"/tools/web_rag/jobs/{job_id}",
                    }
                except Exception as e:
                    logger.exception("web_rag index failed")
                    return {"error": f"Indexing failed: {e}"}

            if action == "query":
                try:
                    retriever = await asyncio.to_thread(
                        RETRIEVAL_MANAGER.get_retriever,
                        config,
                        user_id,
                        payload.get("k", 5),
                    )
                    docs = await asyncio.to_thread(
                        cast(Any, retriever).invoke, payload["query"]
                    )
                    return {
                        "results": [d.page_content for d in docs],
                        "sources": [
                            d.metadata.get("source") for d in docs if d.metadata
                        ],
                    }
                except ValueError as e:
                    return {
                        "error": str(e),
                        "hint": "Index at least one URL first using action='index'.",
                    }
                except Exception as e:
                    logger.exception("web_rag query failed")
                    return {"error": f"Query failed: {e}"}

            if action == "status":
                index = await asyncio.to_thread(get_index_status, config, user_id)
                jobs = await asyncio.to_thread(
                    INDEXING_MANAGER.list_jobs, user_id=user_id, limit=10
                )
                return {
                    "index": index,
                    "jobs": jobs,
                }

            return {"error": "invalid action"}

    def get_router(self):
        return self.router

    def get_langchain_tool(self):
        async def arun(
            query: str,
            user_id: str = "default_user",
            k: int = 5,
            auto_bootstrap_web: bool = True,
            config: RunnableConfig | None = None,
        ) -> str:
            return await self._query_with_progress(
                query=query,
                user_id=user_id,
                k=k,
                auto_bootstrap_web=auto_bootstrap_web,
                config=config,
            )

        def run(
            query: str,
            user_id: str = "default_user",
            k: int = 5,
            auto_bootstrap_web: bool = True,
        ) -> str:
            return asyncio.run(
                self._query_with_progress(
                    query=query,
                    user_id=user_id,
                    k=k,
                    auto_bootstrap_web=auto_bootstrap_web,
                )
            )

        return StructuredTool.from_function(
            func=run,
            coroutine=arun,
            name="web_rag",
            description=(
                "Query local hybrid RAG over indexed web documents. "
                "If empty, it can auto-bootstrap by indexing top web search results. "
                "Returns JSON with status, retrieved chunks, and sources."
            ),
            args_schema=WebRAGArgs,
        )

    async def _bootstrap_from_web(
        self,
        query: str,
        user_id: str,
        config: RunnableConfig | None = None,
    ) -> dict:
        try:
            await adispatch_custom_event(
                "tool_progress",
                {"tool": self.name, "stage": "bootstrap_search", "status": "started"},
                config=config,
            )
        except Exception:
            pass

        search_cfg = CONFIG_STORE.get("web_search")
        try:
            service = SerperSearchService(search_cfg)
            results = await asyncio.to_thread(service.search, query)
        except Exception as e:
            return {"indexed_urls": 0, "errors": [f"bootstrap search failed: {e}"]}

        links = [r.get("link") for r in results if r.get("link")][:2]
        indexed = 0
        errors: list[str] = []
        source_items: list[dict[str, Any]] = []

        for link in links:
            source_record = {
                "url": cast(str, link),
                "status": "running",
                "stage": "bootstrap_index",
                "indexer_tool": "web_rag",
                "parser": self._get_config().get("pdf_parser", "pypdf"),
                "documents": 0,
                "chunks": 0,
                "error": None,
            }
            source_items.append(source_record)

            try:
                await adispatch_custom_event(
                    "tool_progress",
                    {
                        "tool": self.name,
                        "stage": "bootstrap_index",
                        "status": "started",
                        "url": link,
                    },
                    config=config,
                )
            except Exception:
                pass

            try:
                indexer = WebRAGIndexer(self._get_config(), user_id)
                stats = await asyncio.to_thread(indexer.index_url, cast(str, link))
                source_record["status"] = "completed"
                source_record["stage"] = "completed"
                source_record["documents"] = stats.get("documents", 0)
                source_record["chunks"] = stats.get("chunks", 0)
                source_record["parser"] = stats.get("parser", source_record["parser"])
                indexed += 1
            except Exception as e:
                errors.append(f"{link}: {e}")
                source_record["status"] = "failed"
                source_record["stage"] = "failed"
                source_record["error"] = str(e)

        return {
            "indexed_urls": indexed,
            "errors": errors,
            "indexer_tool": "web_rag",
            "parser": {
                "pdf_parser": self._get_config().get("pdf_parser", "pypdf"),
                "docling_device": self._get_config().get("docling_device", "cpu"),
            },
            "sources": source_items,
        }
