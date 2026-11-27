import os
import pickle
from typing import List

from rank_bm25 import BM25Okapi


class SparseStore:
    """
    Persistent BM25 sparse index aligned with stored document texts.
    Stores raw texts and rebuilds BM25 on load.
    """

    def __init__(self, persist_path: str):
        self.persist_path = persist_path
        self._texts: List[str] = []
        self._tokenized: List[List[str]] = []
        self._bm25: BM25Okapi | None = None

        if os.path.exists(self.persist_path):
            self._load()

    def add_texts(self, texts: List[str]) -> None:
        for text in texts:
            tokens = self._tokenize(text)
            self._texts.append(text)
            self._tokenized.append(tokens)

        self._rebuild()

    def query(self, query: str, k: int = 5) -> List[str]:
        if not self._bm25:
            return []

        tokens = self._tokenize(query)
        scores = self._bm25.get_scores(tokens)

        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:k]

        return [self._texts[i] for i, _ in ranked]

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.persist_path), exist_ok=True)
        with open(self.persist_path, "wb") as f:
            pickle.dump(self._texts, f)

    def _load(self) -> None:
        with open(self.persist_path, "rb") as f:
            self._texts = pickle.load(f)

        self._tokenized = [self._tokenize(t) for t in self._texts]
        self._rebuild()

    def _rebuild(self) -> None:
        if self._tokenized:
            self._bm25 = BM25Okapi(self._tokenized)
        else:
            self._bm25 = None

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return text.lower().split()
