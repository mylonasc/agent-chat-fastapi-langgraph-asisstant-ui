# Packaged Application, Build, And Release Reconnaissance

## Scope

This report describes the current portable non-RAG application, not the
separate `application/backend/full` RAG demo. User-facing setup belongs in
[`../docs/packaged-app.md`](../docs/packaged-app.md); this file records the
implementation boundaries maintainers need when changing the package.

## Distribution And Runtime

- Distribution source: `packages/agent-chat-minimal`
- Project name: `agent-chat-fastapi-langgraph-assistant-ui`
- Supported Python: 3.11+
- Current source version: `agent_chat_minimal.__version__` (`0.5.1` at this
  snapshot)
- Console command: `minimal-chat-serve`
- ASGI factory: `agent_chat_minimal:create_default_app --factory`

`minimal-chat-serve` builds `Settings` from environment and CLI values, then
calls `create_configured_app()`. The application serves the Assistant API,
thread/session routes, `/api/config`, and the unified static UI at `/`. Its
default bind is `0.0.0.0:8011`. A wheel contains the static UI, so Node is not
needed at runtime.

`create_app(...)` is the injection-first API for embedding a graph, a graph
factory, or a named agent mapping. `create_configured_app()` owns the optional
durable SQLite dependencies used by the supported CLI and ASGI factory.

## Agent Registration

`registry.py` supplies two built-ins: `weather` and `calculator`. It also loads
third-party entry points from `agent_chat.agents`. A plugin factory is named in
its own `pyproject.toml`:

```toml
[project.entry-points."agent_chat.agents"]
my-agent = "my_package.my_agent:make_my_agent"
```

Built-ins win name collisions. Passing `agents={...}` to `create_app()` replaces
rather than extends the discovered registry. Factories that accept
`checkpointer=` receive the shared in-memory or durable checkpointer. See the
[agent guide](../docs/implementing-agents.md) for the public contract.

## UI Build And Wheel Build

`scripts/build_wheel.sh` is the canonical local artifact build. It runs
`scripts/stage_ui.sh`, clears `dist/`, and runs `uv build`.

`stage_ui.sh` performs a frozen pnpm install and static build of
`application/frontend/frontend`, with same-origin API configuration. It copies
the generated `out/` directory to `src/agent_chat_minimal/web/`. That generated
directory is ignored by Git, while Hatch force-includes it in both the wheel and
sdist. The runtime UI preset is selected with `UI_PRESET=minimal` or
`UI_PRESET=full`; there is one bundle and no packaged `/full/` mount.

## Persistence Boundary

The default application uses in-memory services and a `MemorySaver`. Setting
`PERSISTENCE_ENABLED=true`, or a database/checkpoint path or URL, selects the
supported SQLite composition after installing the `persistence` extra. It owns
two distinct stores:

- application data through `SQLiteRepositories`
- LangGraph checkpoint data through `LangGraphSQLiteCheckpoints`

The paths must remain separate. The FastAPI lifespan opens, migrates when
`AUTO_MIGRATE=true`, injects, and closes these resources.

## Verification And Release Automation

- Package tests: `pytest packages/agent-chat-minimal`
- Built-wheel smoke test:
  `packages/agent-chat-minimal/scripts/smoke_test_wheel.sh`
- Artifact CI: `.github/workflows/artifact-workflow.yml`
- Publish CI: `.github/workflows/publish-workflow.yml`

Artifact checks build the wheel, validate package metadata, and exercise an
installed artifact without Node on `PATH`. Keep these checks aligned with any
change to static assets, console commands, or the HTTP surface.

## Relationship To Repository Applications

`application/backend/langgraph-server-minimal/server.py` is only a compatibility
import of `create_default_app()`. Do not add a second minimal route or agent
implementation there. `docker-compose.minimal.yml` remains useful for split UI
development, while a wheel is the single-process deployment form.

`application/backend/full` is a separate source-run RAG application with its
own tool composition. Its Web Search/RAG endpoints are not promised by, and do
not ship with, the portable package.
