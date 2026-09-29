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

## Built-In Documentation

The distribution includes these Markdown guides and exposes them without
unpacking the wheel:

```python
from agent_chat_minimal import docs

docs.list()
docs.show("agents")
```

| Guide | Purpose |
| --- | --- |
| `quickstart` | Install, run, and make the first request |
| `agents` | Implement, embed, and publish agents |
| `providers` | Model specs and provider dependencies |
| `configuration` | Environment variables, CLI, persistence, and hooks |
| `threads` | Thread and transcript behavior |
| `transport` | Assistant streaming transport boundary |
| `persistence` | Durable repositories and checkpoints |
| `runtime-config` | Runtime UI configuration and capabilities |

Run the package tests and artifact smoke test from the repository root:

```bash
python -m pip install "packages/agent-chat-minimal[test]"
pytest packages/agent-chat-minimal
packages/agent-chat-minimal/scripts/smoke_test_wheel.sh
```
