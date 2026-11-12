# Serve The Packaged App

`agent-chat-fastapi-langgraph-assistant-ui` is the canonical portable non-RAG
application. It serves FastAPI, the Assistant UI static export, and agents from
one process and one origin. The default port is 8011.

## Install And Run

The published distribution needs Python 3.11+; Node and pnpm are not runtime
dependencies.

```bash
python -m pip install agent-chat-fastapi-langgraph-assistant-ui
export OPENAI_API_KEY=sk-...
minimal-chat-serve --port 8011
```

Visit <http://localhost:8011/>. Useful endpoints are `GET /health`, `GET
/agents`, `POST /assistant`, `POST /assistant/{agent_id}`, and `GET /docs`.
Without a credential, the UI and health endpoint still load; an agent request
returns a structured `503 agent_not_ready` response.

The default model is `openai:gpt-4o-mini` and the default agent is `weather`.
Change either at launch:

```bash
minimal-chat-serve --model anthropic:claude-sonnet-4-5 --agent calculator
minimal-chat-serve --agent weather --check
```

`--check` constructs the selected default agent and exits. Install the matching
provider extra when needed, for example
`python -m pip install "agent-chat-fastapi-langgraph-assistant-ui[ollama]"`.
See the package's [provider guide](../packages/agent-chat-minimal/src/agent_chat_minimal/docs/providers.md)
for supported model specifications and credentials.

## Reverse-proxy URL prefixes

> This support requires an artifact built from the prefix fix. Published
> 0.6.2/0.7.1 wheels do not support it. Until a release containing the fix is
> available, follow [Build From This Repository](#build-from-this-repository)
> below and install that wheel; setting `BASE_PATH` on an old wheel is not enough.

Select a public prefix at runtime; no frontend rebuild or proxy response-body
rewriting is needed for newly built package artifacts:

```bash
BASE_PATH=/platform/apps/chat minimal-chat-serve --port 8011
# Equivalent: minimal-chat-serve --base-path /platform/apps/chat
```

The YAML setting is `base_path: /platform/apps/chat`; Python callers use
`Settings(base_path="/platform/apps/chat")`. Use `""` (the default) for `/`.
Prefixes must start with `/`, have no trailing slash, and contain only URL-safe
ASCII letters, digits, `-`, `_`, `.`, and `~` in nonempty segments. Dot segments,
URL escapes, and the reserved `__agent_chat_base_path__` segment are rejected.

Publish `/platform/apps/chat/` through the proxy. Both stripping the prefix
before forwarding and forwarding the complete public path are supported. Have
the proxy redirect the bare `/platform/apps/chat` to `/platform/apps/chat/`.
For example, either nginx form works (the `proxy_pass` trailing slash determines
whether nginx strips the location prefix):

```nginx
location = /platform/apps/chat {
    return 307 /platform/apps/chat/;
}
location /platform/apps/chat/ {
    proxy_pass http://127.0.0.1:8011/; # omit final / to preserve the prefix
    proxy_set_header Host $http_host;
    proxy_buffering off;
}
```

`BASE_PATH` configures the app's ASGI `root_path` and normalizes stripped paths
before routing, so generated redirects retain the public prefix. Use the same
setting with the ASGI factory; do not add a second independent prefix through
Uvicorn `--root-path` or mount the app under a different path. `root_path` alone
or `X-Forwarded-Prefix` does not relocate the UI. Configure trusted forwarded
headers separately when TLS terminates at the proxy. Prefix configuration is
not access control: restrict direct upstream access at the proxy/network layer.

With `API_BASE` empty, the runtime manifest advertises `BASE_PATH` as the
same-origin API base. An explicit `API_BASE=/other/api` or absolute HTTP(S) URL
overrides that API destination without changing UI asset/config-discovery paths.

Package staging compiles a reserved Next.js `basePath` marker. At startup the
server copies the export into a per-app temporary directory and replaces that
marker throughout HTML, Flight payloads, CSS, and compiled JS. Installed package
files remain untouched; Node is not needed at runtime. Writable temporary
storage is required, and changing the prefix requires restarting the app.
Custom `MINIMAL_WEB_DIR`/`FULL_WEB_DIR` exports without the marker are served
unchanged and must already be built for their public path (the server warns).
Old 0.6.2/0.7.1 wheels do not contain this marker and are not repaired merely by
setting a prefix; install an artifact built with this fix.

### Verify the deployment

For a proxy exposed at `https://chat.example.com`, open
**`https://chat.example.com/platform/apps/chat/`** (including the final `/`).

1. Check the public health and config endpoints:

   ```bash
   curl --fail https://chat.example.com/platform/apps/chat/health
   curl --fail https://chat.example.com/platform/apps/chat/api/config
   ```

   Health should return `{"status":"ok"}`. With `API_BASE` unset or empty,
   config should contain `"api_base":"/platform/apps/chat"`.
2. In the browser's Network panel, reload the page. JS, CSS, and fonts must load
   beneath `/platform/apps/chat/_next/`, and config must load from
   `/platform/apps/chat/api/config`. There should be no requests to origin-root
   `/_next/` or `/api/config` and no URLs containing `__agent_chat_base_path__`.
3. With a configured model credential, send a message and check that a streamed
   reply appears. A visible page or HTTP 200 alone does not prove hydration.
4. Refresh the page. If using the full preset, check that thread history still
   loads. Opening `/platform/apps/chat/admin` should redirect to the same path
   with a final `/`; its “Back to chat” link should stay beneath the prefix.

If assets escape to `/_next/`, confirm that you installed a newly built artifact
and are not overriding it with a root-built `MINIMAL_WEB_DIR`. If config or API
requests escape the prefix, check `BASE_PATH`, stale `API_BASE` values, and the
proxy's forwarding rules. Restart the server after changing `BASE_PATH` and
reload the browser. Do not use HTML-only URL rewriting as a workaround.

## Build From This Repository

Use this when changing the unified frontend or packaging code. The build stages
`application/frontend/frontend/out` into the Python package and creates a
wheel. It requires `uv`, Node, pnpm, and the frontend's locked dependencies.

```bash
packages/agent-chat-minimal/scripts/build_wheel.sh
python -m venv .venv-agent-chat
.venv-agent-chat/bin/pip install packages/agent-chat-minimal/dist/*.whl
OPENAI_API_KEY=sk-... .venv-agent-chat/bin/minimal-chat-serve --port 8011
```

For a prefixed deployment, use the installed wheel's executable:

```bash
BASE_PATH=/platform/apps/chat API_BASE= UI_PRESET=full \
  .venv-agent-chat/bin/minimal-chat-serve --port 8011
```

The wheel and sdist are written to `packages/agent-chat-minimal/dist/`. These
are generated build outputs, not files committed to Git. Prefer a fresh virtual
environment: a local build may carry the same version as an older installed
release, and a plain `pip install` can otherwise leave that release in place.
Node/pnpm are needed only on the build machine, not on the deployment host.

For an editable source installation, stage the UI first. Otherwise the source
server intentionally starts API-only:

```bash
packages/agent-chat-minimal/scripts/stage_ui.sh
python -m pip install -e "packages/agent-chat-minimal[persistence]"
minimal-chat-serve --port 8011
```

### Maintainer release checklist

1. Merge the fix and require the artifact CI checks to pass, including installed
   wheel/sdist prefix browser tests.
2. Choose an unused version newer than the current PyPI release and update
   `__version__` in
   `packages/agent-chat-minimal/src/agent_chat_minimal/__init__.py`. A local
   artifact retaining an already-published version is for testing, not re-upload.
3. Publish a GitHub Release from the release commit, tagged
   `agent-chat-fastapi-langgraph-assistant-ui-vX.Y.Z`, matching that version.
   `.github/workflows/publish-workflow.yml` rebuilds, tests, and publishes to
   PyPI through Trusted Publishing. Pushing a feature branch does **not** publish.
4. Install the released version into a fresh environment and repeat the public
   prefix verification above. Update the availability note in this guide with
   the first release containing the fix.

## Configuration And Persistence

The primary settings are `MODEL`, `DEFAULT_AGENT`, `UI_PRESET`, `HOST`, and
`PORT`. `UI_PRESET=minimal` is the default; `UI_PRESET=full` enables the
thread-oriented layout from the same bundled UI. `MINIMAL_WEB_DIR` overrides
the bundled static directory for local frontend testing.

The server is in-memory by default. Enable the supported durable SQLite
composition by installing the persistence extra and setting paths or URLs:

```bash
python -m pip install "agent-chat-fastapi-langgraph-assistant-ui[persistence]"
PERSISTENCE_ENABLED=true UI_PRESET=full \
DATABASE_PATH=./agent-chat.db \
CHECKPOINT_DATABASE_PATH=./agent-chat-checkpoints.db \
minimal-chat-serve --port 8011
```

Use separate application and LangGraph checkpoint databases. Full configuration,
ASGI factory use, and persistence lifecycle details are in the
[package configuration guide](../packages/agent-chat-minimal/src/agent_chat_minimal/docs/configuration.md).

## Configuration File And Starter Projects

Beyond environment variables, the server loads a versioned YAML file with
explicit precedence (defaults → YAML → present environment → CLI/API
overrides), including welcome copy, proposed questions, endpoints, and
persistence paths:

```bash
minimal-chat-serve --config ./agent_chat.yaml
AGENT_CHAT_CONFIG=./agent_chat.yaml minimal-chat-serve
```

Generate a user-owned agent project (editable agent, thin server, config,
offline tests) with no network calls at generation time:

```bash
minimal-chat-init ./my-agent --provider ollama --preset full --persistence sqlite
cd my-agent && pip install -e .[test] && pytest
```

Details: [starter guide](../packages/agent-chat-minimal/src/agent_chat_minimal/docs/starter.md),
[setup engine](../packages/agent-chat-minimal/src/agent_chat_minimal/docs/setup.md),
and [provider guide](../packages/agent-chat-minimal/src/agent_chat_minimal/docs/providers.md)
(endpoint/credential setup, LiteLLM direct-vs-proxy semantics, offline-vs-live checks).

## Container Image

Build the wheel first, then build the runtime image. The image installs the
wheel and runs `minimal-chat-serve`; it does not build frontend assets.

```bash
packages/agent-chat-minimal/scripts/build_wheel.sh
docker build -t agent-chat-minimal packages/agent-chat-minimal
docker run --rm -p 8011:8011 -e OPENAI_API_KEY agent-chat-minimal
```

For adding agents, continue with [Implementing agents](implementing-agents.md).
