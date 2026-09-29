# Setup engine and future TUI

One offline setup engine serves scripts, the non-interactive initializer, and
a future optional TUI. Import it from `agent_chat_minimal.setup`:

```python
from agent_chat_minimal import StarterOptions, diagnose_options, describe_setup

options = StarterOptions(provider="ollama", model="llama3.1:8b", preset="full")
report = diagnose_options(options)
print(report.to_json())
```

## Contracts

- `StarterOptions`: versioned serializable inputs (project/package names,
  provider, model, preset, persistence, endpoint, credential env reference,
  model kwargs). Unknown fields fail validation.
- `GenerationPlan`: versioned serializable preview of what the AGS-04
  generator will write (target dir, names, provider/model, preset,
  persistence, expected files, required extras). AGS-04 implements the
  template-backed `plan()`/`generate()` methods behind the
  `StarterGenerator` protocol.
- `Diagnostic`/`SetupReport`: stable codes, field paths, remedies, and exit
  statuses. `exit_status_for(...)` returns `0` for clean validation and `2`
  for errors. Warnings (for example `unknown_provider`) do not fail
  validation, so custom LangChain integrations stay supported.
- `list_providers()` / `get_provider_descriptor()` /
  `register_provider_descriptor()`: wizard metadata for OpenAI, Ollama, and
  LiteLLM, plus an extension point for other integrations.
- `get_config_schema()`: the versioned `agent_chat.yaml` JSON Schema shipped
  in the wheel.
- `describe_setup()`: contract version, providers, presets, persistence
  modes, config schema id, and the wizard flow
  (`project → provider → endpoint → environment_references → model →
  preset → questions → storage → preview → generate → diagnose`).

## Offline guarantees

Validation never installs dependencies, downloads models, resolves
credential values, or makes network calls. Reports always carry
`connectivity: "not_tested"`. Explicit live checks (for example
`minimal-chat-serve --check` with real credentials) are separate and
opt-in. Diagnostics serialize to JSON without credential values; only
environment variable names are stored.

The base package has no TUI dependency. A future TUI presents these
options, previews the `GenerationPlan`, asks for confirmation, then
generates. Cancellation performs no writes.
