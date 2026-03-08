# Full Agent: Web Search + Hybrid RAG

This backend ships with a **production‑ready multi‑tool agent** that combines:

- 🌐 Web Search
- 📚 Hybrid Retrieval-Augmented Generation (RAG)
- 📄 HTML / PDF / DOCX ingestion
- 🧠 Dual execution modes (tool-driven or enforced retrieval)

It is the **default agent** used by the full FastAPI server.

---

# Core Capabilities

## 1. Web Search

Tool: `web_search`

- Powered by SERPER
- Returns structured search results
- Can be invoked by the LLM in ReAct mode

---

## 2. Hybrid RAG (Dense + Sparse)

Tool: `web_rag`

Retrieval strategy:

- ✅ Dense retrieval (FAISS vector store)
- ✅ Sparse retrieval (BM25 via rank-bm25)
- ✅ Reciprocal Rank Fusion (RRF)

Persistence:

- Per-user FAISS index
- Per-user BM25 corpus
- Stored under `data/web_rag/user_<id>/`

---

## 3. Document Ingestion

Supported formats:

- HTML (URLs)
- PDF (local or URL)
- DOCX (local)
- Plain text fallback

Parsing uses LangChain document loaders:

- `WebBaseLoader`
- `PyPDFLoader`
- `Docx2txtLoader`

Documents are chunked and indexed into both dense and sparse stores.

---

# Agent Modes

Controlled via environment variable:

```
AGENT_MODE=react          # default
AGENT_MODE=enforced_rag
```

## Mode: `react` (Default)

- Tool-driven ReAct agent
- LLM decides when to:
  - Search the web
  - Use hybrid RAG
  - Combine both

## Mode: `enforced_rag`

- Retrieval always executed before answering
- Retrieved context injected as system message
- Still compatible with future tool extensions

---

# Embedding Providers

Configured via tool configuration (`web_rag` config):

```
embedding_provider:
  - "openai"
  - "fastembed"
  - "sentence_transformers"
```

### Optional Sentence Transformers

If using:

```
ENABLE_SENTENCE_TRANSFORMERS=1
TRANSFORMERS_NO_TORCHVISION=1
```

Startup will fail if constraints are not satisfied.

---

# Startup Validation

On server startup, the following checks run:

- ✅ Embedding preflight (`embed_query("healthcheck")`)
- ✅ FAISS save/load roundtrip validation
- ✅ Environment constraint validation

Server will not start if these fail.

---

# Agent Factory

To construct the agent manually:

```python
from fastlang.server.get_graph import make_web_rag_search_agent

graph = make_web_rag_search_agent(
    model_name="gpt-4o-mini",
    checkpointer=MemorySaver(),
)
```

This is the same agent used by the default full server.

---

# Architecture Overview

```
Frontend
   ↓
FastAPI Server
   ↓
LangGraph Agent
   ↓
Tools:
    - web_search
    - web_rag (Hybrid)
   ↓
RetrievalManager
   ↓
FAISS + BM25
```

---

# Current Limitations

- Chunking is size-based (not semantic yet)
- No citation formatting layer
- MemorySaver is in-memory only

---

# Summary

This backend now provides a:

- Hybrid retrieval system
- Web-grounded agent
- Multi-format ingestion pipeline
- Production validation discipline
- Dual-mode execution architecture

It is designed to be extended further with citation formatting, persistent memory, and tool orchestration enhancements.
