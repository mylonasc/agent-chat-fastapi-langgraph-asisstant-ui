"""Cache invalidation must not hide data indexed after the first retrieval."""

from types import SimpleNamespace

from tools.web_rag import retrieval_manager


def test_retriever_cache_tracks_corpus_version_config_and_k(tmp_path, monkeypatch):
    builds = []

    class Indexer:
        def __init__(self, config, user_id):
            builds.append((config, user_id))

        def get_retriever(self, k):
            return SimpleNamespace(k=k)

    monkeypatch.setattr(retrieval_manager, "WebRAGIndexer", Indexer)
    manager = retrieval_manager.RetrievalManager()
    config = {"base_path": str(tmp_path)}
    original = manager.get_retriever(config, "alice", k=3)
    assert manager.get_retriever(config, "alice", k=3) is original
    assert manager.get_retriever(config, "alice", k=8) is not original
    document_path = tmp_path / "user_alice" / "documents.json"
    document_path.parent.mkdir()
    document_path.write_text("[]")
    updated = manager.get_retriever(config, "alice", k=8)
    assert manager.get_retriever(config, "alice", k=8) is updated
    manager.get_retriever({**config, "chunk_size": 400}, "alice", k=8)
    assert len(builds) == 4
    assert len(manager._cache) == 1
