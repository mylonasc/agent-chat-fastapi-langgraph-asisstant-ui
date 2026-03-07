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

## Quick Start with Docker

### Prerequisites
- Docker & Docker Compose
- OpenAI API key

### Setup

1. Copy the environment file:
```bash
cp .env.example .env
```

2. Add your OpenAI API key to `.env`:
```
OPENAI_API_KEY=sk-...
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
| `/threads` | GET | List all threads |
| `/threads` | POST | Create new thread |
| `/threads/{id}` | GET | Get thread details |
| `/threads/{id}/messages` | GET | Get thread messages |
| `/threads/{id}/messages` | POST | Append message |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Your OpenAI API key (required) |
| `NEXT_PUBLIC_API_URL` | Backend URL (frontend only) |

See [RUNNING.md](./RUNNING.md) for more detailed documentation.
