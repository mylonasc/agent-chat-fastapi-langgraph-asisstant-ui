# Agent Chat Minimal

This local Python distribution bundles the fixed weather/graph demo agent,
FastAPI server, and a prebuilt static minimal chat UI. Node is needed only to
build the web payload, not to install or run the resulting wheel.

From the repository root, build the UI and wheel with:

```bash
packages/agent-chat-minimal/scripts/build_wheel.sh
```

The script runs the frozen pnpm install and static export, stages `out/` as
package data, and writes the wheel under `packages/agent-chat-minimal/dist/`.
Generated `web/` content and `dist/` are intentionally gitignored.

Install and serve the local wheel with:

```bash
python -m pip install packages/agent-chat-minimal/dist/*.whl
minimal-chat-serve --port 8011
```

Open <http://localhost:8011/>. Set `OPENAI_API_KEY` to enable `/assistant`;
without it, the UI and `/health` still work and `/assistant` returns 503.
`MINIMAL_WEB_DIR` may override the bundled web directory.
