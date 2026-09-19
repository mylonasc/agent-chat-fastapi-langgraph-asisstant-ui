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
