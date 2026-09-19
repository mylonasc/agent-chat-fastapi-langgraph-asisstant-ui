#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
frontend="$repo_root/application/frontend/frontend-minimal"
package="$repo_root/packages/agent-chat-minimal"
web="$package/src/agent_chat_minimal/web"

cleanup() {
  rm -rf "$web"
  mkdir -p "$web"
  : > "$web/.gitkeep"
}
trap cleanup EXIT

pnpm --dir "$frontend" install --frozen-lockfile
pnpm --dir "$frontend" build
rm -rf "$web"
cp -R "$frontend/out" "$web"

(
  cd "$package"
  uv build --wheel
)
