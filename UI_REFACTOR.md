# UI Refactor Plan

This plan targets the canonical unified frontend in
`application/frontend/frontend`. The legacy `frontend-full` and
`frontend-minimal` applications remain unchanged until the final migration
slice.

## Delivery principles

- Each slice must be independently reviewable and releasable.
- Preserve DOM hooks and user-visible behavior unless a slice explicitly
  changes a product contract.
- Add or move tests before removing compatibility code.
- Do not mix broad formatting changes with behavioral refactors.
- A slice is complete only when all of its acceptance gates pass.

## Global acceptance gates

These gates apply to every implementation slice after Slice 1 establishes
them:

1. `pnpm typecheck`
2. `pnpm lint`
3. `pnpm prettier`
4. `pnpm build`
5. Relevant Playwright suites under `application/frontend/frontend/e2e`
6. No new unapproved `any`, module-level mutable cache, or direct `fetch`
   outside the API/config boundary
7. Existing accessibility and automation hooks (`aria-label`, `data-role`,
   `data-slot`, `data-testid`, and `aui-*`) remain stable

## Slice 1 — Restore engineering gates

**Goal:** Make static checks reliable enough to protect later structural
changes.

### Work

- Replace the removed Next.js `next lint` command with ESLint's flat-config
  CLI.
- Add an explicit `typecheck` script.
- Fix TypeScript errors in the Playwright sources.
- Keep generated output and test artifacts outside lint/format inputs.
- Add the static gates to CI before the packaged E2E suites.

### Acceptance gates

- `pnpm typecheck` exits successfully.
- `pnpm lint` runs ESLint rather than interpreting `lint` as a Next.js path.
- `pnpm build` remains successful.
- CI invokes typecheck, lint, formatting, and build from the canonical UI.

## Slice 2 — Single application-services provider

**Goal:** Resolve runtime configuration and browser identity once and expose
one stable API client to the component tree.

### Work

- Add a root client-side provider composed from `RuntimeConfigProvider` and
  `ApiClientProvider`.
- Change `useRuntimeConfig` and `useApiClient` into context consumers.
- Retain one internal runtime-config loader and the existing base-path
  behavior.
- Collapse the duplicate loading gates in `MyRuntimeProvider`.

### Acceptance gates

- Only the root provider calls the internal config loader and identity hook.
- Every `useApiClient()` call observes the same `client`, `identity`, and
  `loaded` values for a render.
- Full and minimal presets still select correctly after `/api/config` loads.
- Packaged base-path checks and thread E2E tests pass.

## Slice 3 — Typed transport and domain API boundaries

**Goal:** Keep endpoint knowledge and untrusted-payload parsing out of React
components.

### Work

- Split API operations into typed services for threads, transcripts,
  feedback, agents, RAG/admin, and sharing.
- Add runtime validation/normalization for boundary payloads.
- Replace generic `client.request()` calls in components with domain methods.
- Define shared message and indexing DTOs; remove avoidable `any` casts.

### Acceptance gates

- Components contain no backend URL/path literals.
- Malformed payload tests demonstrate safe, visible failure behavior.
- API errors preserve status/code information used by current UI behavior.
- Existing backend-base and error-surfacing E2E suites pass.

## Slice 4 — Shared message conversion and runtime adapters

**Goal:** Remove duplicated full/minimal conversion logic and isolate
assistant-ui's unstable APIs.

### Work

- Extract a shared converter with explicit policies for optimistic messages
  and hydrated UI transcripts.
- Move remote thread-list adapter construction out of the React provider.
- Wrap unavoidable unstable assistant-ui APIs in one compatibility module.
- Add focused converter tests for tool calls, optimistic messages, IDs, and
  hydrated transcripts.

### Acceptance gates

- Full and minimal presets use the same conversion core.
- No unstable assistant-ui API is imported by presentation components.
- Message order, stable IDs, reload hydration, and feedback persistence are
  covered and passing.

## Slice 5 — Decompose the thread feature

**Goal:** Turn `components/assistant-ui/thread.tsx` into a small composition
root.

### Work

- Extract presentational modules: shell/header, starter, composer, messages,
  action bars, branch picker, and errors.
- Extract behavioral hooks/components: auto-title, active-thread persistence,
  initialization, orphan pruning, and transcript synchronization.
- Move feedback into `features/feedback` and indexing status into
  `features/rag`.
- Preserve existing public DOM hooks.

### Acceptance gates

- The thread composition root is under 200 lines.
- Extracted modules have a single primary responsibility.
- No module-level mutable synchronization sets/maps remain.
- Full UI desktop/mobile inspection and thread-sync suites pass without DOM
  contract regressions.

## Slice 6 — Capability-driven feature and tool registry

**Goal:** Make adding a tool or optional feature declarative.

### Work

- Define a registry mapping runtime capabilities to tool UI registrations,
  navigation, status panels, and optional routes/actions.
- Register graph and Web RAG tools through the same extension mechanism.
- Enforce `assistant`, `threads`, `transcripts`, and tool capability flags.
- Hide or disable sharing until a real share endpoint and route exist.

### Acceptance gates

- Disabled capabilities issue no related network requests and render no
  related controls.
- Adding a tool does not require editing `Thread`.
- Every enabled navigation/action has an implemented destination and API
  contract.
- Tool-availability and generative-UI E2E suites pass.

## Slice 7 — RAG and graph feature cleanup

**Goal:** Separate data normalization, polling, visualization, and controls.

### Work

- Split `source-indexing-widget.tsx` into normalizers, polling hooks, and
  focused panels.
- Split `GraphToolUI.tsx` into validation, simulation, controls, and tool
  registration.
- Give SVG marker IDs per-instance uniqueness and strengthen D3 types.
- Pause polling when jobs finish or the page is not visible.

### Acceptance gates

- Pure payload normalizers have unit coverage.
- Multiple graph instances render without marker-ID collisions.
- Polling starts/stops deterministically and is capability-gated.
- No `any` remains in the graph/RAG feature modules.

## Slice 8 — Admin feature and error/loading conventions

**Goal:** Make admin behavior typed, composable, and resilient.

### Work

- Move admin queries into the RAG domain service and reusable polling hook.
- Split overview, jobs, source previews, and test search into components.
- Add consistent loading, empty, and error states.
- Replace raw buttons/inputs with shared accessible UI primitives.

### Acceptance gates

- Admin failures are visible and recoverable; no unhandled promise rejection
  is produced.
- Poll requests do not overlap.
- Admin is inaccessible or clearly unavailable when capability-disabled.
- Admin DOM/accessibility inspection passes.

## Slice 9 — Legacy frontend consolidation

**Goal:** Establish one source of truth without breaking documented Compose
workflows.

### Work

- Inventory contracts still requiring `frontend-full` or `frontend-minimal`.
- Choose and document one path: migrate Compose to the unified frontend,
  generate legacy builds from it, or extract a shared workspace package.
- Update docs, skills, Compose files, and CI together.
- Remove legacy trees only after their consumers have migrated.

### Acceptance gates

- No maintained component exists as manually synchronized copies.
- Minimal/full Compose and packaged deployment workflows remain documented
  and tested.
- Dependency versions come from one maintained manifest or workspace policy.

### Implemented consolidation decision

Both split Compose stacks now build `application/frontend/frontend`; their
existing service names and ports remain stable, while each backend's
`/api/config` manifest selects the runtime preset and capabilities. The full
RAG backend now publishes that manifest. The manually synchronized
`frontend-full` and `frontend-minimal` trees were removed, leaving one package
manifest and lockfile. Historical `.agent-recon` notes retain old paths only as
an audit record.

## Initial implementation status

- [x] Slice 1 — Restore engineering gates
- [x] Slice 2 — Single application-services provider
- [x] Slice 3 — Typed transport and domain API boundaries
- [x] Slice 4 — Shared message conversion and runtime adapters
- [x] Slice 5 — Decompose the thread feature
- [x] Slice 6 — Capability-driven feature and tool registry
- [x] Slice 7 — RAG and graph feature cleanup
- [x] Slice 8 — Admin feature and error/loading conventions
- [x] Slice 9 — Legacy frontend consolidation
