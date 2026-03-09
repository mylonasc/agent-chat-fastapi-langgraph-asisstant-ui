# Running the Application

This repo contains two flavors of a LangGraph + FastAPI + Assistant UI chat application:

## Flavors

### Minimal
- **Backend**: Simple chat-only server with weather + graph visualization tools
- **Frontend**: Basic chat interface
- **Use case**: Quick testing, prototyping, understanding the stack

### Full
- **Backend**: Full-featured server with thread management, message persistence
- **Frontend**: Complete chat UI with thread list, history, multiple chats
- **Use case**: Production-ready with multi-chat support

## Quick Start with Docker

### Prerequisites
- Docker & Docker Compose
- OpenAI API key

### Setup

1. Copy the environment file:
```bash
cp .env.example .env
```

2. Edit `.env` and add your API keys:
```
OPENAI_API_KEY=sk-...
SERPER_API_KEY=...
DOCLING_VARIANT=none
```

`DOCLING_VARIANT` options for full backend Docker build:

- `none` (default): no Docling installed
- `cpu`: installs Docling CPU stack
- `gpu`: installs Docling + ONNX Runtime GPU

### Run Minimal Flavor

```bash
docker-compose -f docker-compose.minimal.yml up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8011

### Run Full Flavor

```bash
docker-compose -f docker-compose.full.yml up --build
```

- Frontend: http://localhost:3001
- Backend API: http://localhost:8010
- Admin panel: http://localhost:3001/admin

## Running Locally (Without Docker)

### Minimal

```bash
# Terminal 1 - Backend
cd application/backend/langgraph-server-minimal
./start_server.sh

# Terminal 2 - Frontend
cd application/frontend/frontend-minimal
pnpm install
pnpm dev
```

### Full

```bash
# Terminal 1 - Backend
cd application/backend/full
./start_server.sh

# Terminal 2 - Frontend
cd application/frontend/frontend-full
pnpm install
pnpm dev
```

Optional PDF extraction backends (full backend):

- Docling CPU: `uv sync --extra docling-cpu`
- Docling GPU: `uv sync --extra docling-gpu`

Then set `web_rag` tool config with `pdf_parser: "docling"` and `docling_device: "cpu"` or `"cuda"`.

## API Endpoints

### Minimal Backend (port 8011)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/assistant` | POST | Chat endpoint (SSE streaming) |
| `/health` | GET | Health check |

### Full Backend (port 8010)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/assistant` | POST | Chat endpoint (SSE streaming) |
| `/threads` | GET | List all threads |
| `/threads` | POST | Create new thread |
| `/threads/{id}` | GET | Get thread details |
| `/threads/{id}/messages` | GET | Get thread messages |
| `/threads/{id}/messages` | POST | Append message to thread |
| `/tools/web_rag/status` | GET | Index stats + recent indexing jobs |
| `/tools/overview` | GET | Available tools, configs, runtime dependency state |
| `/tools/web_rag/jobs/{job_id}` | GET | Per-URL indexing progress for one job |
| `/tools/web_rag/chunks` | GET | Preview indexed chunks for a user |
| `/tools/web_rag/raw` | GET | Preview raw downloaded sources for a user |
| `/tools/web_rag/download/chunks` | GET | Download indexed chunks as JSON |
| `/tools/web_rag/download/raw` | GET | Download raw downloaded sources as JSON |
| `/tools/web_rag/test-search` | POST | Run retrieval test query + latency |

`web_search` now queues background indexing by default and returns an indexing `job_id` in the tool result payload.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Your OpenAI API key (required) |
| `SERPER_API_KEY` | Serper API key (required for `web_search` in full backend) |
| `NEXT_PUBLIC_API_URL` | Backend URL (frontend only, optional in Docker) |

## Tech Stack

- **Backend**: FastAPI, LangGraph, Assistant Stream CE
- **Frontend**: Next.js 16, Assistant UI, Tailwind CSS
- **LLM**: OpenAI (GPT-4o-mini by default)
