Parent: #22

Priority: P0

## Why

Known contract defects would obscure later refactor regressions. Fix these on
the current architecture before moving code.

## Implementation

- Use `resolve_thread_id()` in the live assistant route, including
  `runConfig.thread_id`.
- Remove model-agnostic `OPENAI_API_KEY` gating and report provider-specific
  initialization failures.
- Reserve API prefixes such as `/tools` from SPA fallback so missing endpoints
  return JSON errors rather than HTML.
- Validate the configured default agent during app creation.
- Correct docs that contradict current custom-agent replacement behavior.
- Add focused regression tests without broad restructuring.

## Acceptance Criteria

- Ollama/Anthropic model selection is not blocked by an OpenAI key check.
- All documented thread ID locations work through `POST /assistant`.
- Unsupported `/tools/*` calls never return SPA HTML.
- Invalid default agents fail at startup with an actionable error.
- Tests cover every corrected contract.

## Dependencies

None. This is the first implementation issue.
