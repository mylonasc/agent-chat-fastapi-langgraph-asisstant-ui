# Running The Application

This file is retained for existing links. The current documentation is organized
by deployment choice rather than by the former minimal/full labels:

- [Serve the packaged app](docs/packaged-app.md): recommended single-process,
  single-port deployment for the canonical non-RAG application.
- [Run with Docker Compose](docs/docker-compose.md): split frontend/backend
  development stacks for the minimal compatibility app and separate full RAG
  demo.
- [Implement an agent](docs/implementing-agents.md): embed, register, or
  publish a LangGraph agent plugin.
- [Documentation map](docs/README.md): repository architecture and all guides.

## Fastest Start

```bash
python -m pip install agent-chat-fastapi-langgraph-assistant-ui
export OPENAI_API_KEY=sk-...
minimal-chat-serve --port 8011
```

Open <http://localhost:8011/>. The same process provides the UI, `GET /health`,
`GET /agents`, and FastAPI documentation at `GET /docs`.

## Compose Start

```bash
cp .env.example .env
docker-compose -f docker-compose.minimal.yml up --build
# or the separate RAG demo:
docker-compose -f docker-compose.full.yml up --build
```

The minimal split UI is at <http://localhost:3000>; the full RAG demo UI is at
<http://localhost:3001>.
