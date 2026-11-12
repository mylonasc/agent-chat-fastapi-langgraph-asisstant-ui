# Runtime UI Configuration

Static `NEXT_PUBLIC_*` values are baked in at build time. The packaged
application additionally serves a versioned runtime contract at
`GET /api/config` so one static build adapts to its deployment without
rebuilding.

## Schema (v1)

```json
{
  "version": 1,
  "api_base": "",
  "ui_preset": "minimal",
  "identity_mode": "anonymous",
  "server_mode": "prod",
  "features": {"agents": true, "assistant": true, "threads": true, "transcripts": true},
  "tools": {
    "web_rag": {"enabled": false, "status_path": "/tools/web_rag/status"},
    "admin": {"enabled": false, "status_path": null},
    "sharing": {"enabled": false, "status_path": null},
    "attachments": {"enabled": false, "status_path": null}
  }
}
```

- `api_base`: `""` means same-origin (the secure default). An absolute
  `http(s)` URL supports split-port development (`API_BASE` env). A same-origin
  `/prefix/path` is also supported. With `API_BASE` empty, the server advertises
  `BASE_PATH` here (empty for origin-root deployment).
- `ui_preset`: the deployment preset (`UI_PRESET` env).
- `identity_mode`: `anonymous` (default header subject) or `delegated`
  (a custom `principal_resolver` owns identity; set `IDENTITY_MODE`
  accordingly).
- `server_mode`: `prod` (thread failures render a generic message) or
  `debug` (the thread surfaces the backend error code, message, and hint).
  Set `SERVER_MODE` / `server_mode:`; nothing else reads it yet.
- `features`: baseline capabilities backed by the composition root.
- `tools`: optional tool UIs. `enabled: false` means the backend does not
  serve them — discoverable before a widget mounts or polls.

The packaged UI discovers the manifest at `${BASE_PATH}/api/config`, using the
same relocated build marker as its Next.js assets. The API destination in the
manifest cannot change chunk paths or the config-discovery path. Configure
`BASE_PATH` on the server rather than attempting to fix UI mounting with
`API_BASE` or ASGI `root_path` alone.

## Caching

The endpoint is computed per request and served with
`Cache-Control: no-store`: deployment values stay changeable after the wheel
is built, and a stale config can never pin a UI to the wrong backend.

## Consumers

- Python: `build_runtime_config(settings, provider)` builds the snapshot;
  `parse_runtime_config(payload)` validates untrusted data with
  backward-compatible defaults (unknown versions, missing or mistyped fields
  degrade to compiled defaults instead of raising).
- TypeScript: `lib/runtime-config.ts` in both frontends mirrors the schema,
  `parseRuntimeConfig`, `fetchRuntimeConfig` (defaults on unavailable or
  malformed responses), and `resolveApiBase` precedence (runtime config,
  then build-time env, then localhost).

## Packaged UI behavior

The unified packaged UI loads this manifest before selecting the minimal or
full preset. Its runtime hook supplies the effective API base and presentation
settings to the chat components. Build-time `NEXT_PUBLIC_*` values remain
fallbacks for split-port development; changing those variables on an installed
server does not recompile its UI.

Optional tools are described by the capability manifest, but availability does
not imply that every UI surface is capability-gated. The packaged backend does
not implement RAG/admin tool APIs and explicitly returns `501` for unsupported
`/tools/*` calls. See [configuration.md](configuration.md#url-prefix-deployment)
for deployment-prefix configuration and limitations.
