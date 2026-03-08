import os
import pytest


@pytest.mark.skipif(not os.getenv("SERPER_API_KEY"), reason="SERPER key missing")
def test_live_serper():
    from application.backend.full.tools.web_search.service import SerperSearchService

    service = SerperSearchService({"max_results": 1})
    results = service.search("OpenAI")

    assert len(results) == 1
    assert "link" in results[0]


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OpenAI key missing")
def test_live_openai_embeddings():
    from application.backend.full.tools.web_rag.embeddings import EmbeddingFactory

    embeddings = EmbeddingFactory.create({"embedding_provider": "openai"})
    vec = embeddings.embed_query("hello world")

    assert isinstance(vec, list)
    assert len(vec) > 10
