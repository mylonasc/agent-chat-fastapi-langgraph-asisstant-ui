import hashlib
import json
from typing import Dict, Tuple

from .indexer import WebRAGIndexer


class RetrievalManager:
    """
    Centralized retriever factory with in-memory caching.
    Avoids repeated FAISS/BM25 disk reloads per request.
    """

    def __init__(self):
        # (user_id, config_hash) -> retriever
        self._cache: Dict[Tuple[str, str], object] = {}

    @staticmethod
    def _config_signature(config: dict) -> str:
        """Stable hash of config dict."""
        normalized = json.dumps(config or {}, sort_keys=True)
        return hashlib.sha256(normalized.encode()).hexdigest()

    def get_retriever(self, config: dict, user_id: str, k: int = 5):
        sig = self._config_signature(config)
        key = (user_id, sig)

        if key in self._cache:
            retriever = self._cache[key]
            # Update k dynamically if needed
            retriever.k = k
            return retriever

        indexer = WebRAGIndexer(config, user_id)
        retriever = indexer.get_retriever(k=k)

        self._cache[key] = retriever
        return retriever


# Global singleton for application usage
RETRIEVAL_MANAGER = RetrievalManager()
