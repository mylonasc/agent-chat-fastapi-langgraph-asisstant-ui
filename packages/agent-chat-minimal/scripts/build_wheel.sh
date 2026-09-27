#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
frontend_minimal="$repo_root/application/frontend/frontend-minimal"
frontend_full="$repo_root/application/frontend/frontend-full"
package="$repo_root/packages/agent-chat-minimal"
web="$package/src/agent_chat_minimal/web"
web_full="$package/src/agent_chat_minimal/web_full"

cleanup() {
  rm -rf "$web" "$web_full"
  mkdir -p "$web" "$web_full"
  : > "$web/.gitkeep"
  : > "$web_full/.gitkeep"
}
trap cleanup EXIT

pnpm --dir "$frontend_minimal" install --frozen-lockfile
pnpm --dir "$frontend_minimal" build
rm -rf "$web"
cp -R "$frontend_minimal/out" "$web"

# Full UI (thread sidebar) is namespaced under /full and talks same-origin.
pnpm --dir "$frontend_full" install --frozen-lockfile
NEXT_PUBLIC_API_BASE="" FULL_UI_BASE_PATH=/full pnpm --dir "$frontend_full" build
rm -rf "$web_full"
cp -R "$frontend_full/out" "$web_full"

(
  cd "$package"
  uv build --wheel
)
