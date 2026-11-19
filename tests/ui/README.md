# DOM-only UI testing

This Playwright harness checks the full and minimal applications through DOM,
ARIA, computed-style, and layout-geometry inspection. Screenshots, visual
snapshots, and image analysis are intentionally disabled.

```bash
cd tests/ui
pnpm install
pnpm install:browsers
pnpm typecheck
pnpm test
pnpm inspect:full
pnpm inspect:minimal -- --mobile
```

The test runner reuses applications already running on ports 3001 and 3000.
If they are unavailable, Playwright starts the corresponding Compose stacks.
Set `FULL_UI_URL`, `MINIMAL_UI_URL`, or `FULL_API_URL` to inspect other hosts.

## OpenAI persistence E2E

The durable full-preset tests can use OpenAI without Ollama or a local GPU.
The launcher uses Python 3.11, starts the source package on port 8011, and
creates isolated temporary SQLite databases that are removed after the run.
It reads the credential from the environment and never writes it to disk:

```bash
cd tests/ui
export OPENAI_API_KEY=...
pnpm test:persistence:openai
```

The default model is `openai:gpt-4o-mini`. Override it with
`OPENAI_E2E_MODEL=openai:<model>` when needed.

Inspection commands print JSON so agents can compare structure, accessible
names, target sizes, duplicate IDs, and overflow without visual judgment.

## Installed-package proxy prefix regression

Build the wheel with `packages/agent-chat-minimal/scripts/build_wheel.sh`, then
install it into a clean Python virtual environment. From `tests/ui`, run:

```bash
UI_PYTHON=/path/to/venv/bin/python node scripts/verify-base-path.mjs
```

The reusable test launches the installed package with a credential-free graph
and a real prefix-restricted streaming HTTP proxy. Chromium checks root,
single-segment, and nested prefixes with prefix stripping and preservation.
Both presets check asset/font loading, runtime bootstrap, redirects, refresh,
client-side navigation, and requests escaping the prefix. The full preset also
checks chat streaming, threads, transcript synchronization, and feedback.
Output is structured JSON; it uses DOM assertions, not screenshots.
Repeat with an environment installed from the sdist to verify both artifacts.
