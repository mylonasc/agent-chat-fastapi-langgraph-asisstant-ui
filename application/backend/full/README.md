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

## HTTP Tool Administration

All `/tools/web_rag/*`, `/tools/web_search/*`, and `/tools/overview` HTTP
endpoints require an authorized administrator, including configuration reads
and writes, index/job status, searches, indexing, and downloads. They return
JSON `503` while administration is disabled (the default).

For local administration, set a strong random `FULL_ADMIN_TOKEN` in the
backend environment (or repository `.env` for Compose), then send it as a
bearer credential:

```bash
curl -H "Authorization: Bearer $FULL_ADMIN_TOKEN" \
  http://localhost:8010/tools/web_rag/configuration
```

With a token configured, missing/invalid credentials return JSON `401`.
The token grants global tool administration; `user_id` selects a data namespace,
not an identity. Keep the token server-side, use HTTPS outside localhost, and
never put it in `NEXT_PUBLIC_*`, browser bundles, or a URL. The legacy frontend
does not send admin credentials, so its HTTP tool/admin controls cannot access
these APIs by default. Do not bypass authorization to restore those controls.

Deployments with authentication can instead install a trusted sync or async
resolver accepting a FastAPI `Request`:

```python
from fastlang.server.server import app
from tools.authorization import AdminPrincipal

async def resolve_admin(request):
    user = await authenticate_request(request)  # Your verified JWT/session integration
    if user is None:
        return None
    return AdminPrincipal(subject=user.subject, is_admin=user.is_admin)

app.state.admin_principal_resolver = resolve_admin
```

The resolver is authoritative: it disables local-token fallback. It returns
`None` for unauthenticated requests (`401`), or an `AdminPrincipal`; non-admin
principals are rejected with `403`. Client-supplied subject/role headers are
not proof of authentication.

**Security boundary:** this only protects HTTP tool administration. Legacy
`/assistant` and `/threads` routes and agent-invoked tools do not gain trusted
identity or namespace isolation from this change. Agent tools can still access
RAG data through chat. Do not expose this demo as a public or multi-user service;
place the entire backend behind authentication until those boundaries are
migrated. This backend is not the packaged app's authenticated composition.
