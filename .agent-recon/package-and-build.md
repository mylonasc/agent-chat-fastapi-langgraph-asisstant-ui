# Packaged Library, Build, and Release Reconnaissance

## Package Map

The published distribution is rooted at `packages/agent-chat-minimal` even
though it now includes both UI flavors and threaded backend functionality.

Important files:

- `packages/agent-chat-minimal/pyproject.toml`: metadata, dependencies, entry
  point, Hatch wheel/sdist configuration.
- `packages/agent-chat-minimal/src/agent_chat_minimal/server.py`: FastAPI app
  factory, streaming, thread routes, static mounts, CLI, module-level app.
- `packages/agent-chat-minimal/src/agent_chat_minimal/config.py`: `Settings`
  and environment documentation.
- `packages/agent-chat-minimal/src/agent_chat_minimal/registry.py`: built-in
  agents and `agent_chat.agents` entry-point discovery.
- `packages/agent-chat-minimal/src/agent_chat_minimal/threads.py`: in-memory
  metadata and Assistant UI message stores.
- `packages/agent-chat-minimal/src/agent_chat_minimal/docs.py`: packaged
  Markdown resource access.
- `packages/agent-chat-minimal/src/agent_chat_minimal/demo_agent/`: weather,
  calculator, graph tool, provider-independent agent factory.
- `packages/agent-chat-minimal/scripts/build_wheel.sh`: builds both Next static
  exports, stages them under the Python package, and builds the wheel.
- `packages/agent-chat-minimal/scripts/smoke_test_wheel.sh`: installs and runs
  a wheel without Node on `PATH`.
- `.github/workflows/publish-workflow.yml`: release build and PyPI publish.

Static output is staged into:

- `src/agent_chat_minimal/web/` for the minimal UI.
- `src/agent_chat_minimal/web_full/` for the full UI.

Only `.gitkeep` is tracked in those directories. Hatch force-includes generated
assets in wheels and sdists (`pyproject.toml:41-52`).

## Public API

`src/agent_chat_minimal/__init__.py:16-51` exports:

- `__version__`
- `AGENT_REGISTRY`
- `ENV_DOC`
- `ChatGraph`
- `DEFAULT_WEB_DIR`
- `DEFAULT_WEB_FULL_DIR`
- `ScopedChatRequest`
- `Settings`
- `ThreadManager`
- `ThreadMessageStore`
- `ThreadMetadata`
- `create_app`
- `default_prepare_state`
- `discover_agents`
- `docs`
- `main`
- `resolve_thread_id`

Version `0.3.5` is duplicated manually in `pyproject.toml:5-8` and
`__init__.py:31`.

`create_app()` (`server.py:234-282`) supports:

- a prebuilt `graph`;
- a deferred `graph_factory`;
- a named multi-agent `agents` map;
- a default agent;
- custom minimal/full static directories;
- a custom state reducer;
- an injected checkpointer;
- injected thread metadata and message stores.

The package also creates a module-level ASGI app at `server.py:615` and exposes
`minimal-chat-serve` from `pyproject.toml:27-28`. CLI options are `--host`,
`--port`, `--model`, `--agent`, and `--check` (`server.py:618-656`).

## Agent Registry

Built-ins `weather` and `calculator` are registered in `registry.py:21-40`.
Third parties use the `agent_chat.agents` entry-point group
(`registry.py:43-61`). Built-ins win duplicate names.

`demo_agent/agent_factory.py:16-67` accepts a model string or `BaseChatModel`,
binds tools, builds an `agent -> tools -> agent` graph, and optionally compiles
with a checkpointer.

When a caller passes `agents={...}`, the supplied map replaces built-ins; it is
not merged. `docs/agents.md:41-46` currently documents the opposite behavior.

## HTTP Surface

Core routes in `server.py`:

- `GET /health` (`371-373`)
- `GET /agents` (`375-377`)
- `POST /assistant` (`565-567`)
- `POST /assistant/{agent_id}` (`569-571`)
- thread CRUD/list/archive routes (`381-442`)
- `GET /threads/{id}/messages` (`444-465`)
- `POST /threads/{id}/messages` (`467-470`)
- `/full` static mount (`573-594`)
- `/` static mount (`596-610`)

`SPAStaticFiles` (`server.py:44-69`) falls back to `index.html` for client-side
routes. `/full` must be mounted before `/` because Starlette uses registration
order.

## Request and Streaming Flow

1. `ScopedChatRequest` extends dependency-owned `ChatRequest` with `thread_id`
   and `user_id` (`server.py:72-77`).
2. Agent sources are selected with prebuilt/factory first, then caller map, then
   discovered agents (`server.py:285-315`).
3. Default checkpointing is `MemorySaver` (`server.py:228-231`, `288-289`).
4. Graph instances are cached after successful construction
   (`server.py:324-343`).
5. Single-agent factories are eagerly built (`server.py:345-358`).
6. Thread metadata is created or loaded (`server.py:511-519`).
7. `default_prepare_state()` turns text `add-message` commands into LangChain
   human messages (`server.py:119-133`).
8. Invalid AI tool-call history is sanitized (`server.py:195-225`).
9. LangGraph streams `messages`, `updates`, and `custom` events
   (`server.py:533-560`).
10. `assistant-stream-ce` creates and serializes the response
    (`server.py:562-563`).

## Thread Storage

There are three independent stores:

- `ThreadManager` metadata (`threads.py:33-87`).
- `ThreadMessageStore` Assistant UI JSON (`threads.py:90-111`).
- LangGraph checkpoint state.

Defaults are in-memory and process-local. `GET /threads/{id}/messages` first
checks UI JSON and then falls back to `graph.get_state()` (`server.py:444-465`).

Thread ownership is not enforced. Listing accepts a `user_id`, but fetch,
rename, archive, delete, and message operations require only an ID. A caller
that knows an ID can operate on it.

## Build and Publication

The local build (`scripts/build_wheel.sh:4-33`):

1. Registers cleanup for staged assets.
2. Runs frozen installs/builds for both frontends.
3. Builds full UI with same-origin API calls and `/full` base path.
4. Copies `out/` trees into Python package data.
5. Runs `uv build --wheel`.

The smoke script (`scripts/smoke_test_wheel.sh:19-45`) creates a temporary
venv, installs `dist/*.whl`, removes Node from `PATH`, starts the server, checks
`/health`, checks root HTML, and expects a no-key `/assistant` failure. It does
not test `/full/`, packaged docs, entry points, discovery, or a successful
offline stream.

Publish workflow behavior (`.github/workflows/publish-workflow.yml`):

- Triggered by release publication or manual dispatch (`23-27`).
- Uses Node 22, pnpm 10.20.0, Python 3.11, and trusted publishing (`35-60`).
- Builds and stages both UIs (`62-82`).
- Compares release tag and project version for conventional release tags
  (`84-99`).
- Installs source plus tests and runs pytest before building (`101-107`).
- Builds wheel and sdist (`109-113`).
- Runs `twine check` and verifies two `index.html` archive members
  (`115-140`).
- Publishes via OIDC (`142-146`).

The final wheel is not installed/exercised in publication CI. The existing
smoke script is not invoked there.

## Repository/Package Drift

The development minimal backend at
`application/backend/langgraph-server-minimal/server.py` is an older,
independent implementation with only health, assistant, and minimal static
serving. It lacks registry, threads, full UI, injection, provider abstraction,
and checkpointing. Its graph ignores its model argument and hard-codes
`gpt-4o-mini` (`demo_agent/get_graph.py:25-33`).

The full backend independently duplicates thread CRUD, streaming, state
reduction, checkpointer setup, and static/API behavior. It adds Web Search/RAG
routers under `/tools/*` (`application/backend/full/fastlang/server/server.py:
56-107`).

The wheel uses the same full frontend, but the package does not expose those
tool routes. The full UI therefore displays admin/RAG functions that cannot
work against the packaged server. Worse, `tools` is not a reserved SPA prefix,
so missing `/tools/*` requests can receive root `index.html` instead of JSON
404 (`server.py:46-69`).

Root docs are stale. `README.md:175-181` and `RUNNING.md:57-63` describe
packaged full UI, custom graphs, and PyPI publication as future work even though
they exist.

## Concrete Defects

### Thread ID Resolution

`resolve_thread_id()` supports top-level, state, and `runConfig` IDs
(`server.py:136-152`), and README documentation advertises `runConfig`. The
real assistant route duplicates only top-level/state logic (`server.py:511-519`)
and never calls the helper. Existing tests validate the helper separately but
not route integration.

### Provider Gating

`server.py:482-488` rejects the default weather agent without
`OPENAI_API_KEY`, regardless of `MODEL`. This blocks documented Ollama or
Anthropic use.

### Full UI Capability Mismatch

`frontend-full/app/admin/page.tsx` calls `/tools/web_rag/*` and
`/tools/overview`; these do not exist in the packaged server. The thread UI
registers Web Search/RAG tool renderers unconditionally.

### Unwired UI Transcript Append

The backend has `POST /threads/{id}/messages`, and docs describe a history
append hook, but `frontend-full/app/MyRuntimeProvider.tsx` only performs GET
hydration. Normal use likely falls back to checkpoint state and does not
persist exact Assistant UI message objects.

### Configuration Is Distributed

`Settings` claims to be central, but registry factories read `MODEL` directly,
`create_app()` reads web paths and keys directly, and only CLI host/port/default
agent consistently use `Settings`. `Settings.web_dir_path()` is unused and has
no full-UI equivalent.

### Other Risks

- `allow_origins=["*"]` with credentials is overly permissive
  (`server.py:360-369`).
- Invalid default agent values are not rejected at startup.
- Importing `server` constructs a module-level app and state; CLI constructs a
  second app.
- `langchain-openai` is mandatory despite provider-neutral design.
- Dependencies use broad lower bounds and no compatibility ceiling.
- Local builds do not clear `dist/`; smoke installs `dist/*.whl`.
- Manual dispatch can publish without canonical tag/version validation.
- Python compatibility is tested only on 3.11.
- Package metadata lacks common license/author/URL/classifier fields.

## Existing Test Coverage

Package tests cover static mounts, `/full`, injected graphs, registry/default
agents, provider model resolution, state reduction, thread CRUD/checkpointer
fallback, and packaged docs.

Important gaps:

- route-level `runConfig.thread_id`;
- non-OpenAI weather agent without OpenAI key;
- actual entry-point discovery;
- invalid default agent startup;
- CLI and `--check`;
- final installed wheel behavior;
- generated full export against packaged API;
- UI message append from the actual frontend;
- ownership/cross-user behavior;
- CORS browser behavior;
- complete static asset archive checks;
- version consistency;
- newer supported Python versions;
- successful streamed request using an offline fake agent.

## Package Quick Wins

1. Use `resolve_thread_id()` in `run_assistant()` and add route integration
   coverage.
2. Remove or make legacy OpenAI gating provider-aware.
3. Add a package capability endpoint and hide unsupported full UI features.
4. Reserve `/tools` from SPA fallback even when capabilities are absent.
5. Correct stale docs and custom-agent replacement semantics.
6. Run and expand wheel smoke tests in release CI.
7. Clear `dist/` for local builds and eliminate duplicated version sources.
8. Make repository apps consume the package instead of copying it.
9. Introduce a real settings object passed into `create_app()`.
10. Add provider extras and configurable CORS.
