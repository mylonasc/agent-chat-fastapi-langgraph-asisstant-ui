# Configuration

Single source of truth: `Settings` in `config.py` (stdlib only, no extra
dependency). CLI flags override env vars.

## Environment

```text
HOST=0.0.0.0                # uvicorn bind host
PORT=8011                   # uvicorn bind port
MODEL=openai:gpt-4o-mini    # provider:model spec (see providers.md)
DEFAULT_AGENT=weather       # registry id aliased by POST /assistant
MINIMAL_WEB_DIR=            # override bundled web/ (empty = bundled)
FULL_WEB_DIR=               # deprecated mount hook (no bundle ships)
UI_PRESET=minimal           # runtime UI preset: minimal or full
API_BASE=                   # same-origin default; absolute http(s) URL for split-port dev
IDENTITY_MODE=anonymous     # anonymous or delegated (custom principal resolver)
DATABASE_PATH=agent-chat.db # default application SQLite file
DATABASE_URL=               # SQLAlchemy URL; overrides DATABASE_PATH
CHECKPOINT_DATABASE_PATH=agent-chat-checkpoints.db # separate graph state file
CHECKPOINT_DATABASE_URL=    # SQLite URL; overrides CHECKPOINT_DATABASE_PATH
AUTO_MIGRATE=true           # migration policy for a composition root
PERSISTENCE_ENABLED=false   # explicitly open durable SQLite app/checkpoint stores
OPENAI_API_KEY=             # credential for the default openai model
ANTHROPIC_API_KEY=          # credential when MODEL uses anthropic:
```

The machine-readable contract is `agent_chat_minimal/schemas/agent_chat.schema.json`
(`version: 1`, also via `get_config_schema()` for wizard/editor use). Public
Python hooks: `Settings.from_yaml` / `Settings.load`, `create_app`,
`create_configured_app`, `ModelConfig`/`resolve_model`, `bundled_ui_dir`,
and the `agent_chat_minimal.setup` validation/diagnostic API.

```python
from agent_chat_minimal import Settings, create_app, create_configured_app

settings = Settings.from_env()
app = create_app(settings=settings)

# Custom agents with package-owned in-memory or SQLite resources. The same
# mapping works in both modes; durable stores open during lifespan and are
# disposed at shutdown.
custom = create_configured_app(settings, agents={"helper": make_helper_agent})
```

`create_configured_app(settings, agents=..., default_agent=...)` is the public
composition API for generated projects and embedders. It forwards explicit
Python agent mappings through the same route/service/transport implementation
as `create_app`, validates `default_agent` membership, and passes
`settings.model` explicitly to built-in factories. It never mutates process
environment state, so independent app instances can use different models in one
process. Legacy no-argument factories that read `MODEL` themselves keep working
through the documented environment fallback.

## Message id contract

Message ids are opaque strings shared by the UI runtime, transcript rows,
and feedback rows — and they must be unique per message and never bare
integers. The server mints human echo ids as `u-<hex>` for exactly this
reason: per-conversation counters (`"0"`, `"2"`, …) repeat in every thread,
so transcript appends collide across threads (409) and feedback can resolve
to another thread's row; worse, the Assistant UI runtime keys its message
resources through plain JS objects, whose key ordering puts integer-like
keys first regardless of insertion order — mixing `"0"`/`"2"` user ids with
`"ai-…"` assistant ids silently reorders multi-turn threads (users grouped
before assistants). Custom `prepare_state` reducers that assign their own
human ids must follow the same contract (unique, non-bare-integer); ids
supplied on `add-message` commands are kept verbatim.

`GET /api/config` serves the versioned runtime UI contract derived from these
settings and the capability provider (see [runtime-config.md](runtime-config.md)).
It is computed per request with `Cache-Control: no-store` so deployments stay
tunable after the wheel is built.

`Settings.resolved_database_url()` returns `DATABASE_URL` when set, otherwise
an absolute `sqlite+aiosqlite` URL for `DATABASE_PATH`. The HTTP app defaults
to in-memory repositories (no files, no side effects); a composition root
opens repositories itself and passes them in (see below). Use
`settings.auto_migrate` to choose whether to pass `migrate=True` to
`SQLiteRepositories.open(...)`.

`Settings.resolved_checkpoint_database_url()` independently resolves
`CHECKPOINT_DATABASE_URL` or `CHECKPOINT_DATABASE_PATH`. It must not point at
the application session database. Open `LangGraphSQLiteCheckpoints` separately
and pass it as `checkpoint_deleter=` (session deletion) plus
`checkpointer=<adapter.checkpointer>` (graph factories).

## Durable packaged app

The supported CLI and ASGI factory remain in-memory by default. Enable durable
SQLite composition explicitly with `PERSISTENCE_ENABLED=true`, or by explicitly
setting any application/checkpoint database path or URL. Install the optional
dependencies first:

```bash
pip install "agent-chat-fastapi-langgraph-assistant-ui[persistence]"
UI_PRESET=full DATABASE_PATH=./agent-chat.db \
CHECKPOINT_DATABASE_PATH=./agent-chat-checkpoints.db \
minimal-chat-serve --port 8011
```

The entry point opens a migrated `SQLiteRepositories` application database and
a separate `LangGraphSQLiteCheckpoints` database during FastAPI lifespan,
injects both into routes/graph factories, and disposes them at shutdown. Set
`AUTO_MIGRATE=false` to require a deployment-time
`minimal-chat-migrate ./agent-chat.db` instead; it never upgrades implicitly.
Missing optional dependencies fail startup with the exact persistence-extra
install command. The legacy `application/backend/full` remains a development
implementation and is not made durable by its current data volume; migrate
deployments to the packaged app.

```python
from agent_chat_minimal.adapters.langgraph_sqlite import LangGraphSQLiteCheckpoints
from agent_chat_minimal.adapters.sqlite import SQLiteRepositories

repos = await SQLiteRepositories.open(settings.resolved_database_url())
checkpoints = await LangGraphSQLiteCheckpoints.open(
    settings.resolved_checkpoint_database_url()
)
app = create_app(
    repositories=repos,
    checkpoint_deleter=checkpoints,
    checkpointer=checkpoints.checkpointer,
)
```

## CLI

```bash
minimal-chat-serve --host 127.0.0.1 --port 8011 \
  --model ollama:llama3.1 --agent calculator
minimal-chat-serve --config ./agent_chat.yaml --agent weather
minimal-chat-serve --agent weather --check   # build graph, exit, no server
```

`--config` loads a versioned YAML file (`version: 1`); `AGENT_CHAT_CONFIG`
selects one explicitly without flags. `--check` builds the configured default
agent with `settings.model` and exits, without starting the server or making
network calls beyond model construction.

`--check` is the fast CI smoke test: non-zero exit with the real factory
error when credentials are missing.

## Hooks (`create_app(...)`)

| Parameter        | Purpose                                            |
| ---------------- | -------------------------------------------------- |
| `graph=`         | Serve one prebuilt graph (`/agents == ["default"]`)|
| `graph_factory=` | Deferred single-graph build (errors at startup)    |
| `agents=`        | Name → factory map (multi-agent mode)              |
| `default_agent=` | Id aliased by `POST /assistant`                    |
| `web_dir=`       | Override the bundled UI directory (empty = bundled; missing = API-only) |
| `prepare_state=` | `(state, request) -> message dicts` reducer        |
| `checkpointer=`  | Shared checkpointer (`"memory"` default, see below)|
| `web_full_dir=`  | Deprecated mount hook (no bundle ships; `/full` is gone) |
| `repositories=`  | Bundle with `sessions`/`transcripts`/`feedback` (memory default; pass SQLite for durability) |
| `session_service=`/`transcript_service=` | Override application services (tests) |
| `principal_resolver=` | Request → trusted principal (default: `x-agent-chat-subject` header, `default_user` fallback) |
| `checkpoint_deleter=` | Checkpoint port wired into session deletion |
| `thread_manager=`/`message_store=` | Deprecated; contents are migrated into the services |
| `settings=`      | Validated deployment settings; explicit keywords override it |

For an ASGI server, use the side-effect-free factory entry point:

```bash
uvicorn agent_chat_minimal:create_default_app --factory
```

Resolve the installed prebuilt UI at startup with `bundled_ui_dir("minimal")`
or `bundled_ui_dir("full")` instead of capturing an absolute path at
generation time. `resolve_ui_dir(override, preset)` maps an empty override to
the bundle; a missing bundle starts in API-only mode (`/api/config` and
`/assistant` keep working, static routes are disabled).

## Checkpointer

`"memory"` (default) builds one shared `MemorySaver` and passes it to every
factory whose signature accepts `checkpointer`. Per-`thread_id` graph state
then persists across requests (see [threads.md](threads.md)). Pass an explicit
saver instance for custom backends, or `None` to disable injection.

For durable local graph state, install the `persistence` extra, open
`LangGraphSQLiteCheckpoints`, and pass its `checkpointer` property to the app or
graph factories (plus the adapter itself as `checkpoint_deleter=` so session
deletion removes graph state).

## `/assistant` 503 semantics

Agent factory failures return
`{"error": "agent_not_ready", "message": ..., "hint": ...}` with the real
provider or factory exception in `hint`. The server does not assume that the
selected model uses OpenAI; Ollama, Anthropic, and other configured providers
are initialized by their own factories.

## Source checkout UI and local Ollama

The generated `web/` directory is intentionally not tracked. An editable
checkout therefore starts API-only until
`packages/agent-chat-minimal/scripts/stage_ui.sh` runs, or until
`MINIMAL_WEB_DIR` points at a static export. Built wheels already contain the
UI. For a local provider install the `ollama` extra and set, for example,
`MODEL=ollama:qwen3.8:latest`; no OpenAI credential is needed.
