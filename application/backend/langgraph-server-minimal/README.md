# Minimal Compatibility Backend

This directory is a compatibility development entry point for the canonical
portable application in [`packages/agent-chat-minimal`](../../../packages/agent-chat-minimal).
It does not own a separate agent or route implementation: `server.py` imports
`agent_chat_minimal.create_default_app()`.

From this directory, start the package-backed API with reload:

```bash
uv run uvicorn server:app --port 8011
```

To serve a static export from a checkout on the same port, set the web directory
before starting the server:

```bash
MINIMAL_WEB_DIR=../../frontend/frontend-minimal/out \
  uv run uvicorn server:app --port 8011
```

For the normal packaged deployment, local wheel build, persistence, and agent
registration, use the [packaged app guide](../../../docs/packaged-app.md). For
the split frontend/backend development setup, use
[`docker-compose.minimal.yml`](../../../docs/docker-compose.md).
