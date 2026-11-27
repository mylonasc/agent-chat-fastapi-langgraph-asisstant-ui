import hashlib
from typing import List

from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document


def _doc_id(doc: Document):
    source = doc.metadata.get("source", "")
    content = doc.page_content
    return hashlib.sha256((source + content).encode()).hexdigest()


class HybridRetriever(BaseRetriever):
    """Hybrid retriever using Reciprocal Rank Fusion (RRF)."""

    dense: BaseRetriever
    sparse: BaseRetriever
    k: int = 5
    rrf_k: int = 60

    model_config = {"arbitrary_types_allowed": True}

    def _get_relevant_documents(self, query: str, *, run_manager) -> List[Document]:
        dense_docs = self.dense.invoke(query)
        sparse_docs = self.sparse.invoke(query)

        scores = {}
        lookup = {}

        for rank, doc in enumerate(dense_docs):
            did = _doc_id(doc)
            scores.setdefault(did, 0.0)
            scores[did] += 1.0 / (self.rrf_k + rank + 1)
            lookup[did] = doc

        for rank, doc in enumerate(sparse_docs):
            did = _doc_id(doc)
            scores.setdefault(did, 0.0)
            scores[did] += 1.0 / (self.rrf_k + rank + 1)
            lookup[did] = doc

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [lookup[did] for did, _ in ranked[: self.k]]


class SparseRetriever(BaseRetriever):
    """BM25-backed sparse retriever wrapping SparseStore."""

    store: object
    documents: List[Document]
    k: int = 5

    model_config = {"arbitrary_types_allowed": True}

    def _get_relevant_documents(self, query: str, *, run_manager) -> List[Document]:
        texts = self.store.query(query, k=self.k)
        lookup = {d.page_content: d for d in self.documents}
        return [lookup[t] for t in texts if t in lookup]
