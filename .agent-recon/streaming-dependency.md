# `assistant-stream-ce` Reconnaissance

## Role in the Repository

`assistant-stream-ce` is the Python bridge between LangGraph and Assistant UI.
All three backend variants import it directly:

- package: `packages/agent-chat-minimal/src/agent_chat_minimal/server.py:11-14`;
- full backend: `application/backend/full/fastlang/server/server.py:1-4`;
- legacy minimal backend:
  `application/backend/langgraph-server-minimal/server.py:5-8`.

It owns four critical concerns:

1. Request validation with `ChatRequest`.
2. Run lifecycle and state-diff generation with `create_run` and
   `RunController`.
3. LangGraph chunk aggregation with `append_langgraph_event`.
4. Tagged wire serialization with `DataStreamResponse`.

The repository has no local abstraction around those responsibilities.

## Exact Coupling

The packaged server subclasses dependency-owned `ChatRequest` to add thread and
user fields (`server.py:72-76`). This means dependency model changes affect the
FastAPI schema and validation.

`RunController.state` is a mutation-observing proxy, not a plain dictionary.
Application code mutates nested state and relies on generated state operations.

`append_langgraph_event` performs nontrivial behavior:

- accepts namespaced LangGraph event tuples;
- converts and merges incremental `AIMessageChunk` objects;
- identifies messages/tool calls by IDs;
- appends tool messages;
- maps non-message update channels into state.

Application code adds custom `tool_updates`, then delegates core event merging
to the library.

`DataStreamResponse` emits newline-delimited tagged records, including text,
reasoning, tool begin/argument/result, data, error, source, and `aui-state`
operations. It is served as `text/plain`, not standard `text/event-stream` SSE.
Repository docs that call it SSE are imprecise.

The dependency request schema accepts `add-tool-result`, but repository
backends only process `add-message`. That is an application gap, not proof the
dependency supports the full desired behavior automatically.

## Frontend Consumers

Both frontends use `useAssistantTransportRuntime`; this is the actual protocol
consumer. They subsequently convert LangChain-shaped state with
`convertLangChainMessages`.

The full frontend's only direct `assistant-stream` source import is a type used
for an empty title stream. Most coupling is transitive through Assistant UI
transport packages.

`@assistant-ui/react-data-stream` is declared in both frontends but unused.
The full app's AI SDK route is also unused. These are possible migration paths,
not current adapters.

## Version Status

Python manifests specify `assistant-stream-ce>=0.0.2`. Application lockfiles
resolve exactly `0.0.2`, but the published package has no lockfile for consumer
resolution. The package is pre-1.0, minimally released, and exposes a small
maintenance/governance surface. Imports reach into submodules such as
`modules.langgraph` and `serialization`.

At reconnaissance time, PyPI had only `0.0.1` and `0.0.2`, with `0.0.2` latest.
The project describes itself as a lightly adapted extraction. License metadata
was inconsistent.

Frontend lockfiles resolve Assistant Stream `0.2.45`/`0.2.46`, while the wider
ecosystem has a `0.3.x` generation. Minimal can contain both direct 0.2.45 and
transitive 0.2.46. There is no explicit cross-language compatibility pin or
golden protocol contract.

## Alternatives Already Present

### AI SDK UI Message Stream

`frontend-full/app/api/chat/route.ts` uses Vercel AI SDK `streamText()` and
`toUIMessageStreamResponse()`. It is not connected to the active runtime and
cannot run in the packaged static export, but proves a second protocol was
considered.

### Assistant UI Data Stream

`@assistant-ui/react-data-stream` is installed but unused. Moving to it would
require coordinated frontend/backend protocol work and likely package upgrades.

### Local Chat Model Adapter

Repository notes describe `useLocalRuntime` with a custom `ChatModelAdapter`.
This could consume a repository-owned SSE/NDJSON protocol but would require
reimplementation of current command/state semantics.

### Local Compatibility Implementation

Only four Python surfaces are used, so vendoring/reimplementing the current
subset is feasible. The hard part is semantic compatibility: proxy mutations,
incremental chunk merges, tool-call assembly, errors, substreams, cancellation,
and ordering.

## Option Assessment

### Retain Unchanged

Cost: low. Risk: moderate.

The current code works, but direct coupling, open pre-1.0 version constraints,
old frontend protocol generation, and limited upstream history make upgrades
risky.

### Pin and Isolate

Cost: low to medium. This is the recommended near-term path.

Add a repository-owned transport module exposing concepts such as:

```text
TransportRequest
stream_graph_run(...)
append_graph_event(...)
AssistantProtocolResponse
```

Only that module imports `assistant-stream-ce`. Agent/session/routes should not
know the concrete dependency.

### Reimplement Current Protocol

Cost: medium. This reduces supply-chain risk but transfers subtle protocol
maintenance to this project. Do it only with comprehensive golden fixtures and
browser integration tests.

### Migrate Protocol

Cost: high. A raw local runtime or AI SDK/data-stream migration changes request
DTOs, event conversion, tool representation, optimistic commands, converters,
history, errors, and frontend hooks. It should follow, not precede, clearer
application and persistence boundaries.

## Required Contract Tests

Current tests mainly assert HTTP status and visible happy-path behavior. Add
golden tests for:

- content type and exact framing;
- initial/full state operations;
- incremental AI chunk merge;
- stable IDs and ordering;
- tool-call begin, argument delta, and result;
- custom tool progress;
- graph updates and namespaced events;
- error framing and completion;
- disconnect/cancellation behavior;
- `add-message` and `add-tool-result` requests;
- frontend consumption of recorded fixtures;
- compatibility across deliberately supported JS/Python package versions.

## Recommendation

Keep `assistant-stream-ce` during the configuration and persistence redesign.
Pin it exactly, isolate it behind a local adapter, and add protocol fixtures.
After the canonical package has stable transport, session, and UI capability
contracts, evaluate either:

1. a local compatibility implementation preserving the wire protocol; or
2. a deliberate migration to a newer documented Assistant UI/data-stream
   protocol.

Replacing it now would combine protocol migration with storage, identity,
frontend consolidation, and package redesign, creating unnecessary risk.
