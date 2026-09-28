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
  `http(s)` URL supports split-port development (`API_BASE` env).
- `ui_preset`: the deployment preset (`UI_PRESET` env).
- `identity_mode`: `anonymous` (default header subject) or `delegated`
  (a custom `principal_resolver` owns identity; set `IDENTITY_MODE`
  accordingly).
- `features`: baseline capabilities backed by the composition root.
- `tools`: optional tool UIs. `enabled: false` means the backend does not
  serve them — discoverable before a widget mounts or polls.

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

## Not yet wired

Components still read build-time `NEXT_PUBLIC_*` values; preset switching
and visual capability gating arrive with PUIR-09/PUIR-13. The manifest makes
unsupported features discoverable now (e.g. `tools.web_rag.enabled` is
`false` on the packaged app, matching its explicit `501` refusal).
