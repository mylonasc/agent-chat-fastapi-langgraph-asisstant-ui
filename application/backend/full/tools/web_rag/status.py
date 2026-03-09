import json
from pathlib import Path


def get_index_status(config: dict, user_id: str) -> dict:
    base_path = config.get("base_path", "data/web_rag")
    user_path = Path(base_path) / f"user_{user_id}"

    docs_path = user_path / "documents.json"
    faiss_path = user_path / "index.faiss"
    bm25_path = user_path / "bm25.pkl"
    raw_sources_path = user_path / "raw_sources.jsonl"

    doc_count = 0
    source_count = 0
    if docs_path.exists():
        try:
            raw = json.loads(docs_path.read_text())
            doc_count = len(raw)
            sources = {
                d.get("metadata", {}).get("source") for d in raw if isinstance(d, dict)
            }
            source_count = len([s for s in sources if s])
        except Exception:
            pass

    raw_source_count = 0
    if raw_sources_path.exists():
        try:
            with raw_sources_path.open("r", encoding="utf-8") as f:
                raw_source_count = sum(1 for _ in f)
        except Exception:
            pass

    return {
        "user_id": user_id,
        "base_path": str(user_path),
        "document_count": doc_count,
        "source_count": source_count,
        "has_faiss": faiss_path.exists(),
        "has_bm25": bm25_path.exists(),
        "raw_sources_count": raw_source_count,
        "is_empty": doc_count == 0,
    }
