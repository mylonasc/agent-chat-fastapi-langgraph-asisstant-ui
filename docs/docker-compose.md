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

`OPENAI_API_KEY` is required for normal OpenAI chat. Explicitly selecting the
`web_search` toolset also requires `SERPER_API_KEY`. Keep `.env` out of version
control. See [Toolsets](toolsets.md) for startup and runtime controls.

## Local Demo Launcher

For a native run with uv/Node/pnpm instead, add `--local`; see
[Run without Docker](local-development.md).

With Docker and the Compose v2 plugin installed and Docker running:

```bash
./scripts/run_demo --minimal          # default: UI :3000, API :8011
./scripts/run_demo --full             # full layout: UI :3001, API :8010
./scripts/run_demo --full --detach    # background startup, wait for services
./scripts/run_demo --full --logs      # follow the last 100 log lines
./scripts/run_demo --full --stop      # stop/remove containers, retain volumes
./scripts/run_demo --help
```

The launcher always builds the **current checkout**, including uncommitted
frontend/backend changes. It does not download a release or pull Git changes.
Docker's build cache is retained; use `--no-build` only when you intentionally
want existing images instead of the latest source. No local Node or Python
installation is needed for the demo containers.

Foreground startup streams logs, and Ctrl-C stops the containers. Use
`--detach` to keep the demo running after your terminal exits. The launcher
prints chat, API documentation, and health URLs. Open the chat URL once the
frontend is ready. Startup requires a repository-root `.env`; the launcher
never overwrites or sources it as shell code. Exported shell variables take
precedence over `.env` according to Docker Compose's normal rules.

You can invoke the script by absolute path from any directory. It always uses
this checkout's Compose files and `.env`, not the caller's working directory.
Use `--dry-run` to print the command without Docker or `.env`. Only the
selected setup is affected; volumes and full-demo tool data are not deleted
by `--stop`. Container-local data without a mounted volume can still be lost
when containers are removed or recreated.

## Minimal Stack

```bash
docker-compose -f docker-compose.minimal.yml up --build
```

| Service | URL | Purpose |
| --- | --- | --- |
| `frontend-minimal` | <http://localhost:3000> | Canonical unified UI, minimal runtime preset |
| `backend-minimal` | <http://localhost:8011> | Package compatibility entry point |

Both Compose setups run the same canonical packaged backend. Compose builds the
`application/frontend/frontend` source as a separate development service; the
backend runtime manifest selects its minimal preset. Use the
[packaged app](packaged-app.md) instead when you need the
single-port distributable deployment.

## Full UI Stack

```bash
docker-compose -f docker-compose.full.yml up --build
```

| Service | URL | Purpose |
| --- | --- | --- |
| `frontend-full` | <http://localhost:3001> | Canonical unified UI, full runtime preset |
| `backend-full` | <http://localhost:8010> | Canonical packaged backend, full UI preset |

`full` is a layout, not a toolset. Both layouts default to basic
`calculator,weather,graph` tools. For search/RAG, use:

```bash
./scripts/run_demo --runtime docker --ui full --toolsets calculator,web_search,web_rag
```

The allowlist is baked into the image and selects optional dependencies. Set
`AGENT_CHAT_ADMIN_TOKEN` for local application-wide **Manage toolsets** controls;
**Conversation tools** selects a permitted subset per conversation. See
[Toolsets](toolsets.md) for authorization, knobs, and persistence. Each setup
uses a named volume at `/app/data`. Old `application/backend/full/data` remains
untouched but is not automatically imported.

## Stop A Stack

```bash
docker-compose -f docker-compose.minimal.yml down
docker-compose -f docker-compose.full.yml down
```

Run one stack at a time unless you deliberately want both APIs and frontends.
They use distinct host ports and may otherwise compete for Docker resources.

Both Compose files build the same frontend manifest and lockfile. The service
names and ports remain stable for existing commands; `/api/config` from each
backend selects the relevant layout and capabilities at runtime.
