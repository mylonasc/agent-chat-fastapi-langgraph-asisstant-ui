# Minimal and Full Frontend Reconnaissance

## Architecture

Both frontends are statically exported Next.js Assistant UI applications.

### Minimal

- Entry: `application/frontend/frontend-minimal/app/page.tsx:6-13`.
- Runtime: `app/MyRuntimeProvider.tsx:118-151`.
- Uses one `useAssistantTransportRuntime`.
- Initial state is an empty message list.
- API is `NEXT_PUBLIC_API_URL` or same-origin `/assistant`.
- Registers one specialized `render_graph` tool UI.
- Has no remote threads, session management, admin, or feedback.

### Full

- Entry: `application/frontend/frontend-full/app/page.tsx:1-5`.
- Composition: `app/assistant.tsx:11-43`.
- Provider: `app/MyRuntimeProvider.tsx:22-166`.
- Uses unstable remote thread-list runtime plus one assistant transport runtime
  per selected thread.
- Supports thread CRUD, hydration, auto-title, admin link, share button,
  reasoning, RAG/search renderers, and indexing polling.

## API and Protocol Contract

Both UIs send Assistant Transport commands/state, not an ordinary chat
completion request. Backends explicitly process text-bearing `add-message`
commands. Attachments are displayed in the UI but not represented by the
backend reducer. `add-tool-result` is documented but not clearly handled.

The response is the Assistant Stream state protocol. The frontend depends on:

- `useAssistantTransportRuntime`;
- streamed state operations;
- LangChain-shaped messages;
- `convertLangChainMessages`;
- backend ordering and tool-call IDs.

This means arbitrary SSE/token streams are not drop-in replacements.

The full app contains `app/api/chat/route.ts`, a separate Vercel AI SDK/OpenAI
route. It is unused and incompatible with the static export runtime model. It
should be removed or treated as an explicit future experiment.

## Thread Adapter

`frontend-full/app/MyRuntimeProvider.tsx:87-155` maps:

- list to `GET /threads?user_id=default_user`;
- fetch to `GET /threads/{id}`;
- initialize to `POST /threads`;
- rename to `PATCH /threads/{id}`;
- archive/unarchive to POST subroutes;
- delete to `DELETE /threads/{id}`;
- history to `GET /threads/{id}/messages`.

Hydration (`MyRuntimeProvider.tsx:40-78`) fetches messages and calls
`unstable_loadExternalState` through `any` casts. It does not check response
status before JSON parsing, has no user-visible retry state, can skip hydration
when any runtime messages exist, and depends on unstable APIs.

No history adapter calls `POST /threads/{id}/messages`, despite backend support.
Exact Assistant UI tool/message payloads are therefore not normally persisted.

Both converters replace IDs with array indexes:

- minimal `MyRuntimeProvider.tsx:104-115`;
- full `MyMessageConverter.tsx:37-50`.

This is unsuitable for durable feedback or robust branching.

## Static Export and Runtime Configuration

Both applications use `output: "export"`, trailing slashes, and unoptimized
images.

Values requiring a rebuild today:

- minimal `NEXT_PUBLIC_API_URL`;
- full `NEXT_PUBLIC_API_BASE` / `NEXT_PUBLIC_API_URL`;
- `FULL_UI_BASE_PATH`;
- feature visibility and admin availability;
- tool renderer registration;
- hard-coded user/session values;
- branding, text, fixed headers/body, route structure.

The full API base is duplicated in:

- `app/MyRuntimeProvider.tsx:14-17`;
- `app/admin/page.tsx:6-9`;
- `components/assistant-ui/thread.tsx:51-54`;
- `components/assistant-ui/source-indexing-widget.tsx:18-21`.

There is no runtime config JSON, global injected config, or capability endpoint.

The wheel builds full UI with `NEXT_PUBLIC_API_BASE=""` and
`FULL_UI_BASE_PATH=/full`, making API calls same-origin while assets live under
`/full`. This is a good portable default but cannot target arbitrary browser
API URLs after packaging.

Runtime-configurable without rebuilding:

- browser origin when relative paths are used;
- reverse-proxy routing;
- backend model, credentials, tools, storage, and persistence;
- mounted static directory overrides.

## Recommended Runtime Configuration

Preserve static export and add a non-hashed same-origin endpoint such as
`GET /api/config` or `/runtime-config.json` with:

```json
{
  "apiBase": "",
  "uiVariant": "full",
  "features": {
    "threads": true,
    "feedback": true,
    "admin": false,
    "webRag": false,
    "sharing": false,
    "attachments": false
  },
  "identity": {
    "mode": "anonymous-session"
  },
  "tools": []
}
```

The UI should load this before creating its runtime. Keep `/full` base path as a
release convention unless there is a compelling need to relocate assets.

An alternative is to formalize same-origin deployment as the only supported
contract. That is simpler and avoids CORS, but still needs capability and
identity configuration.

## Full UI Feature Mismatches

### Admin

`app/admin/page.tsx:22-173` exposes RAG configuration/status, jobs, previews,
downloads, and test search. It is unauthenticated, polls every two seconds, and
assumes routes absent from the packaged backend. Fetch error handling is weak.

### Tool Renderers

Full UI statically registers `web_search`, `web_rag`, and `web_rag_status`
(`source-indexing-widget.tsx:487-530`; mounted at `thread.tsx:76-79`). Unknown
tools use a fallback. Static registration means backend-discovered tools cannot
gain specialized UI at runtime without a frontend extension mechanism.

Widgets can create multiple 1.2-second polling loops. Server-side capability
and authorization checks remain mandatory; tool arguments/results are not a
trusted source of user identity.

### Share

`share-button.tsx:14-31` copies `${origin}/share/${threadId}`. No matching page
exists, threads are not made public, and `/full` is omitted. The feature is
nonfunctional and should be hidden until implemented end to end.

### Feedback

There is no feedback UI. Add stable message IDs and backend persistence first,
then implement direct positive/negative actions. Do not rely on the installed
feedback adapter until its compatibility with the selected Assistant UI runtime
is verified.

### Identity

There is no auth/session provider. `default_user` is hard-coded throughout
thread and RAG requests. The sidebar cookie only stores visual state.

For a useful packaged baseline, support an anonymous browser session ID stored
in a secure-ish first-party cookie or local storage and sent through one API
client. For secure deployments, allow an injected identity resolver/middleware
to override it. Never present anonymous IDs as authentication.

## Duplication and Dependency Drift

Minimal/full duplicate thread, attachment, Markdown, tool fallback, tooltip,
button, dialog, avatar, and utility components, but their copies differ.

Dependency versions also differ:

- Next 16.1.0 vs 16.0.10;
- Assistant UI React 0.11.52 vs resolved 0.11.51;
- LangGraph adapter 0.7.12 vs 0.7.13;
- data-stream 0.11.13 vs a 0.11.12 range;
- exact vs ranged React versions.

The full frontend retains unused AI SDK dependencies. The full lock also has
peer-version warnings where adapters request newer `@assistant-ui/react` than
the app resolves.

Recommended consolidation sequence:

1. Align Next, React, Assistant UI, and Tailwind versions.
2. Extract API base/config loading and typed client.
3. Extract transport message conversion.
4. Extract common visual primitives only after behavior is aligned.
5. Define a tool-renderer registry and feature/capability contract.
6. Keep minimal/full as thin composition shells, or replace them with one app
   whose runtime config selects features.

## Options

### One Configurable Static App

Most maintainable long-term: one static frontend with feature flags for
minimal/full modes. This removes duplicated transport, converter, and UI code
while retaining two entry URLs or named presets. The risk is accidentally
inflating minimal behavior/bundle and coupling advanced components.

### Shared Core, Two Shells

Lower migration risk: retain two applications but extract config, API client,
transport adapter, message conversion, and shared components into a workspace
package. Build both exports into the wheel.

### Server-Hosted Next

Provides easy runtime env/auth/share routes but violates the hard requirement
unless a separate Node service becomes mandatory. It should not be the default
packaged architecture.

### Custom Stream Transport

Can remove Assistant Stream coupling but requires commands, cancellation,
tools, errors, state reconciliation, optimistic updates, and history to be
redesigned. Not a quick configurability win.

## Current Test Findings and Gaps

The repository has Playwright DOM/layout tests, full tool tests, backend thread
tests, and a live two-turn message-order test.

Missing coverage:

- both static builds on every relevant CI run;
- actual generated `/full/` export served from a wheel;
- same-origin and external API base modes;
- runtime config load/failure/default behavior;
- capability hiding against the packaged backend;
- first-message thread initialization races;
- thread switching while hydration is pending;
- HTTP/non-JSON errors for every adapter call;
- rich tool history after reload;
- attachments or hidden attachment controls;
- cancellation and thread switches;
- protocol fixture compatibility;
- admin authorization/isolation;
- polling request counts and cleanup;
- feedback persistence;
- share route only after it exists;
- base-path correctness for manually generated links.

A read-only type check found the full frontend passing. Minimal failed in
`components/tools/GraphToolUI.tsx` because D3 declarations were not resolved,
causing implicit `any` callbacks despite `@types/d3` being declared. Clean
install type checks should run before packaging.
