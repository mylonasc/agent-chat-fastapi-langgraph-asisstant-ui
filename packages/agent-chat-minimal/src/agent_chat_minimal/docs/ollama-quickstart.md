# Local Ollama chat: fastest supported route

Use the bundled UI and the starter generator for a local chat website without
writing agent code, running a separate frontend server, or supplying an API key.
This guide documents the **currently supported tool-enabled starter**. The
tool-free built-in `chat` agent proposed in issue #70 is not implemented here;
do not use `--agent chat` with this version. Ordinary non-tool models require
a custom tool-free graph until that enhancement ships.

## 1. Choose Python and make a model available

Use standard CPython **3.12** for the shortest known-working source-build path.
The package supports Python 3.11+, but transitive dependencies may not support
free-threaded interpreters: Python 3.14t can fail while building `orjson`.
Explicitly select 3.12 rather than accepting an environment manager's default.

Install Ollama separately (https://ollama.com/download). Start its daemon in
another terminal if it is not already running:

```bash
ollama serve
```

In your working terminal, pull a tool-capable model and check the endpoint:

```bash
ollama pull llama3.1:8b
ollama list
curl --fail http://localhost:11434/api/tags
```

Pulling downloads model weights and needs network access and sufficient disk/RAM.
Model availability is not established by merely installing the Python extra.
Use the exact installed model tag below. `llama3.1:8b` is the starter example
because the generated helper binds a greeting tool; do not substitute a model
without tool support just because it can answer ordinary chat prompts.

## 2. Generate, install, and serve a baseline site

The following POSIX-shell sequence uses a released package that includes the
initializer. New documentation/setup CLI commands require a build containing
the agentic-enablement enhancements; the initializer itself already exists.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install 'agent-chat-fastapi-langgraph-assistant-ui[ollama]'
minimal-chat-init ./my-local-chat --provider ollama --model llama3.1:8b --preset full
cd my-local-chat
python -m pip install -e '.[test]'
python -m pytest
my-local-chat-serve --config ./agent_chat.yaml
```

Open **http://localhost:8011/**. `/health` checks the server and `/agents`
should list `helper`. The `full` preset provides the threaded chat UI. No
OpenAI key, Node.js, Next.js rebuild, Docker stack, or custom Python module is
needed. The generated project already declares the Ollama extra. On Windows,
activate the virtual environment with `.venv\Scripts\activate` instead.

Generation never installs dependencies, pulls models, or launches services.
The last command starts a long-running server; stop it with Ctrl+C. Default
history is in memory and is lost on server restart. Read `AGENTS.md` in the
generated project before editing its code.

For automation, append `--dry-run --json` to preview, then use `--json` without
`--dry-run` to generate and obtain command argv arrays and their working directory.
Older published versions may not support these JSON flags; use the simple
initializer sequence above or install this branch's built wheel.

### Starting from this repository checkout

Build and install the bundled UI once, from the repository root, before running
the initializer. Node.js/pnpm and `uv` are build tools only:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
UV_PYTHON=3.12 packages/agent-chat-minimal/scripts/build_wheel.sh
python -m pip install packages/agent-chat-minimal/dist/*.whl
```

Then run the `minimal-chat-init`, `cd`, project install, test, and serve commands
from step 2. The generated dependency specification installs the selected
Ollama integration. An editable checkout without staged UI assets may serve
only the API; a built wheel avoids that trap. Generated projects pin the
library version used to generate them.

## 3. Select a model or a remote Ollama endpoint

- Choose a model at generation: `--provider ollama --model llama3.1:8b`.
  In the generated `agent_chat.yaml`, the equivalent is
  `model: ollama:llama3.1:8b`; the final colon is part of the model tag.
- The default model endpoint is `http://localhost:11434`. When running inside
  a container, `localhost` means that container, not the host's Ollama daemon.
- `API_BASE` controls browser-to-FastAPI communication, **not** the Ollama
  endpoint. Leave it unset for the bundled same-origin UI. Do not assume an
  arbitrary `MODEL_BASE_URL` environment variable is consumed by this server.

For a non-default endpoint, use the library's supported `ModelConfig` in
`src/my_local_chat/agents/helper.py`. The initializer currently accepts
`--base-url` but does not forward it into the generated helper, so that flag
alone is **not** a working endpoint override in this version. Replace the
helper factory body with the following (its existing imports and tool/prompt
constants remain in place):

```python
    if isinstance(model, str):
        selected = ModelConfig.from_spec(model)
        model = ModelConfig(
            provider=selected.provider,
            model=selected.model,
            base_url="http://ollama.internal:11434",
        )
    return make_tool_agent(model, list(HELPER_TOOLS), HELPER_SYSTEM_PROMPT, checkpointer)
```

This URL is the Ollama model API, not the browser-facing chat website. Keep
the same `model:` setting in YAML; the factory preserves the selected model tag.
This optional remote-endpoint customization requires a small code edit; the
default local endpoint needs none. Correctly forwarding initializer endpoint
options should be addressed alongside issue #70's faster onboarding work.

`minimal-chat-setup doctor --provider ollama --preset full --json` checks local
dependencies and bundled UI availability, not whether Ollama is running or a
model is installed. Likewise, `my-local-chat-serve --check` constructs the graph;
only a real conversation verifies inference and tool support.

## 4. Optional durable SQLite history

For a new project, add `--persistence sqlite` to the initializer command. Before
the first server start, create its data directory from the generated project root:

```bash
mkdir -p data
```

The generator declares the `persistence` extra and writes separate application
and checkpoint paths under `data/`. Do not assume their parent directories are
created automatically in this version; first-run directory handling is another
enhancement tracked by issue #70.

For an existing memory-only project, add `persistence` to its library dependency
extras in `pyproject.toml` alongside `ollama`, reinstall with
`python -m pip install -e '.[test]'`, create `data/`, and add these top-level
keys to `agent_chat.yaml`:

```yaml
persistence_enabled: true
database_path: data/app.db
checkpoint_database_path: data/checkpoints.db
```

Keep `ui_preset: full`. Paths resolve relative to the configuration file.
Keep both SQLite files and their WAL files on writable local durable storage;
this setup is intended for one server process/node.

## 5. Live smoke test (explicit, not an offline test)

With Ollama and the site running:

1. Open http://localhost:8011/ in a browser. Send “Remember the codeword amber.”
   Confirm that an assistant response arrives through the streaming transport.
   Very short responses may appear all at once; use a longer prompt or inspect
   the `/assistant` response stream if needed.
2. In the **same thread**, ask “What codeword did I give you?” Verify the answer
   refers to amber, testing multi-turn model context.
3. With SQLite enabled, reload the page in the same browser profile and open
   that thread from the sidebar. Verify both turns are visible.
4. Stop and restart the same generated server with the same config and database
   files. Reload, reopen the thread, and ask about the codeword again. This checks
   durable transcripts **and** LangGraph checkpoint restoration.

Use the same browser profile: anonymous identity is stored locally, and clearing
browser storage can make a different identity see a different thread list.
`python -m pytest` is an offline fake-model check, not evidence that this live
procedure succeeded. Do not claim live verification without actually doing it.

## Shortcuts and limitations

For a tool-demo-only check, the existing packaged server can run
`UI_PRESET=full minimal-chat-serve --model ollama:llama3.1:8b --agent calculator`.
It serves a calculator agent, not a general-purpose tool-free chat agent.
The recommended route for a user-owned application is the initializer above.

Issue #70 proposes a built-in tool-free `chat` agent, a simpler direct launch,
and safer SQLite first-run behavior. Those are implementation work, not features
that documentation alone can enable. See `providers`, `starter`, and
`agent-onboarding` for the current supported extension points.
