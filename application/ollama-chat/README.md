# Local Ollama Chat

A streaming chat app using this repository's built library and bundled Assistant
UI. Includes Markdown, stop generation, multiple conversations, and SQLite history.
No API key or separate frontend server is needed.

## Build and install

Run from the repository root (Python 3.11+, uv, Node, and pnpm required to build):

```bash
packages/agent-chat-minimal/scripts/build_wheel.sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python 'packages/agent-chat-minimal/dist/agent_chat_fastapi_langgraph_assistant_ui-0.6.2-py3-none-any.whl[ollama,persistence]'
```

## Run

Start Ollama if it is not already running, and download the default model:

```bash
ollama serve
# In another terminal:
ollama pull llama3.2:latest
```

Then, from the repository root:

```bash
.venv/bin/python application/ollama-chat/server.py
```

Open **http://localhost:8011**. Both the UI and API are served on that port.
The server binds only to loopback by default; do not expose this unauthenticated
app to the public Internet. Conversations are stored in this directory's `data/`.

Change the model in `agent_chat.yaml` or override it at launch:

```bash
MODEL=ollama:llama3.1:latest .venv/bin/python application/ollama-chat/server.py
```

Ollama defaults to `http://localhost:11434`. To use another local endpoint, set
`OLLAMA_HOST=http://localhost:11434` before starting the app. `PORT` and
`UI_PRESET=minimal` are also supported environment overrides. Use `--config PATH`
for a different YAML configuration.

If chat fails, check `curl http://localhost:11434/api/tags` and ensure the model
name exactly matches an installed model. Server errors are logged in the terminal.

## Offline tests

```bash
uv pip install --python .venv/bin/python pytest httpx
.venv/bin/python -m pytest application/ollama-chat/test_server.py
```
