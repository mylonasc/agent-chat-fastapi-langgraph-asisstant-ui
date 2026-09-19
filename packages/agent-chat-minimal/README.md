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

Run the offline serving tests and clean-venv smoke check from the repository
root:

```bash
python3 -m venv /tmp/agent-chat-minimal-tests
/tmp/agent-chat-minimal-tests/bin/pip install \
  "packages/agent-chat-minimal[test]"
/tmp/agent-chat-minimal-tests/bin/pytest packages/agent-chat-minimal
packages/agent-chat-minimal/scripts/smoke_test_wheel.sh
```

Build the Python-only runtime image after building the wheel:

```bash
docker build -t agent-chat-minimal packages/agent-chat-minimal
docker run --rm -p 8011:8011 agent-chat-minimal
```
