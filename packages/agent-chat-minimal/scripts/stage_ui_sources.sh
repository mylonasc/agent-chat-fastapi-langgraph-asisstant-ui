#!/usr/bin/env bash
# Stage the unified frontend *sources* as sdist payload so the published
# source distribution is an editable-UI version, not built HTML/JS/CSS only.
# This mirrors stage_ui.sh (which stages the compiled static export served at
# runtime) but copies TypeScript/Next.js sources instead of building them.
# Staged output is gitignored; `build_wheel.sh` runs this implicitly before
# `uv build` so the sdist always carries sources matching the built bundle.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
frontend="$repo_root/application/frontend/frontend"
package="$repo_root/packages/agent-chat-minimal"
dest="$package/src/agent_chat_minimal/ui_src/frontend"

rm -rf "$package/src/agent_chat_minimal/ui_src"
mkdir -p "$dest"
# Copy everything except install/build outputs; the consumer runs
# `pnpm install --frozen-lockfile && pnpm build` on their own machine.
cp -R "$frontend/." "$dest/"
rm -rf \
  "$dest/node_modules" \
  "$dest/.next" \
  "$dest/out" \
  "$dest/test-results" \
  "$dest/tsconfig.tsbuildinfo"
test -f "$dest/package.json"
test -f "$dest/app/page.tsx"

# Restore tracked placeholders (staging wipes them; output itself is ignored).
git -C "$repo_root" checkout -- \
  packages/agent-chat-minimal/src/agent_chat_minimal/ui_src/.gitkeep

echo "staged: $dest"
