# Coding-agent onboarding

Start here to inspect the installed library and create a baseline chat website.
All documentation, discovery, validation, and generation commands work offline.
Installing dependencies and running a real model are separate, explicit actions.

**Want a local Ollama website quickly?** Start with
`minimal-chat-docs show ollama-quickstart` ([guide](ollama-quickstart.md)).
It covers model availability, Python 3.12, the no-custom-code starter route,
endpoint selection, SQLite directories, and an explicit live smoke test. The
tool-free `--agent chat` shortcut proposed in issue #70 is not available yet.

## 1. Discover the installed capabilities

```bash
minimal-chat-setup describe --json
minimal-chat-docs list --json
minimal-chat-docs show starter
minimal-chat-docs search "persistence" --limit 5 --json
minimal-chat-setup schema --json
```

`describe` returns provider metadata, presets, storage choices, a guide catalog,
and command argv arrays. `schema` returns the actual bundled JSON Schema;
its `$id` is an identifier, not a URL you need to fetch. `minimal-chat-docs`
without a subcommand prints this guide. Search is case-insensitive literal
line matching, not regex or semantic search. Results include guide name,
one-based line number, heading, and excerpt. No matches is a successful empty
result. Use `show <guide>` to follow a result or read a linked local guide.

Python access is also available:

```python
from agent_chat_minimal import docs
from agent_chat_minimal.onboarding import describe

docs.catalog()  # names, titles, summaries
docs.get("agents")  # Markdown, no filesystem path assumptions
docs.search("checkpointer", limit=5)
describe()  # machine-readable onboarding metadata
```

The server's `/docs` endpoint is Swagger API documentation, not these library
guides. The installed package is the source of truth for its version's behavior.

## 2. Check local prerequisites

```bash
minimal-chat-setup doctor --provider openai --preset full --persistence sqlite --json
```

Doctor checks selected provider/storage dependencies, credential environment
variable presence, and the bundled UI. It never installs anything, imports
optional model integrations, contacts a provider, downloads a model, or prints
credential values. Missing prerequisites produce exit status 2 and structured
diagnostics with remedies. A successful result has `ready: true` and
`connectivity: "not_tested"`: it does not prove credentials are valid or that
the model supports tool calling. Unknown providers still require manual checks.
It examines the selected starter options, not an existing project's custom code
or deployment environment. Dependency/credential gaps do not prevent previewing
or generating a project for another environment.

## 3. Preview and generate a user-owned site

```bash
minimal-chat-init ./my-site --preset full --persistence sqlite --dry-run --json
minimal-chat-init ./my-site --preset full --persistence sqlite --json
```

Select `--provider ollama --model llama3.1:8b` for local Ollama.
For custom endpoints or credential names, use `ModelConfig` in the generated
helper (see `providers` and `ollama-quickstart`). The initializer currently
accepts `--base-url` and `--credential-env`, but does not forward those values
into its generated helper; do not rely on them alone to configure a live model.
Credential references must be environment variable names, never values.
The default initializer preset remains `minimal`
for compatibility; `full` enables the threaded UI.

Generation writes an editable agent, thin Python server, versioned YAML,
`pyproject.toml`, credential placeholders, offline tests, `AGENTS.md`, and
`starter-manifest.json`. JSON output includes the plan and next steps as argv
arrays, to run from the generated project directory. Preview writes nothing;
generation refuses non-empty destinations. Do not regenerate over user work.

## 4. Install, verify, and serve explicitly

```bash
cd my-site
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e '.[test]'
python -m pytest
export OPENAI_API_KEY=...  # use the secret manager/environment, not tracked files
my-site-serve --config ./agent_chat.yaml --check
my-site-serve --config ./agent_chat.yaml
```

Open http://localhost:8011/. Check `/health` for server health and `/agents`
for the registered helper agent. `.env` files are not automatically loaded.
`--check` constructs the graph but does not send a real model request. Tests
use a fake model and need no credentials or network. For Ollama, start its
daemon and install a tool-capable model separately.

## Scope and customization

- This scaffolds a chat website, not a general-purpose website or a new Next.js
  source project. The installed UI needs no Node.js or frontend build to run.
- Edit `agent_chat.yaml` to change presentation, proposed questions, model,
  and persistence; see `configuration` and `runtime-config`.
- Edit `src/my_site/agents/helper.py` to change behavior; see `agents`.
- `full` is the bundled threaded UI, not the separate RAG/admin demo backend.
- Installation, secret provisioning, model downloads, live checks, and production
  deployment are deliberately not performed by the initializer.

## Output contracts

Documentation and setup commands accept `--json` before or after their
subcommand. JSON data is written to stdout without progress messages.
Successful commands return 0; validation/lookup/prerequisite failures return 2.
Initializer JSON output includes `contract_version`, `ok`, `plan`, and
`next_steps`; errors include `code` and `diagnostics`. CLI syntax errors follow
standard argparse behavior (exit 2 and usage on stderr). Never log secrets or
pass credential values as initializer arguments.
