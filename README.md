# LangGraph FastAPI Assistant UI

[![CI](https://github.com/mylonasc/agent-chat-fastapi-langgraph-asisstant-ui/actions/workflows/artifact-workflow.yml/badge.svg)](https://github.com/mylonasc/agent-chat-fastapi-langgraph-asisstant-ui/actions/workflows/artifact-workflow.yml)
[![PyPI version](https://img.shields.io/pypi/v/agent-chat-fastapi-langgraph-assistant-ui)](https://pypi.org/project/agent-chat-fastapi-langgraph-assistant-ui/)

A reference application for serving LangGraph agents through FastAPI with an
Assistant UI frontend. It has two intentionally different ways to run:

| Choose this | When you need | Entry point |
| --- | --- | --- |
| **Packaged app** | One Python process that serves a reusable agent API and bundled UI | `minimal-chat-serve` on port 8011 |
| **Docker Compose** | The repository's split frontend/backend development stacks | `docker-compose.*.yml` |

Start with the packaged app for deployment. For current source development,
use the demo launcher with either layout and explicitly selected toolsets.

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

To test the latest local checkout with Docker, configure `.env` from
`.env.example`, then run:

```bash
./scripts/run_demo --minimal          # http://localhost:3000
./scripts/run_demo --full             # http://localhost:3001 (full layout)
./scripts/run_demo --full --detach    # start in the background
./scripts/run_demo --full --local     # without Docker; requires uv, Node, pnpm
./scripts/run_demo --runtime local --ui full --toolsets calculator,weather,graph
./scripts/run_demo --help
```

Docker mode rebuilds images from your local source by default. See the
[Compose guide](docs/docker-compose.md#local-demo-launcher) for logs and shutdown.
For native source development with hot reload, see
[Run without Docker](docs/local-development.md).

**Layout and tools are independent.** Both demo layouts use basic tools by
default; add `web_search,web_rag` explicitly when wanted. **Manage toolsets**
provides durable administrator controls; **Conversation tools** selects a
permitted subset for each conversation. See [Toolsets and runtime configuration](docs/toolsets.md)
for shared packaged/local/Docker naming, configuration knobs, and authorization.

For a ready-to-run local Ollama chat UI (no API key), see
[Local Ollama Chat](application/ollama-chat/README.md). It uses the built library,
streams responses, and saves conversations locally.

### For Coding Agents

**Local Ollama chat:** start with the
[copy-paste Ollama quick start](packages/agent-chat-minimal/src/agent_chat_minimal/docs/ollama-quickstart.md).
It covers Python 3.12, model availability, the current no-custom-code starter,
endpoint configuration, durable history, and live checks. Issue #70's tool-free
`--agent chat` shortcut is not implemented on this branch.

The installed package provides offline discovery, searchable guides, and a safe
project initializer—no repository checkout or frontend build is needed:

```bash
minimal-chat-setup describe --json
minimal-chat-docs show agent-onboarding
minimal-chat-docs search "provider" --json
minimal-chat-init ./my-site --preset full --dry-run --json
minimal-chat-init ./my-site --preset full --json
```

Generated projects include `AGENTS.md`, editable agent code, configuration,
offline tests, and structured next steps. Installation, credentials, and starting
services remain explicit actions. `/docs` is the running server's API reference;
`minimal-chat-docs` reads the library guides bundled with your installed version.

### Guides

Read these in order for the shortest path through the repository:

- [Documentation map](docs/README.md): architecture and guide index.
- [Serve the packaged app](docs/packaged-app.md): install, build, configure,
  and deploy the canonical portable server.
- [Run with Docker Compose](docs/docker-compose.md): minimal and full split
  development stacks, ports, and environment variables.
- [Implement an agent](docs/implementing-agents.md): embed a graph, register a
  named agent, or publish an entry-point plugin.
- [Monitor the full agent with OpenInference + Phoenix](application/backend/full/examples/phoenix_monitoring/README.md):
  an opt-in local tracing example for the RAG backend.
- [Package README](packages/agent-chat-minimal/README.md): package-specific
  commands and the documentation shipped inside the wheel.

## Repository Map

```text
packages/agent-chat-minimal/        Canonical portable Python application
  src/agent_chat_minimal/           FastAPI composition, agent registry, UI assets
  scripts/                          Static UI staging, wheel build, artifact smoke test
application/backend/
  langgraph-server-minimal/         Compatibility entry point for the package
  full/                             Legacy source-run RAG server/examples
application/frontend/
  frontend/                         Unified packaged and Compose UI (both presets)
docs/                               Maintainer and deployment guides
.agent-recon/                       Architecture reconnaissance and implementation history
```

The package owns the shared server, toolset policy, optional web integrations,
persistence, and static UI behavior. Both demo layouts use this backend.
`application/backend/langgraph-server-minimal` and the old RAG tools namespace
are compatibility entry points; legacy RAG examples remain under `full/`.

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
