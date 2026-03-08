import os
import tempfile

from langchain_core.documents import Document

from tools.web_rag.embeddings import EmbeddingFactory
from tools.web_rag.vectorstore import FAISSStore


def validate_environment():
    """
    Validate critical environment constraints.
    """
    # If sentence transformers enabled, enforce torchvision isolation flag
    if os.getenv("ENABLE_SENTENCE_TRANSFORMERS") == "1":
        if os.getenv("TRANSFORMERS_NO_TORCHVISION") != "1":
            raise RuntimeError(
                "TRANSFORMERS_NO_TORCHVISION must be set to '1' when using sentence transformers."
            )


def validate_embeddings(config: dict):
    """
    Ensure embedding provider initializes and can embed.
    """
    embeddings = EmbeddingFactory.create(config)

    try:
        _ = embeddings.embed_query("healthcheck")
    except Exception as e:
        raise RuntimeError(f"Embedding preflight failed: {e}") from e

    return embeddings


def validate_faiss_roundtrip(embeddings):
    """
    Create temporary FAISS index, persist and reload to ensure functionality.
    """
    with tempfile.TemporaryDirectory() as tmp:
        store = FAISSStore(tmp, "validation_user", embeddings)

        doc = Document(page_content="faiss validation", metadata={})
        store.add_documents([doc])
        store.save()

        # Reload
        store2 = FAISSStore(tmp, "validation_user", embeddings)
        retriever = store2.as_dense_retriever(k=1)

        results = retriever.invoke("validation")

        if not results or "validation" not in results[0].page_content:
            raise RuntimeError("FAISS roundtrip validation failed.")


def run_startup_validation(config: dict):
    """
    Full startup validation pipeline.
    """
    validate_environment()
    embeddings = validate_embeddings(config)
    validate_faiss_roundtrip(embeddings)
