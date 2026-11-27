import threading
import time
import uuid
import copy
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .indexer import WebRAGIndexer


class BackgroundIndexingManager:
    def __init__(self, max_workers: int = 4):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._lock = threading.Lock()
        self._jobs: dict[str, dict[str, Any]] = {}

    def start_job(self, config: dict, user_id: str, urls: list[str]) -> str:
        job_id = str(uuid.uuid4())
        now = time.time()
        job = {
            "job_id": job_id,
            "user_id": user_id,
            "status": "queued",
            "created_at": now,
            "updated_at": now,
            "indexer_tool": "web_rag",
            "parser": {
                "pdf_parser": config.get("pdf_parser", "pypdf"),
                "docling_device": config.get("docling_device", "cpu"),
            },
            "total_urls": len(urls),
            "completed_urls": 0,
            "failed_urls": 0,
            "items": [
                {
                    "url": u,
                    "status": "queued",
                    "stage": "queued",
                    "error": None,
                    "started_at": None,
                    "completed_at": None,
                    "documents": 0,
                    "chunks": 0,
                    "parser": config.get("pdf_parser", "pypdf"),
                    "indexer_tool": "web_rag",
                }
                for u in urls
            ],
        }

        with self._lock:
            self._jobs[job_id] = job

        self._executor.submit(self._run_job, job_id, config, user_id, urls)
        return job_id

    def _run_job(
        self, job_id: str, config: dict, user_id: str, urls: list[str]
    ) -> None:
        self._set_job_field(job_id, "status", "running")

        indexer = WebRAGIndexer(config, user_id)

        for idx, url in enumerate(urls):
            self._set_item_stage(job_id, idx, "running", "downloading")
            try:
                stats = indexer.index_url(
                    url,
                    progress_callback=lambda stage, payload: self._set_item_stage(
                        job_id,
                        idx,
                        "running",
                        stage,
                        payload,
                    ),
                )
                self._set_item_stage(job_id, idx, "completed", "completed", stats)
                with self._lock:
                    self._jobs[job_id]["completed_urls"] += 1
                    self._jobs[job_id]["updated_at"] = time.time()
            except Exception as e:
                self._set_item_stage(
                    job_id,
                    idx,
                    "failed",
                    "failed",
                    payload={"error": str(e)},
                )
                with self._lock:
                    self._jobs[job_id]["failed_urls"] += 1
                    self._jobs[job_id]["updated_at"] = time.time()

        with self._lock:
            job = self._jobs[job_id]
            job["status"] = (
                "completed" if job["failed_urls"] == 0 else "completed_with_errors"
            )
            job["updated_at"] = time.time()

    def _set_job_field(self, job_id: str, key: str, value: Any) -> None:
        with self._lock:
            self._jobs[job_id][key] = value
            self._jobs[job_id]["updated_at"] = time.time()

    def _set_item_stage(
        self,
        job_id: str,
        idx: int,
        status: str,
        stage: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            item = self._jobs[job_id]["items"][idx]
            item["status"] = status
            item["stage"] = stage
            if item.get("started_at") is None and status == "running":
                item["started_at"] = time.time()

            if payload:
                if payload.get("error"):
                    item["error"] = payload.get("error")
                if "documents" in payload:
                    item["documents"] = payload.get("documents")
                if "chunks" in payload:
                    item["chunks"] = payload.get("chunks")
                if "parser" in payload:
                    item["parser"] = payload.get("parser")

            item["completed_at"] = (
                time.time() if status in {"completed", "failed"} else None
            )
            self._jobs[job_id]["updated_at"] = time.time()

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return copy.deepcopy(job) if job else None

    def list_jobs(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            jobs = [j for j in self._jobs.values() if j.get("user_id") == user_id]
            jobs.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
            return [copy.deepcopy(j) for j in jobs[:limit]]


INDEXING_MANAGER = BackgroundIndexingManager()
