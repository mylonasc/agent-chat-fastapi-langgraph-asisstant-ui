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
# Edit .env and set your model credentials, then:
./scripts/run_demo --minimal
# or the separate RAG demo:
./scripts/run_demo --full
```

The minimal split UI is at <http://localhost:3000>; the full layout is at
<http://localhost:3001>. The launcher rebuilds the current local checkout.
Use `--detach` for background startup, `--logs` to follow logs, and `--stop`
to stop the selected setup. Run `./scripts/run_demo --help` for all options.

**Naming update:** `full` selects the full UI, not a RAG backend. Both setups
use the common packaged backend and basic tools by default. Use
`--toolsets calculator,web_search,web_rag` explicitly for RAG/search. See
[Toolsets](docs/toolsets.md) for runtime controls and configuration.

## Without Docker

With uv, Node.js 20.9+, pnpm 10, and a configured `.env`:

```bash
./scripts/run_demo --minimal --local
./scripts/run_demo --full --local
```

This installs locked dependencies and runs the latest backend/frontend source
with hot reload. Ctrl-C stops both servers. Use `--ui-port` and `--api-port`
to avoid conflicts with an existing Docker demo. See the
[local development guide](docs/local-development.md) for details.
