# Quickstart

For a local Ollama website without API keys or custom agent code, start with
[ollama-quickstart.md](ollama-quickstart.md). It uses the existing tool-enabled
starter and explains the tool-free shortcut still proposed in issue #70.

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
For the sidebar with previous chats, set `UI_PRESET=full` and open
<http://localhost:8011/>.

## Next steps

- Coding agent? → [agent-onboarding.md](agent-onboarding.md).
- Generate an editable chat website? → [starter.md](starter.md).
- Custom agent? → [agents.md](agents.md).
- Another model provider? → [providers.md](providers.md).
- Env vars and flags? → [configuration.md](configuration.md).
- Threaded chats / frontend-full? → [threads.md](threads.md).
