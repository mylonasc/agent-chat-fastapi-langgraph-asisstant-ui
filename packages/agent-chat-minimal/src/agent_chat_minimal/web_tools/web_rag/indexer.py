import json
import time
from pathlib import Path
from typing import Any, Callable

from langchain_core.documents import Document
from .vectorstore import FAISSStore
from .embeddings import EmbeddingFactory
from .retriever import HybridRetriever, SparseRetriever
from .sparse_store import SparseStore
from .ingestion.loader import ContentLoader


class WebRAGIndexer:
    def __init__(self, config: dict, user_id: str):
        self.config = config
        self.user_id = user_id

        self.embeddings = EmbeddingFactory.create(config)

        base_path = config.get("base_path", "data/web_rag")

        self.store = FAISSStore(
            base_path=base_path,
            user_id=user_id,
            embeddings=self.embeddings,
        )

        # Sparse BM25 store (persist alongside FAISS)
        sparse_path = f"{base_path}/user_{user_id}/bm25.pkl"
        self.sparse_store = SparseStore(sparse_path)

        # Simple splitter fallback (no external dependency)
        self.chunk_size = config.get("chunk_size", 800)

        user_path = Path(base_path) / f"user_{user_id}"
        user_path.mkdir(parents=True, exist_ok=True)
        self.raw_sources_path = user_path / "raw_sources.jsonl"

    def index_url(
        self,
        url: str,
        progress_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        if progress_callback:
            progress_callback("downloading", {"url": url})

        docs = ContentLoader.load(url, parser_config=self.config)

        if progress_callback:
            progress_callback(
                "extracting",
                {
                    "url": url,
                    "documents": len(docs),
                },
            )

        self._append_raw_sources(url, docs)

        # Simple chunking fallback
        split_docs = []
        if progress_callback:
            progress_callback("chunking", {"url": url})

        for d in docs:
            content = d.page_content
            chunks = [
                content[i : i + self.chunk_size]
                for i in range(0, len(content), self.chunk_size)
            ]
            for c in chunks:
                split_docs.append(
                    Document(
                        page_content=c,
                        metadata={**d.metadata, "source": url},
                    )
                )

        if progress_callback:
            progress_callback(
                "indexing",
                {
                    "url": url,
                    "chunks": len(split_docs),
                },
            )

        self.store.add_documents(split_docs)
        # Update sparse store with raw chunk texts
        self.sparse_store.add_texts([d.page_content for d in split_docs])
        self.store.save()
        self.sparse_store.save()

        parser = (
            docs[0].metadata.get("parser") if docs and docs[0].metadata else "pypdf"
        )

        return {
            "url": url,
            "documents": len(docs),
            "chunks": len(split_docs),
            "parser": parser or "pypdf",
            "indexer_tool": "web_rag",
        }

    def _append_raw_sources(self, url: str, docs: list[Document]) -> None:
        with self.raw_sources_path.open("a", encoding="utf-8") as f:
            for d in docs:
                rec = {
                    "url": url,
                    "captured_at": time.time(),
                    "metadata": d.metadata or {},
                    "content": d.page_content,
                    "content_length": len(d.page_content or ""),
                }
                f.write(json.dumps(rec, ensure_ascii=True) + "\n")

    def get_retriever(self, k=5):
        dense = self.store.as_dense_retriever(k=k)

        sparse = SparseRetriever(
            store=self.sparse_store,
            documents=self.store.get_all_documents(),
            k=k,
        )

        return HybridRetriever(
            dense=dense,
            sparse=sparse,
            k=k,
        )
