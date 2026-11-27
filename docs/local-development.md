# Run the Demo Without Docker

Use the same launcher with `--local` to run the **current checkout** directly:

```bash
./scripts/run_demo --minimal --local  # http://localhost:3000, API :8011
./scripts/run_demo --full --local     # http://localhost:3001, API :8010
./scripts/run_demo --runtime local --ui full --toolsets calculator,web_search,web_rag
```

## Prerequisites

- Linux or macOS with Bash.
- [uv](https://docs.astral.sh/uv/getting-started/installation/).
- Node.js 20.9 or newer and pnpm 10 (the frontend pins pnpm 10.20.0).
- A repository-root `.env`, copied from `.env.example`. Set `OPENAI_API_KEY`
  for normal OpenAI chat; explicitly selected Web Search uses `SERPER_API_KEY`.

Docker is **not required**. On first startup, uv provisions Python 3.11 if
needed and syncs the selected backend's locked dependencies into its project
virtual environment. The launcher then runs `pnpm install --frozen-lockfile`.
First-time setup needs network access and may take a few minutes, especially
for explicitly selected RAG dependencies. Optional Docling/GPU extras are not installed
by the default local launcher.

Both layouts use the canonical `packages/agent-chat-minimal` backend with
persistence dependencies. Basic tools are the default; RAG/search are explicit
toolsets independent of layout. See [Toolsets](toolsets.md) for configuration.
Both use the latest source in `application/frontend/frontend`, **not** a
previously bundled or published UI.

## Development Workflow

Local mode runs Uvicorn with reload and the Next.js **development server**;
it is not a production/static build. It waits for the backend and frontend
HTTP endpoints before printing the ready URLs. Both servers bind to loopback.
Logs stay in the terminal, and **Ctrl-C shuts down both servers**, including
their reloader/worker processes. If either server fails, the other is stopped.

After the initial dependency setup, you can skip dependency installation:

```bash
./scripts/run_demo --full --local --no-build
```

Unlike Docker's `--no-build`, local `--no-build` still serves current source;
it only skips uv/pnpm dependency synchronization. Run without it again when
Python dependencies or the frontend lockfile change.

The root `.env` is loaded by uv as environment data, never sourced as shell
code. Exported shell variables take precedence. The launcher explicitly sets
the selected UI preset and API URL so runtime configuration and the frontend
use the requested local ports. It does not overwrite `.env` or pull Git changes.

## Ports and Existing Demos

Local defaults match Docker's ports. The launcher **does not stop existing
services** if a port is occupied. Either stop the selected Docker setup with
`./scripts/run_demo --full --stop`, or choose different local ports:

```bash
./scripts/run_demo --full --local --ui-port 3101 --api-port 8110
```

Run only one local frontend per checkout at a time: both presets share the
frontend source directory and Next.js dev lock. A local demo and a Docker
demo can coexist on different ports. Local mode is foreground-only;
`--detach`, `--logs`, and `--stop` remain Docker-only flags. Local data follows
the shared backend's configuration under `.demo-data/<ui>/`; it is not
automatically copied from Docker volumes or the legacy RAG data directory.

To inspect the command without installing anything or starting services:

```bash
./scripts/run_demo --full --local --dry-run
```

## Launcher Checks

Offline CLI and process-lifecycle tests (no model calls or dependency downloads):

```bash
python3 -m unittest discover -s tests -p 'test_run_demo*.py'
```

Opt-in real startup/configuration/shutdown smoke check, without LLM calls:

```bash
RUN_DEMO_LIVE=full python3 -m unittest discover -s tests -p test_run_demo_local.py
# Or RUN_DEMO_LIVE=minimal; add RUN_DEMO_SKIP_INSTALL=1 after initial setup.
```
