# Monitor the full agent with OpenInference + Phoenix

This opt-in launcher serves the **existing** `fastlang.server.server:app` and
`make_web_rag_search_agent` graph, not a replacement toy agent. OpenInference's
LangChain instrumentation captures LangGraph runs, nodes, LLM calls, tool calls,
and LangChain retrievers; Phoenix receives the OpenTelemetry traces over OTLP/HTTP.
The normal backend entry point remains uninstrumented.

## 1. Start Phoenix

From the repository root (Docker Compose v2):

```bash
docker compose -f application/backend/full/examples/phoenix_monitoring/compose.yml up -d
```

Open <http://localhost:6006>. The named volume preserves traces across restarts.
The collector image is pinned by digest for reproducible deployments.
Only the loopback interface is exposed. Recent Phoenix
images enable authentication by default, even though this Compose file does not
set authentication options.

If prompted to log in, use `admin@localhost` / `admin` on a fresh volume and
choose a new password. Then create a **system API key** in Phoenix Settings.
The backend needs that key to export traces; logging into Phoenix in your browser
does not authenticate the exporter. Existing volumes retain your changed password.

## 2. Start the instrumented full backend

From the repository root, using Python 3.11+ and `uv`:

```bash
cd application/backend/full
export OPENAI_API_KEY=sk-...
# Needed only for web_search, not the local index status tool:
export SERPER_API_KEY=...
export AGENT_MODE=react
export PHOENIX_PROJECT_NAME=full-agent
export PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006/v1/traces
# Required when Phoenix authentication is enabled; use the system API key,
# not your login password. Keep it out of version control.
export PHOENIX_API_KEY='<your-system-api-key>'
uv run --extra phoenix python -m examples.phoenix_monitoring.serve
```

Alternatively, keep credentials in the repository's untracked `.env` and use
`uv run --env-file ../../../.env --extra phoenix python -m examples.phoenix_monitoring.serve`.
Do not run the normal backend on port 8010 at the same time. Phoenix runs in
Docker, but this backend runs on the host, so its collector URL is `localhost`,
not a Compose service name. The launcher intentionally uses one process and no
reload so instrumentation is installed in the process executing the graph.

Port 8010 serves the API, not the chat UI: `/` returns `404 Not Found` by design.
Use <http://localhost:8010/health> or <http://localhost:8010/docs> to check the
backend, and start the separate frontend below for browser chat on port 3001.

## 3. Exercise the actual streaming API

In another terminal:

```bash
curl -N http://localhost:8010/assistant \
  -H 'Content-Type: application/json' \
  -d '{
    "thread_id": "phoenix-demo",
    "user_id": "default_user",
    "state": {"messages": []},
    "commands": [{
      "type": "add-message",
      "message": {
        "role": "user",
        "parts": [{"type": "text", "text": "Use web_rag_status to check whether my local index is ready. Do not search the web."}]
      }
    }]
  }'
```

For the full browser UI, run the frontend separately in
`application/frontend/frontend` with `pnpm install` then
`NEXT_PUBLIC_API_BASE=http://localhost:8010 pnpm dev --port 3001`.
Open <http://localhost:3001> and send the same prompt.

## 4. Inspect Phoenix

Select the **full-agent** project at <http://localhost:6006> after the response
finishes (allow a few seconds for batch export). A typical ReAct trace is:

```text
LangGraph
  agent
    ChatOpenAI                       LLM: messages, model, token usage
  tools
    web_rag_status                   TOOL: arguments and result
  agent
    ChatOpenAI                       LLM: final answer
```

Exact span names depend on library versions. Use the trace waterfall to inspect
latency, tool inputs/outputs, model token usage when reported, and failures.
LangGraph passes the configured `thread_id` as metadata; current OpenInference
versions also use it as the Phoenix session ID, grouping turns in `phoenix-demo`.
Tool choice is model-driven: if the tool is skipped, explicitly ask again.

Try these additional cases:

- **Web search:** ask the agent to use `web_search` to find recent LangGraph
  documentation (`SERPER_API_KEY` required).
- **RAG:** ingest documents using the existing full app, then ask a question
  that requires `web_rag`. Expand retriever spans to inspect retrieved documents.

This HTTP demo uses `AGENT_MODE=react`. The existing `enforced_rag` graph expects
`user_id` in its graph input, but the HTTP adapter only passes messages; that
separate integration limitation is not changed by this monitoring example.

Only operations emitting LangChain callbacks appear as nested spans. This is
not automatic tracing of every FAISS call, background ingestion job, HTTP route,
or internal Python function. Tool errors returned as ordinary text appear as
tool output, not necessarily an OpenTelemetry error status.

## Privacy and operation

Traces can contain prompts, history, tool arguments, retrieved documents, and
model outputs. Use synthetic data. To suppress input/output payloads, set
`OPENINFERENCE_HIDE_INPUTS=true` and `OPENINFERENCE_HIDE_OUTPUTS=true` **before**
starting the backend; review the remaining metadata before tracing sensitive
workloads. This does not replace application authentication or authorization.

Batch export keeps collector I/O off the request path. If Phoenix is unavailable,
the exporter logs failures; chat is not intentionally blocked on the collector.
The launcher flushes and shuts down the provider on normal server exit.

If no traces appear, check the project name, wait for the stream to finish,
confirm Phoenix is reachable, and check backend logs for exporter errors. The
OTLP HTTP endpoint must include `/v1/traces`. Restart after changing settings.

`Failed to export spans batch code: 401, reason: Unauthorized` means the exporter
is missing a valid `PHOENIX_API_KEY`. Create a system key in Phoenix Settings,
export it in the shell running the backend (or add it to the untracked `.env`
when using `--env-file`), and restart the backend. Send a new message afterward;
previously rejected spans are not replayed. A successful `force_flush()` alone
does not prove Phoenix accepted the spans; check exporter errors as well.

Stop Phoenix without deleting its data:

```bash
docker compose -f application/backend/full/examples/phoenix_monitoring/compose.yml down
```

From `application/backend/full`, run the credential-free instrumentation tests:

```bash
uv run --extra phoenix --with pytest pytest tests/test_phoenix_monitoring.py -q
```

With Docker available, also run the authenticated ingestion test. It starts and
removes an isolated collector without mounting your existing Phoenix volume,
creates a temporary system API key, exports a synthetic full-agent run, and
checks that Phoenix persisted its spans. No model credentials are needed.

```bash
PHOENIX_DOCKER_TEST=1 uv run --locked --extra phoenix --with pytest pytest tests/test_phoenix_ingestion.py -q
```
