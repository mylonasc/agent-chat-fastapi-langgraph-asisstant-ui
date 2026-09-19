---
name: inspect-full-assistant-ui
description: Use when inspecting, testing, or improving the full Assistant UI frontend on port 3001, including its sidebar, thread list, RAG widgets, admin view, responsive DOM, accessibility, and layout quality.
---

# Inspect Full Assistant UI

Inspect `application/frontend/frontend-full`, which uses Next.js 16,
`@assistant-ui/react` 0.11, Radix/shadcn primitives, and the FastAPI API on
port 8010.

## Required Method

- Use DOM, ARIA, computed styles, and element geometry only.
- Never use screenshots, visual snapshots, image comparison, or subjective visual inspection.
- Start with `cd tests/ui && pnpm inspect:full`; add `-- --mobile` for the mobile DOM.
- Run `pnpm test:full` before and after UI changes.
- Prefer roles, labels, `data-slot`, `data-role`, `data-testid`, and existing `aui-*` hooks over Tailwind selectors.
- Mock backend routes for deterministic quality tests. Keep live LLM/RAG checks separate from DOM-quality tests.

## Script-first Rule

When a new inspection or E2E check is needed, create or extend a reusable
script under `tests/ui/scripts/` or a Playwright spec under `tests/ui/specs/`.
Do not replace executable coverage with verbose manual test instructions or a
long prose checklist. Report the command, structured result, and concise
findings after the script exists and has been run.

## Full UI Hooks

- Composer: `getByLabel("Message input")`, `.aui-composer-root`
- Sidebar: `[data-slot="sidebar"]`, `[data-slot="sidebar-trigger"]`
- Messages: `[data-role="user"]`, `[data-role="assistant"]`
- Thread actions: accessible button names such as `New Thread`, `Rename thread`, and `Archive thread`
- RAG widgets: `[data-testid^="source-indexing-widget-"]`
- Admin: `/admin`, headed by `Web RAG Admin`

Treat missing accessible names, duplicate IDs, horizontal overflow, controls
outside the viewport, broken keyboard state, and unstable DOM contracts as UI
quality defects.
