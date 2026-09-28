#!/usr/bin/env bash
# Build both frontend static exports and stage them as package data so the
# library serves the UI from a source checkout (API-only mode otherwise).
# Staged output is gitignored; `build_wheel.sh` runs this implicitly.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
frontend_minimal="$repo_root/application/frontend/frontend-minimal"
frontend_full="$repo_root/application/frontend/frontend-full"
package="$repo_root/packages/agent-chat-minimal"
web="$package/src/agent_chat_minimal/web"
web_full="$package/src/agent_chat_minimal/web_full"

pnpm --dir "$frontend_minimal" install --frozen-lockfile
pnpm --dir "$frontend_minimal" build
rm -rf "$web"
cp -R "$frontend_minimal/out" "$web"
test -f "$web/index.html"

# Full UI (thread sidebar) is namespaced under /full and talks same-origin.
pnpm --dir "$frontend_full" install --frozen-lockfile
NEXT_PUBLIC_API_BASE="" FULL_UI_BASE_PATH=/full pnpm --dir "$frontend_full" build
rm -rf "$web_full"
cp -R "$frontend_full/out" "$web_full"
test -f "$web_full/index.html"

# Restore tracked placeholders (staging wipes them; output itself is ignored).
git -C "$repo_root" checkout -- \
  packages/agent-chat-minimal/src/agent_chat_minimal/web/.gitkeep \
  packages/agent-chat-minimal/src/agent_chat_minimal/web_full/.gitkeep

echo "staged: $web $web_full"
