# Run With Docker Compose

Docker Compose runs split frontend/backend development stacks. It is different
from the packaged application: the browser UI and API are separate services and
ports.

## Prerequisites

Create a local environment file and provide at least the credential needed by
the selected stack:

```bash
cp .env.example .env
```

`OPENAI_API_KEY` is required for normal chat in both stacks. The full RAG stack
also uses `SERPER_API_KEY` for Web Search. Keep `.env` out of version control.

## Minimal Stack

```bash
docker-compose -f docker-compose.minimal.yml up --build
```

| Service | URL | Purpose |
| --- | --- | --- |
| `frontend-minimal` | <http://localhost:3000> | Legacy minimal Next.js UI |
| `backend-minimal` | <http://localhost:8011> | Package compatibility entry point |

The backend imports `agent_chat_minimal.create_default_app()`, so it has the
same API behavior as the package but the UI remains a separate development
service. Use the [packaged app](packaged-app.md) instead when you need the
single-port distributable deployment.

## Full RAG Stack

```bash
docker-compose -f docker-compose.full.yml up --build
```

| Service | URL | Purpose |
| --- | --- | --- |
| `frontend-full` | <http://localhost:3001> | Legacy full UI with threads and tool views |
| `backend-full` | <http://localhost:8010> | Separate Web Search/RAG FastAPI demo |

The full backend accepts `SERPER_API_KEY`, `EMBEDDING_PROVIDER`,
`EMBEDDING_MODEL`, `AGENT_MODE`, `DOCLING_VARIANT`, and
`RAG_STARTUP_VALIDATION`. Its `application/backend/full/data` volume stores
tool data, but its chat/checkpoint behavior is not the packaged app's durable
SQLite composition.

## Stop A Stack

```bash
docker-compose -f docker-compose.minimal.yml down
docker-compose -f docker-compose.full.yml down
```

Run one stack at a time unless you deliberately want both APIs and frontends.
They use distinct host ports and may otherwise compete for Docker resources.
