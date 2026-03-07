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

2. Edit `.env` and add your OpenAI API key:
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

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Your OpenAI API key (required) |
| `NEXT_PUBLIC_API_URL` | Backend URL (frontend only, optional in Docker) |

## Tech Stack

- **Backend**: FastAPI, LangGraph, Assistant Stream CE
- **Frontend**: Next.js 16, Assistant UI, Tailwind CSS
- **LLM**: OpenAI (GPT-4o-mini by default)
