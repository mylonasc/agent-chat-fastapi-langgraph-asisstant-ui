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

Inspection commands print JSON so agents can compare structure, accessible
names, target sizes, duplicate IDs, and overflow without visual judgment.

## Installed-artifact URL prefix regression

```bash
packages/agent-chat-minimal/scripts/build_wheel.sh # from repository root
uv venv --python 3.12 /tmp/opencode/prefix-venv
uv pip install --python /tmp/opencode/prefix-venv/bin/python packages/agent-chat-minimal/dist/*.whl
UI_PYTHON=/tmp/opencode/prefix-venv/bin/python node tests/ui/scripts/verify-prefix.mjs
```

Run the Node command from the repository root after installing this harness's
dependencies/browser. It outputs JSON for 12 cases: `/`, `/chat`, nested prefix;
minimal/full presets; prefix-stripping/preserving proxies. Each case tests real
hydration by sending a credential-free streamed message, reload, slash redirect,
and client navigation (including Flight fetches/lazy chunks). Full mode also
checks transcripts and feedback. Same-origin requests must remain under the
prefix; HTTP failures (except absent feedback), uncaught page errors, and
non-cancellation transport failures fail the run. The fixture imports the
installed artifact, not an editable checkout. Artifact CI runs it for both the
wheel and sdist.
