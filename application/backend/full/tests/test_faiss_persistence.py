import tempfile
from langchain_core.documents import Document

from tools.web_rag.vectorstore import FAISSStore
from tools.web_rag.embeddings import EmbeddingFactory


def test_faiss_persistence():
    with tempfile.TemporaryDirectory() as tmp:
        config = {"embedding_provider": "fastembed"}
        embeddings = EmbeddingFactory.create(config)

        store = FAISSStore(tmp, "user1", embeddings)
        docs = [Document(page_content="hello world", metadata={})]

        store.add_documents(docs)
        store.save()

        # Reload
        store2 = FAISSStore(tmp, "user1", embeddings)
        retriever = store2.as_dense_retriever(k=1)
        results = retriever.invoke("hello")

        assert len(results) == 1
        assert "hello" in results[0].page_content
