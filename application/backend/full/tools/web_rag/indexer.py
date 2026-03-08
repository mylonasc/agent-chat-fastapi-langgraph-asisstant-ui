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

    def index_url(self, url: str):
        docs = ContentLoader.load(url)

        # Simple chunking fallback
        split_docs = []
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

        self.store.add_documents(split_docs)
        # Update sparse store with raw chunk texts
        self.sparse_store.add_texts([d.page_content for d in split_docs])
        self.store.save()
        self.sparse_store.save()

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
