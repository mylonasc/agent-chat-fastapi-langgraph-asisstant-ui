import json

from tools.web_rag.status import get_index_status


def test_get_index_status_counts_docs_and_raw_sources(tmp_path):
    user_id = "u1"
    base = tmp_path / "web_rag"
    user_dir = base / f"user_{user_id}"
    user_dir.mkdir(parents=True)

    docs = [
        {"content": "c1", "metadata": {"source": "https://a"}},
        {"content": "c2", "metadata": {"source": "https://b"}},
        {"content": "c3", "metadata": {"source": "https://a"}},
    ]
    (user_dir / "documents.json").write_text(json.dumps(docs), encoding="utf-8")
    (user_dir / "raw_sources.jsonl").write_text(
        json.dumps({"url": "https://a", "content": "x"})
        + "\n"
        + json.dumps({"url": "https://b", "content": "y"})
        + "\n",
        encoding="utf-8",
    )
    (user_dir / "index.faiss").write_text("x", encoding="utf-8")
    (user_dir / "bm25.pkl").write_text("x", encoding="utf-8")

    status = get_index_status({"base_path": str(base)}, user_id)

    assert status["document_count"] == 3
    assert status["source_count"] == 2
    assert status["raw_sources_count"] == 2
    assert status["has_faiss"] is True
    assert status["has_bm25"] is True
    assert status["is_empty"] is False
