# Transport protocol boundary

`agent_chat_minimal.transport` is the canonical package's only integration
point with `assistant-stream-ce`. It owns the request base model, run lifecycle
and controller typing, LangGraph event merging, and HTTP response encoding.
Application, agent, session, and composition code must import these concepts
from the local module rather than the third-party package.

## Supported generation

The Python package intentionally supports exactly `assistant-stream-ce==0.0.2`.
Its response is the Assistant Stream 0.2.x generation consumed by the bundled
frontends' `useAssistantTransportRuntime`. The frozen frontend dependency trees
contain `assistant-stream` 0.2.45 and 0.2.46; this does not claim compatibility
with the newer 0.3.x generation.

The wire format is newline-delimited tagged records served as `text/plain`.
It is not SSE. Representative state, incremental message, tool, data, custom
update, error, and clean-EOF behavior is locked by package golden tests.
Successful completion in 0.0.2 is stream EOF; there is no completion record.

## Replacement criteria

Replace the dependency only when a local compatibility implementation or a
coordinated frontend protocol migration can preserve or deliberately migrate:

- request commands and state initialization;
- ordered state operations and incremental LangGraph message merging;
- stable message and tool-call identifiers;
- tool arguments, results, custom progress, and error framing;
- clean completion, cancellation, and disconnect behavior;
- both bundled frontends and their thread/history conversion behavior.

Any replacement must run the Python protocol goldens and browser integration
tests against both frontend variants. A migration to Assistant Stream 0.3.x,
Assistant UI Data Stream, or AI SDK UI Message Stream is a protocol change and
must update frontend and backend dependencies together rather than relaxing the
Python pin.
