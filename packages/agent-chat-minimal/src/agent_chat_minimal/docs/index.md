# agent-chat-minimal — documentation index

Portable FastAPI + LangGraph chat server with a bundled Assistant UI.
Install from PyPI (Python 3.11+, no Node needed) and serve one command:

```bash
pip install agent-chat-fastapi-langgraph-assistant-ui
minimal-chat-serve --port 8011
```

Guides (shipped inside the wheel under `agent_chat_minimal/docs/`):

- [quickstart.md](quickstart.md) — install, serve, first chat (2 minutes).
- [agents.md](agents.md) — implement and serve your own agent.
- [providers.md](providers.md) — model specs for OpenAI, Anthropic, Ollama, ….
- [configuration.md](configuration.md) — env vars, CLI flags, hooks.
- [threads.md](threads.md) — multi-thread chats, frontend-full compatibility.
- [transport.md](transport.md) — Assistant transport protocol boundary.
- [persistence.md](persistence.md) — durable repositories and checkpoints.
- [runtime-config.md](runtime-config.md) — runtime UI capabilities.
- [index.md](index.md) — this file: architecture overview.

Discoverability: every guide is readable at runtime without unpacking the wheel:

```python
from agent_chat_minimal import docs
docs.list()          # ['agents', 'configuration', ...]
print(docs.get("agents"))
docs.show("threads") # prints to stdout
```

FastAPI also serves interactive Swagger UI at `GET /docs` when the server runs.
