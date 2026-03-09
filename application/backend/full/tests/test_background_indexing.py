import time

from tools.web_rag.background_jobs import BackgroundIndexingManager


def test_background_indexing_job_completes(monkeypatch):
    manager = BackgroundIndexingManager(max_workers=1)

    monkeypatch.setattr(
        "tools.web_rag.background_jobs.WebRAGIndexer.index_url",
        lambda self, url: None,
    )

    job_id = manager.start_job({"embedding_provider": "fastembed"}, "u1", ["a", "b"])

    deadline = time.time() + 3
    while time.time() < deadline:
        job = manager.get_job(job_id)
        if job and job["status"] in {"completed", "completed_with_errors"}:
            break
        time.sleep(0.05)

    job = manager.get_job(job_id)
    assert job is not None
    assert job["status"] == "completed"
    assert job["completed_urls"] == 2
    assert job["failed_urls"] == 0
    assert job["indexer_tool"] == "web_rag"
    assert job["items"][0]["stage"] == "completed"
