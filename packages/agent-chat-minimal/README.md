# Agent Chat Minimal

This local Python distribution bundles the fixed weather/graph demo agent,
FastAPI server, and a prebuilt static minimal chat UI. Node is needed only to
build the web payload, not to install or run the resulting wheel.

From the repository root, build the UI and wheel with:

```bash
packages/agent-chat-minimal/scripts/build_wheel.sh
```

The script runs the frozen pnpm install and static export, stages `out/` as
package data, and writes the wheel under `packages/agent-chat-minimal/dist/`.
Generated `web/` content and `dist/` are intentionally gitignored.

An editable source installation does not include generated `web/` files. To
serve the UI from a checkout, stage it first (or use the built wheel above):

```bash
packages/agent-chat-minimal/scripts/stage_ui.sh
python -m pip install -e "packages/agent-chat-minimal[persistence]"
minimal-chat-serve --port 8011
```

Install from PyPI (Python 3.11+, no Node required) and serve with:

```bash
pip install agent-chat-fastapi-langgraph-assistant-ui
minimal-chat-serve --port 8011
```

Install durable application persistence separately when needed:

```bash
pip install "agent-chat-fastapi-langgraph-assistant-ui[persistence]"
minimal-chat-migrate ./agent-chat.db
```

Or install and serve the locally built wheel with:

```bash
python -m pip install packages/agent-chat-minimal/dist/*.whl
minimal-chat-serve --port 8011
```

Open <http://localhost:8011/>. One static UI serves both presets: the
runtime preset (`UI_PRESET`, visible at `GET /api/config`) selects the
single-prompt chat or the thread sidebar with previous chats.
Set `OPENAI_API_KEY` to enable `/assistant`; without it, the UI and
`/health` still work and `/assistant` returns 503.
`MINIMAL_WEB_DIR` may override the bundled web directory
(`FULL_WEB_DIR` remains as a deprecated override hook and no longer
ships a bundle).

See [`../../docs/migration-to-packaged-app.md`](../../docs/migration-to-packaged-app.md)
for the canonical package migration path and legacy development-stack status.

For a durable full preset, install the persistence extra and configure both
separate SQLite files (the supported CLI/factory owns migrations and clean
shutdown):

```bash
pip install "agent-chat-fastapi-langgraph-assistant-ui[persistence]"
UI_PRESET=full DATABASE_PATH=./agent-chat.db \
CHECKPOINT_DATABASE_PATH=./agent-chat-checkpoints.db \
minimal-chat-serve --port 8011
```

## Arbitrary agents & providers

```python
from agent_chat_minimal import create_app
from my_agent import make_my_agent  # any compiled graph over {"messages": [...]}

app = create_app(graph=make_my_agent("anthropic:claude-sonnet-4-5"))
# or deferred: app = create_app(graph_factory=make_my_agent)
# or multi-agent: app = create_app(agents={"mine": make_my_agent})
```

- Models are `provider:name` specs via `init_chat_model`
  (`openai:gpt-4o-mini`, `anthropic:claude-sonnet-4-5`, `ollama:llama3.1`).
  Factories also accept a chat-model instance (handy for fake-model tests).
- Ollama needs `pip install "agent-chat-fastapi-langgraph-assistant-ui[ollama]"`.
  For a local server, use `MODEL=ollama:qwen3.8:latest`.
- `GET /agents` lists the registry (`weather`, `calculator`, plus
  `agent_chat.agents` entry points); `POST /assistant/{agent_id}` selects one,
  `POST /assistant` aliases the default.
- `create_app(..., prepare_state=fn)` overrides the message reducer;
  `state.thread_id` / `runConfig.thread_id` is forwarded as LangGraph
  `configurable.thread_id` for checkpointer-backed graphs.

## Documentation (in the wheel)

Guides ship inside the package and are readable at runtime:

```python
from agent_chat_minimal import docs
docs.list()           # ['index', 'quickstart', 'agents', ...]
docs.show("threads")
```

| Guide | Covers |
| ----- | ------ |
| `quickstart` | install → first chat in 2 minutes |
| `agents` | write + serve + share your own agent |
| `providers` | OpenAI / Anthropic / Ollama specs & creds |
| `configuration` | env vars, CLI flags, hooks, 503 semantics |
| `threads` | multi-thread chats, frontend-full compat |
| `transport` | pinned Python/frontend protocol boundary and replacement criteria |
| `persistence` | principal, domain ports, service authorization, and deletion semantics |

## Threads (full-preset compatible)

The server also speaks the full-stack thread protocol (`/threads`,
`/threads/{id}/messages`, scoped `POST /assistant` with `thread_id`/`user_id`),
so the full preset (and the legacy `frontend-full` dev app) works against
either backend. See the `threads` guide.

## Configuration

```text
HOST=0.0.0.0                # uvicorn bind host
PORT=8011                   # uvicorn bind port
MODEL=openai:gpt-4o-mini    # provider:model spec
DEFAULT_AGENT=weather       # registry id aliased by POST /assistant
MINIMAL_WEB_DIR=            # override bundled web/ (empty = bundled)
UI_PRESET=minimal           # runtime UI preset: minimal or full
DATABASE_PATH=agent-chat.db # default application SQLite file
DATABASE_URL=               # SQLAlchemy URL; overrides DATABASE_PATH
CHECKPOINT_DATABASE_PATH=agent-chat-checkpoints.db # graph checkpoint SQLite file
CHECKPOINT_DATABASE_URL=    # SQLite URL; overrides checkpoint path
AUTO_MIGRATE=true           # migration policy for a future composition root
OPENAI_API_KEY=             # credential for the default openai model
ANTHROPIC_API_KEY=          # credential when MODEL uses anthropic:
```

CLI mirrors it: `minimal-chat-serve --model ollama:llama3.1 --agent calculator`,
plus `--check` to build the default graph and exit without booting uvicorn.

Run the offline serving tests and clean-venv smoke check from the repository
root:

```bash
python3 -m venv /tmp/agent-chat-minimal-tests
/tmp/agent-chat-minimal-tests/bin/pip install \
  "packages/agent-chat-minimal[test]"
/tmp/agent-chat-minimal-tests/bin/pytest packages/agent-chat-minimal
packages/agent-chat-minimal/scripts/smoke_test_wheel.sh
```

Build the Python-only runtime image after building the wheel:

```bash
docker build -t agent-chat-minimal packages/agent-chat-minimal
docker run --rm -p 8011:8011 agent-chat-minimal
```
