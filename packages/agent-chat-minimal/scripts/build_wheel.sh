#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
package="$repo_root/packages/agent-chat-minimal"
"$package/scripts/stage_ui.sh"

(
  cd "$package"
  rm -rf dist
  uv build
)
