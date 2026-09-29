# Unified Packaged Frontend

This Next.js application is the canonical frontend built into
`agent-chat-minimal`. Its static export is staged into the Python package by
`packages/agent-chat-minimal/scripts/stage_ui.sh`; a built wheel serves it from
the FastAPI application at `/`.

Run it against a backend during frontend development:

```bash
pnpm install --frozen-lockfile
NEXT_PUBLIC_API_BASE=http://localhost:8011 pnpm dev
```

Do not put provider secrets in this frontend. The browser talks to the backend,
which owns model credentials. `GET /api/config` selects runtime UI capabilities
and the `UI_PRESET` layout. See the [packaged app guide](../../../docs/packaged-app.md)
and [Docker Compose guide](../../../docs/docker-compose.md) for supported run
configurations.
