#!/usr/bin/env bash
set -euo pipefail

package="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
artifact="${1:?usage: smoke_test_wheel.sh <wheel-or-sdist>}"
case "$artifact" in
  *.whl|*.tar.gz) ;;
  *) echo "unsupported artifact: $artifact" >&2; exit 2 ;;
esac
venv_root="$(mktemp -d)"
venv="$venv_root/venv"
curl_bin="$(command -v curl)"
port="${PORT:-18011}"
server_pid=""

cleanup() {
  if [[ -n "$server_pid" ]]; then
    kill "$server_pid" 2>/dev/null || true
  fi
  /bin/rm -rf "$venv_root"
}
trap cleanup EXIT

python3 -m venv "$venv"
"$venv/bin/pip" install "$artifact"

export PATH="$venv/bin"
if command -v node >/dev/null; then
  echo "node unexpectedly available in verification PATH" >&2
  exit 1
fi
echo "no node - good"

unset OPENAI_API_KEY
minimal-chat-serve --host 127.0.0.1 --port "$port" &
server_pid=$!
for _ in {1..30}; do
  if "$curl_bin" -sf "http://127.0.0.1:$port/health" >/dev/null; then
    break
  fi
  /bin/sleep 1
done

"$curl_bin" -sf "http://127.0.0.1:$port/health"
"$curl_bin" -sf "http://127.0.0.1:$port/" | /bin/grep -qi "<html"
"$curl_bin" -sf "http://127.0.0.1:$port/api/config" | /bin/grep -Eq '"version"[[:space:]]*:[[:space:]]*1'
test "$("$curl_bin" -s -o /dev/null -w '%{http_code}' \
  "http://127.0.0.1:$port/full/")" = "404"
test "$("$curl_bin" -s -o /dev/null -w '%{http_code}' \
  -X POST "http://127.0.0.1:$port/assistant" \
  -H 'content-type: application/json' \
  -d '{"state":{"messages":[]},"commands":[]}')" = "503"
echo "artifact smoke test passed: ${artifact##*/}"
