# LangGraph-FastAPI-AssistantUI

A template for building conversational interfaces for LangGraph agents with FastAPI and Assistant UI.

## Overview

This repo contains two flavors of a full-stack chat application:

| Flavor | Description |
|--------|-------------|
| **Minimal** | Simple chat-only server with weather + graph visualization tools |
| **Full** | Full-featured server with thread management, message persistence, and multi-chat support |

**Tech Stack:**
- **Backend**: FastAPI, LangGraph, Assistant Stream CE
- **Frontend**: Next.js 16, Assistant UI, Tailwind CSS
- **LLM**: OpenAI (GPT-4o-mini by default)

## Install Minimal From a Local Wheel

The portable minimal flavor serves the prebuilt UI and API from one Python
process at <http://localhost:8011/>. Node and pnpm are required only once to
build the UI; they are not needed to install or run the wheel.

```bash
# Build frontend-minimal and the local wheel from the repository root.
packages/agent-chat-minimal/scripts/build_wheel.sh

python3 -m venv .venv-minimal
.venv-minimal/bin/pip install packages/agent-chat-minimal/dist/*.whl
export OPENAI_API_KEY=sk-...
.venv-minimal/bin/minimal-chat-serve --port 8011
```

The UI, `GET /health`, and `POST /assistant` are all available on port 8011.
Without `OPENAI_API_KEY`, the UI and health check still work while
`/assistant` returns a structured 503 response.

Troubleshooting:

- Re-run `packages/agent-chat-minimal/scripts/build_wheel.sh` if the wheel
  contains a stale UI; the script
  replaces staged `web/` content on every build.
- Set `MINIMAL_WEB_DIR=/absolute/path/to/out` to test a different static export.
- A 503 from `/assistant` means `OPENAI_API_KEY` was not set before startup.

The two-service `docker-compose.minimal.yml` setup remains available for
frontend/backend development. The distributable wheel is the single-port,
Python-only runtime.

## Quick Start with Docker

### Prerequisites
- Docker & Docker Compose
- OpenAI API key

### Setup

1. Copy the environment file:
```bash
cp .env.example .env
```

2. Add your API keys to `.env`:
```
OPENAI_API_KEY=sk-...
SERPER_API_KEY=...
```

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

### Stop Services

```bash
# Press Ctrl+C or run:
docker-compose -f docker-compose.minimal.yml down
docker-compose -f docker-compose.full.yml down
```

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

## Project Structure

```
application/
├── backend/
│   ├── full/                          # Full-featured server
│   │   ├── fastlang/                  # Server package
│   │   └── start_server.sh            # Runs on port 8010
│   └── langgraph-server-minimal/      # Minimal server
│       ├── demo_agent/                 # Agent with tools
│       ├── server.py                   # Main server
│       └── start_server.sh            # Runs on port 8011
└── frontend/
    ├── frontend-full/                  # Full UI (port 3001)
    └── frontend-minimal/               # Minimal UI (port 3000)
packages/
└── agent-chat-minimal/                  # Portable local-wheel distribution
```

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
| `/health` | GET | Health check |
| `/threads` | GET | List all threads |
| `/threads` | POST | Create new thread |
| `/threads/{id}` | GET | Get thread details |
| `/threads/{id}/messages` | GET | Get thread messages |
| `/threads/{id}/messages` | POST | Append message |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI key required for chat; UI and health work without it |
| `SERPER_API_KEY` | Serper API key (required for `web_search` tool in full backend) |
| `EMBEDDING_PROVIDER` | Full-backend embedding provider (`fastembed` or `openai`) |
| `EMBEDDING_MODEL` | Optional embedding model override |
| `RAG_STARTUP_VALIDATION` | Set to `1` to run the network/model-dependent RAG preflight |
| `NEXT_PUBLIC_API_URL` | Minimal frontend backend URL |
| `NEXT_PUBLIC_API_BASE` | Full frontend backend base URL |
| `MINIMAL_WEB_DIR` | Optional static UI directory override for the minimal backend |

## Portable Minimal Follow-ups

The local-wheel epic intentionally leaves these as future work:

- Package the full flavor.
- Support `create_app(custom_graph)` graph injection.
- Publish releases to PyPI.

See [RUNNING.md](./RUNNING.md) for more detailed documentation.

## DOM-only UI Testing

Playwright tests and machine-readable inspection scripts for both frontends
live in [`tests/ui`](./tests/ui). They inspect DOM structure, ARIA, computed
styles, and layout geometry without screenshots or visual snapshots.

```bash
cd tests/ui
pnpm install
pnpm install:browsers
pnpm test
pnpm inspect:full
pnpm inspect:minimal
```
