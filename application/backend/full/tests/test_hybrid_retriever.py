from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from tools.web_rag.retriever import HybridRetriever


class DummyRetriever(BaseRetriever):
    docs: list

    model_config = {"arbitrary_types_allowed": True}

    def _get_relevant_documents(self, query: str, *, run_manager):
        return self.docs


def test_rrf_priority():
    d1 = Document(page_content="A")
    d2 = Document(page_content="B")

    dense = DummyRetriever(docs=[d1, d2])
    sparse = DummyRetriever(docs=[d2])

    hybrid = HybridRetriever(dense=dense, sparse=sparse, k=2)
    results = hybrid.invoke("x")

    assert results[0].page_content == "B"
