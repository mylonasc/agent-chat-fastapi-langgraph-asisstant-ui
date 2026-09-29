# Legacy Full Frontend

This frontend is used by `docker-compose.full.yml` with the separate RAG demo
backend at `application/backend/full`. It is not the static UI bundled in the
portable package.

Run the complete development stack from the repository root:

```bash
docker-compose -f docker-compose.full.yml up --build
```

The UI is available at <http://localhost:3001> and calls the backend at port
8010. For standalone frontend work, set
`NEXT_PUBLIC_API_BASE=http://localhost:8010` before `pnpm dev`. Do not put
provider secrets in the frontend. See the [Docker Compose guide](../../../docs/docker-compose.md).
