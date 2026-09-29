# Agent starter projects

Generate a user-owned project with an editable agent, thin server
composition, versioned configuration, and relocatable UI resolution:

```bash
minimal-chat-init ./my-agent --provider ollama --preset full --persistence sqlite
minimal-chat-init ./my-agent --dry-run   # print the plan, write nothing
```

## What generation does (and does not do)

- Validates options through the shared setup engine (`agent_chat_minimal.setup`).
- Renders `pyproject.toml`, `agent_chat.yaml`, `.env.example`, `.gitignore`,
  `README.md`, `starter-manifest.json`, `src/<package>/agents/`,
  `src/<package>/server.py`, `src/<package>/ui.py`, and offline tests.
- Fails when the destination exists and is not empty; existing projects are
  never overwritten, so reruns cannot clobber user edits.
- Never installs dependencies, downloads models, or makes remote calls.
  Credentials ship as environment placeholders only.

## Run the generated project

```bash
cd my-agent
pip install -e .[test]
export OPENAI_API_KEY=...   # or your provider's credential
my-agent-serve --config ./agent_chat.yaml
my-agent-serve --check       # build the helper graph and exit
pytest                       # offline tests
```

`agent_chat.yaml` paths resolve relative to the file, so the project works
from any working directory and after relocation. The UI resolves through
`bundled_ui_dir()` at startup with an optional project `web/` override —
no absolute site-packages paths, no copied bundles.

## Ownership and upgrade policy

Generated code is yours: edit agents, questions, and presentation freely.
Library upgrades never touch the project — upgrade by bumping the pinned
`agent-chat-fastapi-langgraph-assistant-ui==x.y.z` bound in `pyproject.toml`
(the exact tested version ships in `starter-manifest.json`) and rerunning
`pytest`. Regenerating over an existing project is refused by design; apply
upstream template changes by hand.

## Full preset vs. the RAG backend

The `full` preset is the packaged threaded UI served by this same library —
not the separate `application/backend/full` RAG demo, which has its own
server, admin views, and data volume. Starter projects serve either preset
from one composition; RAG migration is out of scope.
