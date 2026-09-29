# Documentation Map

## Architecture

The repository has a canonical portable application and two split development
stacks:

1. `packages/agent-chat-minimal` is the canonical non-RAG application. It
   contains the FastAPI app factory, agent discovery, assistant-stream
   transport, optional SQLite persistence, and a unified static UI. A built
   wheel runs the API and UI from one Python process on port 8011.
2. `docker-compose.minimal.yml` starts that packaged application through its
   compatibility backend plus the legacy minimal Next.js frontend on port 3000.
3. `docker-compose.full.yml` starts a separate source-run RAG backend on port
   8010 plus the legacy full frontend on port 3001. Its Web Search and RAG tool
   routes are not part of the portable package.

## Guides

- [Packaged app](packaged-app.md): the recommended path for serving the
  portable application, including local wheel builds and persistence.
- [Docker Compose](docker-compose.md): split-stack development workflows.
- [Implementing agents](implementing-agents.md): graph contract, application
  embedding, named registries, and distributable plugins.
- [Migration to packaged app](migration-to-packaged-app.md): short statement of
  what is canonical and what remains a legacy development extension.

The package also ships its own guides in the installed wheel. Run
`python -c 'from agent_chat_minimal import docs; docs.show("agents")'` after
installation, or read them under
`packages/agent-chat-minimal/src/agent_chat_minimal/docs/` in this checkout.
