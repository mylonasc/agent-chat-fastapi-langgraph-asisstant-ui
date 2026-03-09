import json

from langchain_core.documents import Document

from tools.web_rag.tool import WebRAGTool
from tools.web_rag.status_tool import WebRAGStatusTool
from tools.web_search.tool import WebSearchTool


def test_web_rag_empty_index_returns_structured_payload(monkeypatch):
    def _raise_empty(*args, **kwargs):
        raise ValueError("Vector store empty.")

    monkeypatch.setattr(
        "tools.web_rag.tool.RETRIEVAL_MANAGER.get_retriever",
        _raise_empty,
    )

    tool = WebRAGTool().get_langchain_tool()
    raw = tool.invoke({"query": "latest news", "user_id": "default_user"})
    payload = json.loads(raw)

    assert payload["status"] == "empty_index"
    assert "Index URLs first" in payload["hint"]


def test_web_search_can_return_documents_and_rag_chunks(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "test-key")

    class DummyRetriever:
        def invoke(self, query: str):
            return [
                Document(
                    page_content=f"chunk for {query}",
                    metadata={"source": "https://example.com"},
                )
            ]

    monkeypatch.setattr(
        "tools.web_search.tool.SerperSearchService.search",
        lambda self, query: [
            {
                "title": "Example",
                "link": "https://example.com",
                "snippet": "example snippet",
            }
        ],
    )
    monkeypatch.setattr(
        "tools.web_search.tool.RETRIEVAL_MANAGER.get_retriever",
        lambda *args, **kwargs: DummyRetriever(),
    )
    monkeypatch.setattr(
        "tools.web_search.tool.INDEXING_MANAGER.start_job",
        lambda config, user_id, urls: "job-1",
    )

    tool = WebSearchTool().get_langchain_tool()
    raw = tool.invoke(
        {
            "query": "example domain",
            "as_documents": True,
            "as_rag_chunks": True,
            "user_id": "default_user",
            "rag_urls_to_index": 1,
            "rag_k": 1,
        }
    )
    payload = json.loads(raw)

    assert payload["status"] == "ok"
    assert payload["documents"][0]["url"] == "https://example.com"
    assert payload["rag"]["indexing"]["job_id"] == "job-1"
    assert payload["rag"]["indexing"]["indexer_tool"] == "web_rag"
    assert payload["rag"]["indexing"]["parser"]["pdf_parser"] in {"pypdf", "docling"}
    assert payload["rag"]["indexing"]["sources"][0]["url"] == "https://example.com"
    assert payload["rag"]["chunks"][0] == "chunk for example domain"


def test_web_search_auto_indexes_even_without_rag_chunks(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "test-key")

    queued_urls: list[str] = []

    monkeypatch.setattr(
        "tools.web_search.tool.SerperSearchService.search",
        lambda self, query: [
            {
                "title": "Example",
                "link": "https://example.com",
                "snippet": "example snippet",
            }
        ],
    )
    monkeypatch.setattr(
        "tools.web_search.tool.INDEXING_MANAGER.start_job",
        lambda config, user_id, urls: queued_urls.extend(urls) or "job-2",
    )

    tool = WebSearchTool().get_langchain_tool()
    raw = tool.invoke(
        {
            "query": "example domain",
            "as_documents": True,
            "as_rag_chunks": False,
            "user_id": "default_user",
            "rag_urls_to_index": 1,
        }
    )
    payload = json.loads(raw)

    assert payload["status"] == "ok"
    assert payload["indexing"]["job_id"] == "job-2"
    assert payload["indexing"]["queued_urls"] == 1
    assert payload["indexing"]["indexer_tool"] == "web_rag"
    assert queued_urls == ["https://example.com"]


def test_web_rag_bootstraps_from_web_when_empty(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "test-key")

    class DummyRetriever:
        def invoke(self, query: str):
            return [
                Document(page_content="bootstrapped chunk", metadata={"source": "x"})
            ]

    calls = {"get_retriever": 0}

    def fake_get_retriever(*args, **kwargs):
        calls["get_retriever"] += 1
        if calls["get_retriever"] == 1:
            raise ValueError("Vector store empty.")
        return DummyRetriever()

    monkeypatch.setattr(
        "tools.web_rag.tool.RETRIEVAL_MANAGER.get_retriever",
        fake_get_retriever,
    )
    monkeypatch.setattr(
        "tools.web_rag.tool.SerperSearchService.search",
        lambda self, query: [
            {
                "title": "Example",
                "link": "https://example.com",
                "snippet": "example snippet",
            }
        ],
    )
    monkeypatch.setattr(
        "tools.web_rag.tool.WebRAGIndexer.index_url",
        lambda self, url: None,
    )

    tool = WebRAGTool().get_langchain_tool()
    raw = tool.invoke({"query": "example domain", "user_id": "default_user"})
    payload = json.loads(raw)

    assert payload["status"] == "ok"
    assert payload["bootstrap"]["indexed_urls"] == 1
    assert payload["chunks"][0] == "bootstrapped chunk"


def test_web_rag_status_tool_reports_index_and_jobs(monkeypatch):
    monkeypatch.setattr(
        "tools.web_rag.status_tool.get_index_status",
        lambda config, user_id: {
            "user_id": user_id,
            "document_count": 12,
            "is_empty": False,
        },
    )
    monkeypatch.setattr(
        "tools.web_rag.status_tool.INDEXING_MANAGER.list_jobs",
        lambda user_id, limit=10: [{"job_id": "job-xyz", "status": "running"}],
    )

    tool = WebRAGStatusTool().get_langchain_tool()
    payload = json.loads(tool.invoke({"user_id": "default_user"}))

    assert payload["indexer_tool"] == "web_rag"
    assert payload["parser"]["pdf_parser"] in {"pypdf", "docling"}
    assert payload["index"]["document_count"] == 12
    assert payload["jobs"][0]["job_id"] == "job-xyz"
