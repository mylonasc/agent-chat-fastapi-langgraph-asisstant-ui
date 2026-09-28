# E2E UI testing

This Playwright suite sends a real two-turn calculator conversation through the
minimal and full UIs. It verifies that rendered message roots remain in
chronological order:

```text
user, assistant, user, assistant
```

It also guards against the duplicate-branch `2 / 2` regression.

## Prerequisites

Run the package server on two ports so both bundled entry points are available:

```bash
MODEL=ollama:qwen3.8:latest UI_PRESET=full minimal-chat-serve --port 8011
MODEL=ollama:qwen3.8:latest UI_PRESET=minimal minimal-chat-serve --port 8012
```

One unified build serves both presets: the full project uses
`http://127.0.0.1:8011/` (full preset), the minimal project uses
`http://127.0.0.1:8012/` (minimal preset). Override them with
`FULL_UI_URL` and `MINIMAL_UI_URL`.

## Run

```bash
cd "e2e UI testing"
pnpm install
pnpm install:browsers
pnpm typecheck
pnpm test
```

Use `pnpm test:full` or `pnpm test:minimal` to run one interface.

Every test writes a full-page final-state screenshot, including failed tests,
under `screenshots/<ISO timestamp>/`. The screenshot directory is ignored by
Git. Timestamp directory names sort chronologically, so the last entry from
`ls -1 screenshots` is the latest run.
