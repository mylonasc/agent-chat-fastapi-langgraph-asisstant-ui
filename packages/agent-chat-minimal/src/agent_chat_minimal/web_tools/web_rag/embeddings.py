import os
from typing import Dict

from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import FastEmbedEmbeddings


class EmbeddingFactory:
    """Factory for creating embedding models (OpenAI or HuggingFace)."""

    @staticmethod
    def create(config: Dict):
        provider = config.get("embedding_provider", "openai")

        if provider == "openai":
            if not os.getenv("OPENAI_API_KEY"):
                raise RuntimeError("OPENAI_API_KEY not set.")
            return OpenAIEmbeddings(
                model=config.get("embedding_model", "text-embedding-3-small")
            )

        if provider == "fastembed":
            return FastEmbedEmbeddings()

        if provider == "sentence_transformers":
            if os.getenv("ENABLE_SENTENCE_TRANSFORMERS") != "1":
                raise RuntimeError(
                    "Sentence transformers disabled. Set ENABLE_SENTENCE_TRANSFORMERS=1"
                )
            try:
                from langchain_community.embeddings import HuggingFaceEmbeddings
            except ImportError as e:
                raise ImportError("sentence-transformers not installed") from e

            return HuggingFaceEmbeddings(
                model_name=config.get(
                    "embedding_model",
                    "sentence-transformers/all-MiniLM-L6-v2",
                )
            )

        raise ValueError(f"Unsupported embedding provider: {provider}")
