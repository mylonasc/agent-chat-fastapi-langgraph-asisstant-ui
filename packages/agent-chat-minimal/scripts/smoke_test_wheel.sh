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

stop_server() {
  local pid="$1"
  if [[ -z "$pid" ]]; then
    return 0
  fi
  if ! kill -0 "$pid" 2>/dev/null; then
    wait "$pid" 2>/dev/null || true
    return 0
  fi
  # TERM the real server process, then wait for it to exit before the venv
  # is removed: deleting site-packages under a still-starting interpreter
  # produces bogus mid-import ModuleNotFoundErrors.
  kill "$pid" 2>/dev/null || true
  for _ in {1..15}; do
    kill -0 "$pid" 2>/dev/null || break
    /bin/sleep 1
  done
  if kill -0 "$pid" 2>/dev/null; then
    kill -9 "$pid" 2>/dev/null || true
  fi
  wait "$pid" 2>/dev/null || true
  return 0
}

cleanup() {
  stop_server "$server_pid"
  stop_server "$starter_pid"
  wait 2>/dev/null || true
  /bin/rm -rf "$venv_root"
}
trap cleanup EXIT

require_free_port() {
  local what="$1" check_port="$2"
  if "$curl_bin" -sf --max-time 2 "http://127.0.0.1:$check_port/health" >/dev/null 2>&1; then
    echo "stale server still answering on port $check_port before starting $what" >&2
    echo "a previous smoke run likely leaked its server; aborting instead of testing the wrong process" >&2
    exit 1
  fi
}

python3 -m venv "$venv"
"$venv/bin/pip" install "$artifact"

export PATH="$venv/bin"
if command -v node >/dev/null; then
  echo "node unexpectedly available in verification PATH" >&2
  exit 1
fi
echo "no node - good"

unset OPENAI_API_KEY
require_free_port "package server" "$port"
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
require_free_port "starter server" "$starter_port"
# Background directly (no cd-subshell): $! must be the real server PID.
# A `(cd ... && server &)` subshell leaves $! pointing at an already-exited
# shell, so cleanup kills nothing, leaks the server, and the next artifact
# run ends up testing the stale process instead of its own.
pushd "$starter_dir" >/dev/null
"$venv/bin/smoke-agent-serve" --host 127.0.0.1 --port "$starter_port" &
starter_pid=$!
popd >/dev/null
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
