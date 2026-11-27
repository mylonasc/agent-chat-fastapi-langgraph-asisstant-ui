"""Legacy import aliases; implementations live in the portable package.

This adapter keeps the source-run RAG examples and their import paths working
without maintaining a second copy of any tool implementation.
"""
import importlib
import sys

for suffix in (
    "config", "authorization", "web_search", "web_search.service", "web_search.tool",
    "web_rag", "web_rag.ingestion", "web_rag.ingestion.docling_adapter",
    "web_rag.ingestion.loader", "web_rag.embeddings", "web_rag.vectorstore",
    "web_rag.sparse_store", "web_rag.retriever", "web_rag.indexer",
    "web_rag.retrieval_manager", "web_rag.background_jobs", "web_rag.status",
    "web_rag.status_tool", "web_rag.tool", "registry",
):
    module = importlib.import_module(f"agent_chat_minimal.web_tools.{suffix}")
    sys.modules[f"{__name__}.{suffix}"] = module
    if "." not in suffix:
        globals()[suffix] = module
