# Quickstart

## Install

```bash
pip install agent-chat-fastapi-langgraph-assistant-ui
```

Or from this repo (builds the UI + wheel; Node/pnpm needed only here):

```bash
packages/agent-chat-minimal/scripts/build_wheel.sh
python -m pip install packages/agent-chat-minimal/dist/*.whl
```

## Serve

```bash
export OPENAI_API_KEY=sk-...
minimal-chat-serve --port 8011
# open http://localhost:8011/
```

Without `OPENAI_API_KEY`, the UI and `GET /health` still work; `POST /assistant`
returns 503 with setup instructions.

## First chat

```bash
curl -s localhost:8011/health
# {"status":"ok"}

curl -s localhost:8011/agents
# {"agents":["calculator","weather"],"default":"weather"}
```

In the UI, try *"What is 12 × 8?"* (calculator) or *"Weather in London?"*.

## Next steps

- Custom agent? → [agents.md](agents.md).
- Another model provider? → [providers.md](providers.md).
- Env vars and flags? → [configuration.md](configuration.md).
- Threaded chats / frontend-full? → [threads.md](threads.md).
