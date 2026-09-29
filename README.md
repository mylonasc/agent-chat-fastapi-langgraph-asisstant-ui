# LangGraph FastAPI Assistant UI

[![CI](https://github.com/mylonasc/agent-chat-fastapi-langgraph-asisstant-ui/actions/workflows/artifact-workflow.yml/badge.svg)](https://github.com/mylonasc/agent-chat-fastapi-langgraph-asisstant-ui/actions/workflows/artifact-workflow.yml)
[![PyPI version](https://img.shields.io/pypi/v/agent-chat-fastapi-langgraph-assistant-ui)](https://pypi.org/project/agent-chat-fastapi-langgraph-assistant-ui/)

A reference application for serving LangGraph agents through FastAPI with an
Assistant UI frontend. It has two intentionally different ways to run:

| Choose this | When you need | Entry point |
| --- | --- | --- |
| **Packaged app** | One Python process that serves a reusable agent API and bundled UI | `minimal-chat-serve` on port 8011 |
| **Docker Compose** | The repository's split frontend/backend development stacks | `docker-compose.*.yml` |

Start with the packaged app for a new deployment or a new non-RAG agent. Use
the Compose stacks when developing the legacy split applications, especially
the full RAG demo.

## Quick Start

Install the published package (Python 3.11+), configure a model credential,
and serve the bundled UI and API on one port:

```bash
python -m pip install agent-chat-fastapi-langgraph-assistant-ui
export OPENAI_API_KEY=sk-...
minimal-chat-serve --port 8011
```

Open <http://localhost:8011/>. `GET /health`, `GET /agents`, and FastAPI's
interactive API at <http://localhost:8011/docs> are available on the same
server. See the [packaged app guide](docs/packaged-app.md) for local builds,
durable SQLite storage, UI presets, configuration, and container use.

## Documentation

Read these in order for the shortest path through the repository:

- [Documentation map](docs/README.md): architecture and guide index.
- [Serve the packaged app](docs/packaged-app.md): install, build, configure,
  and deploy the canonical portable server.
- [Run with Docker Compose](docs/docker-compose.md): minimal and full split
  development stacks, ports, and environment variables.
- [Implement an agent](docs/implementing-agents.md): embed a graph, register a
  named agent, or publish an entry-point plugin.
- [Package README](packages/agent-chat-minimal/README.md): package-specific
  commands and the documentation shipped inside the wheel.

## Repository Map

```text
packages/agent-chat-minimal/        Canonical portable Python application
  src/agent_chat_minimal/           FastAPI composition, agent registry, UI assets
  scripts/                          Static UI staging, wheel build, artifact smoke test
application/backend/
  langgraph-server-minimal/         Compatibility entry point for the package
  full/                             Separate source-run RAG demo backend
application/frontend/
  frontend/                         Unified static UI built into the package
  frontend-minimal/, frontend-full/ Legacy split Compose frontends
docs/                               Maintainer and deployment guides
.agent-recon/                       Architecture reconnaissance and implementation history
```

The package owns the minimal server's routes, transport, settings, persistence,
and static UI behavior. `application/backend/langgraph-server-minimal` is a
thin compatibility composition root, not a second implementation. The full
backend is separate because it provides source-run Web Search/RAG tools that
the portable package does not include.

## Development Checks

Build the packaged artifact from a checkout (Node and pnpm are required only
for this build step):

```bash
packages/agent-chat-minimal/scripts/build_wheel.sh
python -m pip install "packages/agent-chat-minimal[test]"
pytest packages/agent-chat-minimal
packages/agent-chat-minimal/scripts/smoke_test_wheel.sh
```

The UI inspection and Playwright tests are documented in
[`tests/ui/README.md`](tests/ui/README.md). Historical design decisions and
implementation status live in [`.agent-recon/README.md`](.agent-recon/README.md);
they are maintainer context rather than the deployment guide.
