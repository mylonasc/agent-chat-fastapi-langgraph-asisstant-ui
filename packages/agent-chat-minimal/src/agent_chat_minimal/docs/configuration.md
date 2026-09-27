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
OPENAI_API_KEY=             # credential for the default openai model
ANTHROPIC_API_KEY=          # credential when MODEL uses anthropic:
```

```python
from agent_chat_minimal import Settings
Settings.from_env()  # Settings(host='0.0.0.0', port=8011, ...)
```

## CLI

```bash
minimal-chat-serve --host 127.0.0.1 --port 8011 \
  --model ollama:llama3.1 --agent calculator
minimal-chat-serve --agent weather --check   # build graph, exit, no server
```

`--check` is the fast CI smoke test: non-zero exit with the real factory
error when credentials are missing.

## Hooks (`create_app(...)`)

| Parameter        | Purpose                                            |
| ---------------- | -------------------------------------------------- |
| `graph=`         | Serve one prebuilt graph (`/agents == ["default"]`)|
| `graph_factory=` | Deferred single-graph build (errors at startup)    |
| `agents=`        | Name → factory map (multi-agent mode)              |
| `default_agent=` | Id aliased by `POST /assistant`                    |
| `web_dir=`       | Override the bundled UI directory                  |
| `prepare_state=` | `(state, request) -> message dicts` reducer        |
| `checkpointer=`  | Shared checkpointer (`"memory"` default, see below)|
| `thread_manager=`/`message_store=` | Swap thread storage (tests)          |

## Checkpointer

`"memory"` (default) builds one shared `MemorySaver` and passes it to every
factory whose signature accepts `checkpointer`. Per-`thread_id` graph state
then persists across requests (see [threads.md](threads.md)). Pass an explicit
saver instance for custom backends, or `None` to disable injection.

## `/assistant` 503 semantics

- Default registry + no `OPENAI_API_KEY` → legacy
  `{"error": "OPENAI_API_KEY not configured", ...}` (backward compatible).
- Custom graph/factory failure →
  `{"error": "agent_not_ready", "message": ..., "hint": ...}` with the real
  factory exception in `hint`.
