# Migrate To The Packaged App

`agent_chat_minimal` is the canonical non-RAG application. Use `create_app(...)`
for embedded graphs or `create_default_app()` / `minimal-chat-serve` for the
supported packaged server.

One static UI is served at `/`; select `UI_PRESET=minimal` or `UI_PRESET=full`.
`/full/` is no longer supported. For durable sessions configure
`PERSISTENCE_ENABLED=true` with separate `DATABASE_PATH` and
`CHECKPOINT_DATABASE_PATH` values.

Current demo launch modes all target the package. RAG/search are optional
toolsets independent of the layout; see [Toolsets](toolsets.md). The old
`application/backend/full` server is retained for legacy examples, and its
tool imports forward to the shared optional implementations.
`/full/` was removed in 0.4.0. `FULL_WEB_DIR` is a compatibility override
scheduled for removal in the next major release.
