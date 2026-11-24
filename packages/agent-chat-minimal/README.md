# Agent Chat Minimal

`agent-chat-fastapi-langgraph-assistant-ui` is the portable, canonical non-RAG
application in this repository. It bundles a FastAPI server, LangGraph agent
registry, and one static Assistant UI export. A built wheel serves the UI and
API from one Python process on port 8011.

For repository-level orientation, start at the [root README](../../README.md).
The detailed serving and extension guides are:

- [Serve the packaged app](../../docs/packaged-app.md)
- [Implement an agent](../../docs/implementing-agents.md)
- [Run the split Docker Compose stacks](../../docs/docker-compose.md)

## Install And Serve

Python 3.11+ is required. Node and pnpm are needed to build a wheel from a
checkout, but never to install or run the published package.

```bash
python -m pip install agent-chat-fastapi-langgraph-assistant-ui
export OPENAI_API_KEY=sk-...
minimal-chat-serve --port 8011
```

Open <http://localhost:8011/>. `GET /health`, `GET /agents`, and `GET /docs`
are available on the same server. The default agent is `weather`; use
`minimal-chat-serve --agent calculator` or set `DEFAULT_AGENT` to select a
different registered agent.

## Build From A Checkout

The build stages the unified frontend at `application/frontend/frontend` as
package data, clears `dist/`, and creates the wheel:

```bash
packages/agent-chat-minimal/scripts/build_wheel.sh
python -m pip install packages/agent-chat-minimal/dist/*.whl
minimal-chat-serve --port 8011
```

For an editable install, run `scripts/stage_ui.sh` first; generated `web/`
content is intentionally ignored by Git. Without it, a checkout runs API-only
unless `MINIMAL_WEB_DIR` points to a static export.

## Editable UI Sources

The wheel ships the prebuilt UI only. The sdist is the editable-UI version:
it also contains the full TypeScript/Next.js sources under `ui-src/frontend`.
Extract it, rebuild, and serve the result via `MINIMAL_WEB_DIR`:

```bash
pip download --no-binary :all: agent-chat-fastapi-langgraph-assistant-ui
tar -xzf agent-chat-fastapi-langgraph-assistant-ui-*.tar.gz
cd agent-chat-fastapi-langgraph-assistant-ui-*/ui-src/frontend
pnpm install --frozen-lockfile && pnpm build
MINIMAL_WEB_DIR=$PWD/out minimal-chat-serve --port 8011
```

See the in-package `editable-ui` guide (`docs.show("editable-ui")`) for notes
and limits.

## Built-In Documentation

Coding agents can start with these offline commands:

```bash
minimal-chat-setup describe --json
minimal-chat-docs show ollama-quickstart  # local model → baseline site
minimal-chat-docs show agent-onboarding
minimal-chat-docs search "persistence" --json
minimal-chat-setup doctor --provider openai --preset full --json
minimal-chat-init ./my-site --preset full --dry-run --json
minimal-chat-init ./my-site --preset full --json
```

Generation produces an editable chat site with `AGENTS.md`, configuration,
offline tests, and machine-readable next steps. It does not install dependencies,
provision credentials, or launch services. See the bundled `starter` guide.

The distribution includes these Markdown guides and exposes them without
unpacking the wheel:

```python
from agent_chat_minimal import docs

docs.list()
docs.show("agents")
```

| Guide | Purpose |
| --- | --- |
| `index` | Complete guide index |
| `agent-onboarding` | Agent discovery and baseline website workflow |
| `ollama-quickstart` | Fast local-model setup, endpoints, SQLite, and live checks |
| `quickstart` | Install, run, and make the first request |
| `agents` | Implement, embed, and publish agents |
| `providers` | Model specs and provider dependencies |
| `configuration` | Environment variables, CLI, persistence, and hooks |
| `threads` | Thread and transcript behavior |
| `transport` | Assistant streaming transport boundary |
| `persistence` | Durable repositories and checkpoints |
| `runtime-config` | Runtime UI configuration and capabilities |
| `setup` | Setup contracts, provider metadata, and diagnostics |
| `starter` | Generate and run an editable project |
| `editable-ui` | Rebuild and serve an edited UI from the sdist sources |

Run the package tests and artifact smoke test from the repository root:

```bash
python -m pip install "packages/agent-chat-minimal[test]"
pytest packages/agent-chat-minimal
packages/agent-chat-minimal/scripts/smoke_test_wheel.sh
```
