# Serve The Packaged App

`agent-chat-fastapi-langgraph-assistant-ui` is the canonical portable non-RAG
application. It serves FastAPI, the Assistant UI static export, and agents from
one process and one origin. The default port is 8011.

## Install And Run

The published distribution needs Python 3.11+; Node and pnpm are not runtime
dependencies.

```bash
python -m pip install agent-chat-fastapi-langgraph-assistant-ui
export OPENAI_API_KEY=sk-...
minimal-chat-serve --port 8011
```

Visit <http://localhost:8011/>. Useful endpoints are `GET /health`, `GET
/agents`, `POST /assistant`, `POST /assistant/{agent_id}`, and `GET /docs`.
Without a credential, the UI and health endpoint still load; an agent request
returns a structured `503 agent_not_ready` response.

The default model is `openai:gpt-4o-mini` and the default agent is `weather`.
Change either at launch:

```bash
minimal-chat-serve --model anthropic:claude-sonnet-4-5 --agent calculator
minimal-chat-serve --agent weather --check
```

`--check` constructs the selected default agent and exits. Install the matching
provider extra when needed, for example
`python -m pip install "agent-chat-fastapi-langgraph-assistant-ui[ollama]"`.
See the package's [provider guide](../packages/agent-chat-minimal/src/agent_chat_minimal/docs/providers.md)
for supported model specifications and credentials.

## Build From This Repository

Use this when changing the unified frontend or packaging code. The build stages
`application/frontend/frontend/out` into the Python package and creates a
wheel. It requires `uv`, Node, pnpm, and the frontend's locked dependencies.

```bash
packages/agent-chat-minimal/scripts/build_wheel.sh
python -m venv .venv-agent-chat
.venv-agent-chat/bin/pip install packages/agent-chat-minimal/dist/*.whl
OPENAI_API_KEY=sk-... .venv-agent-chat/bin/minimal-chat-serve --port 8011
```

For an editable source installation, stage the UI first. Otherwise the source
server intentionally starts API-only:

```bash
packages/agent-chat-minimal/scripts/stage_ui.sh
python -m pip install -e "packages/agent-chat-minimal[persistence]"
minimal-chat-serve --port 8011
```

## Configuration And Persistence

The primary settings are `MODEL`, `DEFAULT_AGENT`, `UI_PRESET`, `HOST`, and
`PORT`. `UI_PRESET=minimal` is the default; `UI_PRESET=full` enables the
thread-oriented layout from the same bundled UI. `MINIMAL_WEB_DIR` overrides
the bundled static directory for local frontend testing.

The server is in-memory by default. Enable the supported durable SQLite
composition by installing the persistence extra and setting paths or URLs:

```bash
python -m pip install "agent-chat-fastapi-langgraph-assistant-ui[persistence]"
PERSISTENCE_ENABLED=true UI_PRESET=full \
DATABASE_PATH=./agent-chat.db \
CHECKPOINT_DATABASE_PATH=./agent-chat-checkpoints.db \
minimal-chat-serve --port 8011
```

Use separate application and LangGraph checkpoint databases. Full configuration,
ASGI factory use, and persistence lifecycle details are in the
[package configuration guide](../packages/agent-chat-minimal/src/agent_chat_minimal/docs/configuration.md).

## Container Image

Build the wheel first, then build the runtime image. The image installs the
wheel and runs `minimal-chat-serve`; it does not build frontend assets.

```bash
packages/agent-chat-minimal/scripts/build_wheel.sh
docker build -t agent-chat-minimal packages/agent-chat-minimal
docker run --rm -p 8011:8011 -e OPENAI_API_KEY agent-chat-minimal
```

For adding agents, continue with [Implementing agents](implementing-agents.md).
