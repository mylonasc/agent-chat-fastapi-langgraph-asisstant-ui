import os
import tempfile

from tools.web_rag.sparse_store import SparseStore


def test_sparse_store_basic_ranking():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "bm25.pkl")

        store = SparseStore(path)
        store.add_texts(
            [
                "the quick brown fox",
                "rareword appears here",
                "another document",
            ]
        )
        store.save()

        # Reload from disk
        store2 = SparseStore(path)
        results = store2.query("rareword", k=1)

        assert len(results) == 1
        assert "rareword" in results[0]
