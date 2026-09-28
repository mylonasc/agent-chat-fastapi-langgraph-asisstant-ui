Parent: #22

Priority: P0

## Why

All backends directly depend on a minimally released pre-1.0 streaming package.
The dependency should remain for now, but protocol changes must be contained and
detectable.

## Implementation

- Pin `assistant-stream-ce` to an intentionally supported version.
- Create a repository-owned transport adapter that exclusively owns
  `ChatRequest`, run control, LangGraph event merging, and response encoding.
- Replace direct imports in canonical backend code.
- Add golden fixtures for state operations, message chunks, tools, errors,
  completion, and content type.
- Document the protocol boundary and criteria for later replacement.

## Acceptance Criteria

- Application/session/agent modules do not import `assistant-stream-ce`.
- Existing frontend behavior remains unchanged.
- Golden tests fail on framing or merge-semantic drift.
- Supported Python and frontend protocol versions are explicit.

## Dependencies

- PUIR-01
- Coordinates with PUIR-02
