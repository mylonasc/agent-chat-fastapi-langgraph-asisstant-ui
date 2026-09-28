#!/usr/bin/env bash
# Build the unified frontend static export and stage it as package data so
# the library serves the UI from a source checkout (API-only mode
# otherwise). The preset (minimal/full) is selected at runtime via
# GET /api/config. Staged output is gitignored; `build_wheel.sh` runs this
# implicitly.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
frontend="$repo_root/application/frontend/frontend"
package="$repo_root/packages/agent-chat-minimal"
web="$package/src/agent_chat_minimal/web"

pnpm --dir "$frontend" install --frozen-lockfile
NEXT_PUBLIC_API_BASE="" pnpm --dir "$frontend" build
rm -rf "$web"
cp -R "$frontend/out" "$web"
test -f "$web/index.html"

# Restore tracked placeholders (staging wipes them; output itself is ignored).
git -C "$repo_root" checkout -- \
  packages/agent-chat-minimal/src/agent_chat_minimal/web/.gitkeep

echo "staged: $web"
