# Toolsets and runtime configuration

The current source separates three choices:

| Choice | Values | Meaning |
| --- | --- | --- |
| UI | `minimal`, `full` | Interface layout only |
| Toolsets | A list of IDs below | Tools available to the managed agent |
| Runtime | `local`, `docker`, or installed server | How the same backend runs |

**`full` no longer implies RAG or web search.** Both demo layouts default to
`calculator,weather,graph`. `--minimal`, `--full`, and `--local` remain aliases.
These are source-checkout changes; build a new wheel from this checkout to use
them in a packaged installation. An older published wheel is unchanged.

## Startup / baked configuration

```bash
./scripts/run_demo --runtime local --ui full --toolsets calculator,weather,graph
./scripts/run_demo --runtime docker --ui full --toolsets calculator,weather,graph --detach

# Optional dependencies are installed at setup, never from the browser:
./scripts/run_demo --runtime local --ui full --toolsets calculator,web_search,web_rag

# Initially enable calculator, allowing other basic sets to be enabled later:
./scripts/run_demo --runtime local --ui full --toolsets calculator \
  --allow-toolsets calculator,weather,graph

# A managed agent with no tools:
./scripts/run_demo --runtime local --ui full --toolsets ''
```

`--toolsets` supplies initial defaults. `--allow-toolsets` is the deployment
ceiling for runtime management; it defaults to the selected list. Runtime
administration cannot install packages or enable a toolset outside that ceiling.
Local setup and Docker baking use the same catalogue to select Python extras.
Basic-only setups do not install FAISS, FastEmbed, BM25, or document parsers.
Search-only needs `web-search`; RAG needs `web`.

Both Compose files build `scripts/Dockerfile.backend` from the repository root;
the old per-backend Dockerfiles have been retired.

For a wheel built from this checkout (install its `persistence` extra):

```bash
agent-chat-serve --ui full --toolsets calculator,weather,graph
agent-chat-serve --config /path/to/agent_chat.yaml
```

`agent-chat-serve` is the canonical command with the launcher's basic defaults.
`minimal-chat-serve` retains its legacy agent-registry defaults and accepts
explicit `--ui`, `--toolsets`, and `--allow-toolsets` too. Do not combine
managed toolsets with `--agent`. Opaque custom graphs remain supported through
the app factory, but are not silently rewritten or advertised as enforcing
managed tool policy.

Shared YAML configuration:

```yaml
version: 1
ui_preset: full
toolsets: [calculator, weather]
allowed_toolsets: [calculator, weather, graph]
persistence_enabled: true
database_path: ./data/chat.sqlite3
checkpoint_database_path: ./data/checkpoints.sqlite3
tool_settings_path: ./data/tool-settings.sqlite3
tool_data_path: ./data/web_rag
tool_config:
  divide:
    precision: 3
  get_weather:
    units: fahrenheit
```

Environment equivalents include `UI_PRESET`, `TOOLSETS`, `ALLOWED_TOOLSETS`,
`TOOL_SETTINGS_PATH`, and `TOOL_DATA_PATH`. `AGENT_CHAT_CONFIG` selects YAML;
relative paths resolve against that file. Explicit environment variables
override YAML; CLI flags override those. For Docker, mount custom YAML read-only
and use its **container** path. Its image build allowlist must include the
optional dependencies required by that configuration.

## Runtime UI and knobs

Both layouts expose **Manage toolsets** (`/toolsets`) for application policy
and **Conversation tools** for owner-scoped conversation choices. The catalogue
is read-only until administrator authorization succeeds. Each tool declares
its fields once; forms render switches, bounded integers, and enum dropdowns.
The backend independently rejects unknown fields and invalid values.

| Toolset | Tools | Knobs |
| --- | --- | --- |
| `calculator` | `add`, `subtract`, `multiply`, `divide` | Decimal places per tool (0–12) |
| `weather` | `get_weather` | Celsius/Fahrenheit; simulated, not live weather |
| `graph` | `render_graph` | Maximum nodes (1–500) |
| `web_search` | `web_search` | Result count (1–10), wait for indexing; admin-only automatic indexing |
| `web_rag` | `web_rag`, `web_rag_status` | Retrieval count (1–20), admin-only web bootstrap; startup-only chunk size/provider |

Administrators can configure dormant tools without enabling them. Chunk size
and embedding provider are intentionally read-only at runtime: change startup
configuration and reindex. Use a new `tool_data_path` when changing embedding
providers; do not mix incompatible vectors in an existing corpus.

RAG alone never silently enables web search: bootstrap needs an enabled
`web_search` tool and the admin bootstrap setting. Search cannot index/retrieve
RAG chunks unless `web_rag` is enabled. Model arguments cannot bypass these
checks. RAG namespaces are derived server-side from the resolved principal,
not from a model-supplied `user_id`.

## Persistence and security

Validated settings live in a separate SQLite database. Transactional revision
checks reject stale editors with `409`; refresh rather than overwriting another
editor. Conversation preferences are ownership-checked and owner-scoped, and
are removed when the conversation is deleted.

Each turn binds a fresh graph to an immutable effective-policy snapshot.
Changes apply to the **next turn**, not an in-flight response, and do not cancel
indexing already started. Disabled tools are removed from subsequent agent
bindings, not merely hidden. Historical results remain renderable.

Saved runtime choices override startup defaults after restart, while the current
baked allowlist and startup-only fields remain authoritative. Editing defaults
does not erase runtime choices. Use separate databases for separate deployments.
Managed environment/YAML startup enables chat persistence unless explicitly
disabled; install the `persistence` extra. Programmatic `Settings` callers
should set `persistence_enabled=True` too. Tool preferences persist independently,
but restoring a conversation also requires durable chat sessions/checkpoints.

Local demo data is under `.demo-data/<ui>/`. Docker uses independent named
volumes (`demo-minimal-data`, `demo-full-data`) at `/app/data`; `--stop` retains
them. Old RAG data at `application/backend/full/data/` is **not deleted or
automatically migrated**.

For local administration, set a strong **`AGENT_CHAT_ADMIN_TOKEN`** in the
backend environment/root `.env`, restart, and enter it in Manage toolsets.
The UI holds that token only in page memory, never browser storage. Do not put
credentials in knobs, YAML, `NEXT_PUBLIC_*`, URLs, or the capability manifest.
Provider credentials remain backend-only environment variables such as
`OPENAI_API_KEY` and `SERPER_API_KEY`; forms cannot read or replace them.

Production must inject an authenticated principal resolver. A verified
`Principal(..., claims={"role": "admin"})` grants global administration;
ordinary principals may only manage their own conversations. Client-supplied
subject/role headers are not authentication. The default anonymous resolver is
demo convenience isolation, not secure multi-user authentication. Use HTTPS
and a trusted authentication boundary before exposing network tools.

## API / implementation

- `GET /tooling`: safe deployment catalogue and current policy.
- `GET/PUT /tooling/admin`: administrator-only application settings.
- `GET/PUT /threads/{id}/tools`: owner-only conversation preferences.
- `/api/config`: layout and stable `tooling.enabled`/`tool_names` capabilities.

Writes include `revision`, `global_revision`, `toolsets`, and a `tools` map of
`{enabled, config}` entries. Fields declare `conversation`, `admin`, or `startup`
scope; runtime APIs enforce it.

Implementation is centralized in
`packages/agent-chat-minimal/src/agent_chat_minimal/toolkits/`. Optional web tools
live once in `agent_chat_minimal/web_tools/`. The old
`application/backend/full/tools` namespace is a compatibility adapter, not a
second implementation. The legacy RAG server/examples remain available but
are no longer selected by `run_demo --full`.

Checks:

```bash
uv run --project packages/agent-chat-minimal --extra test pytest packages/agent-chat-minimal/tests
python3 -m unittest discover -s tests -p 'test_run_demo*.py'
cd tests/ui && pnpm test:full
```

After building the frontend, validate an isolated installed wheel (including
the management page and durable conversation choices) without modifying the
source package's staged assets:

```bash
python3 tests/ui/scripts/check-toolsets-wheel.py
```
