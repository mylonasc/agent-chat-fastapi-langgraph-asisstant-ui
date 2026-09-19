---
name: inspect-minimal-assistant-ui
description: Use when inspecting, testing, or improving the minimal Assistant UI frontend on port 3000, including its chat composer, suggestions, D3 graph tool, responsive DOM, accessibility, and layout quality.
---

# Inspect Minimal Assistant UI

Inspect `application/frontend/frontend-minimal`, which uses Next.js 16,
`@assistant-ui/react` 0.11, Assistant Transport, and D3 for the graph tool.

## Required Method

- Use DOM, ARIA, computed styles, SVG attributes, and element geometry only.
- Never use screenshots, visual snapshots, image comparison, or subjective visual inspection.
- Start with `cd tests/ui && pnpm inspect:minimal`; add `-- --mobile` for the mobile DOM.
- Run `pnpm test:minimal` before and after UI changes.
- Prefer roles, labels, `data-role`, and existing `aui-*` hooks over Tailwind selectors.
- For D3, assert SVG semantics, node/edge counts, finite attributes, control state, and containment; do not judge rendered pixels.

## Script-first Rule

When a new inspection or E2E check is needed, create or extend a reusable
script under `tests/ui/scripts/` or a Playwright spec under `tests/ui/specs/`.
Do not replace executable coverage with verbose manual test instructions or a
long prose checklist. Report the command, structured result, and concise
findings after the script exists and has been run.

## Minimal UI Hooks

- Composer: `getByLabel("Message input")`, `.aui-composer-root`
- Suggestions: `.aui-thread-welcome-suggestion`
- Messages: `[data-role="user"]`, `[data-role="assistant"]`
- Tool fallback: `.aui-tool-fallback-root`
- Graph controls: roles `slider` and `checkbox` with their visible labels
- Graph output: scope `svg`, `circle`, `line`, `text`, and `marker#arrow` to the graph tool container

Treat missing accessible names, duplicate IDs, horizontal overflow, controls
outside the viewport, invalid SVG structure, and unstable DOM contracts as UI
quality defects.
