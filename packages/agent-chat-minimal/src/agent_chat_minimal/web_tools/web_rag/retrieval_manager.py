import hashlib
import json
from pathlib import Path

from .indexer import WebRAGIndexer


class RetrievalManager:
    """
    Centralized retriever factory with in-memory caching.
    Avoids repeated FAISS/BM25 disk reloads per request.
    """

    def __init__(self):
        # (user_id, config_hash) -> retriever
        self._cache: dict[tuple, object] = {}

    @staticmethod
    def _config_signature(config: dict) -> str:
        """Stable hash of config dict."""
        normalized = json.dumps(config or {}, sort_keys=True)
        return hashlib.sha256(normalized.encode()).hexdigest()

    def get_retriever(self, config: dict, user_id: str, k: int = 5):
        sig = self._config_signature(config)
        path = (
            Path(config.get("base_path", "data/web_rag"))
            / f"user_{user_id}"
            / "documents.json"
        )
        version = path.stat().st_mtime_ns if path.exists() else 0
        key = (user_id, sig, k, version)

        if key in self._cache:
            retriever = self._cache[key]
            # Update k dynamically if needed
            retriever.k = k
            return retriever

        indexer = WebRAGIndexer(config, user_id)
        retriever = indexer.get_retriever(k=k)

        # Retain only the latest corpus snapshot for this namespace.
        self._cache = {
            key_: value for key_, value in self._cache.items() if key_[0] != user_id
        }
        self._cache[key] = retriever
        return retriever


# Global singleton for application usage
RETRIEVAL_MANAGER = RetrievalManager()
