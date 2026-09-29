# Full RAG Demo Backend

This is a separate source-run FastAPI demo with Web Search and RAG tool routes.
It is not included in the portable `agent-chat-minimal` package and has no
plugin agent registry. Use it when developing the full RAG experience; use the
packaged application for new portable non-RAG agents.

Run the backend from this directory:

```bash
./start_server.sh
```

The recommended full-stack development command is:

```bash
docker-compose -f docker-compose.full.yml up --build
```

This exposes the backend at <http://localhost:8010> and the full frontend at
<http://localhost:3001>. Configure `OPENAI_API_KEY` and, for Web Search,
`SERPER_API_KEY` in the repository `.env`; see the
[Docker Compose guide](../../../docs/docker-compose.md) for optional RAG
environment variables and architecture boundaries.
