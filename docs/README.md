# Documentation Map

## Fastest Local Ollama Route

Read the [Ollama quick start](../packages/agent-chat-minimal/src/agent_chat_minimal/docs/ollama-quickstart.md)
for the current starter-based workflow (no custom agent code for local defaults).
It includes Python 3.12 selection, installing the Ollama extra, pulling a
tool-capable model, endpoint customization, SQLite directories, and live
streaming/context/history checks. The tool-free built-in chat shortcut in
[issue #70](https://github.com/mylonasc/agent-chat-fastapi-langgraph-asisstant-ui/issues/70)
is a proposal, not an available command on this branch.

Agents using the installed enhanced package can run
`minimal-chat-docs show ollama-quickstart` or discover it through
`minimal-chat-setup describe --json`.

## Architecture

The repository has a canonical portable application and two split development
stacks:

1. `packages/agent-chat-minimal` is the canonical non-RAG application. It
   contains the FastAPI app factory, agent discovery, assistant-stream
   transport, optional SQLite persistence, and a unified static UI. A built
   wheel runs the API and UI from one Python process on port 8011.
2. `docker-compose.minimal.yml` starts that packaged application through its
   compatibility backend plus the unified frontend's minimal preset on port 3000.
3. `docker-compose.full.yml` starts a separate source-run RAG backend on port
   8010 plus the unified frontend's full preset on port 3001. Its Web Search and RAG tool
   routes are not part of the portable package.

## Guides

- [Packaged app](packaged-app.md): the recommended path for serving the
  portable application, including local wheel builds and persistence.
- [Docker Compose](docker-compose.md): split-stack development workflows.
- [OpenInference + Phoenix example](../application/backend/full/examples/phoenix_monitoring/README.md):
  trace the full RAG agent's graph, model calls, tools, and retrievers locally.
- [Implementing agents](implementing-agents.md): graph contract, application
  embedding, named registries, and distributable plugins.
- [Migration to packaged app](migration-to-packaged-app.md): short statement of
  what is canonical and what remains a legacy development extension.

The package also ships its own guides in the installed wheel. Run
`python -c 'from agent_chat_minimal import docs; docs.show("agents")'` after
installation, or read them under
`packages/agent-chat-minimal/src/agent_chat_minimal/docs/` in this checkout.
