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
starter_port="${STARTER_PORT:-18012}"
starter_dir="$venv_root/smoke-agent"
server_pid=""
starter_pid=""

cleanup() {
  if [[ -n "$server_pid" ]]; then
    kill "$server_pid" 2>/dev/null || true
  fi
  if [[ -n "$starter_pid" ]]; then
    kill "$starter_pid" 2>/dev/null || true
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

# AGS: the installed wheel generates, installs, tests, and serves a starter
# with Python only on PATH (no node) - mirroring a user outside the checkout.
"$venv/bin/python" -c \
  "from agent_chat_minimal.setup import get_config_schema, describe_setup;" \
  "assert get_config_schema()['title'] == 'Agent Chat configuration';" \
  "assert {p['name'] for p in describe_setup()['providers']} >= {'openai','ollama','litellm'}"
"$venv/bin/minimal-chat-init" "$starter_dir" --project-name smoke-agent --provider openai
test -f "$starter_dir/starter-manifest.json"
test -f "$starter_dir/src/smoke_agent/server.py"
test -f "$starter_dir/src/smoke_agent/agents/helper.py"
test -f "$starter_dir/agent_chat.yaml"
"$venv/bin/python" -c \
  "import json;" \
  "m = json.load(open('$starter_dir/starter-manifest.json'));" \
  "assert m['project_name'] == 'smoke-agent', m;" \
  "assert 'src/smoke_agent/server.py' in m['expected_files'], m"
"$venv/bin/pip" install "$starter_dir"
"$venv/bin/pip" install pytest httpx
(cd "$starter_dir" && "$venv/bin/pytest" -q)
(cd "$starter_dir" && "$venv/bin/smoke-agent-serve" --host 127.0.0.1 --port "$starter_port" &)
starter_pid=$!
for _ in {1..30}; do
  if "$curl_bin" -sf "http://127.0.0.1:$starter_port/health" >/dev/null; then
    break
  fi
  /bin/sleep 1
done
"$curl_bin" -sf "http://127.0.0.1:$starter_port/health"
"$curl_bin" -sf "http://127.0.0.1:$starter_port/agents" | /bin/grep -Eq '"helper"'
"$curl_bin" -sf "http://127.0.0.1:$starter_port/" | /bin/grep -qi "<html"
"$curl_bin" -sf "http://127.0.0.1:$starter_port/api/config" | /bin/grep -Eq '"questions"'
test "$("$curl_bin" -s -o /dev/null -w '%{http_code}' \
  -X POST "http://127.0.0.1:$starter_port/assistant" \
  -H 'content-type: application/json' \
  -d '{"state":{"messages":[]},"commands":[]}')" = "503"
echo "artifact smoke test passed: ${artifact##*/}"
