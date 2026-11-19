#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "OPENAI_API_KEY must be set for the OpenAI persistence E2E stack." >&2
  exit 2
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${script_dir}/../../.." && pwd)"
state_dir="$(mktemp -d /tmp/opencode/agent-chat-openai-e2e.XXXXXX)"
server_pid=""

cleanup() {
  if [[ -n "${server_pid}" ]] && kill -0 "${server_pid}" 2>/dev/null; then
    kill "${server_pid}" 2>/dev/null || true
    wait "${server_pid}" 2>/dev/null || true
  fi
  rm -rf -- "${state_dir}"
}
trap cleanup EXIT INT TERM

export MODEL="${OPENAI_E2E_MODEL:-openai:gpt-4o-mini}"
export DATABASE_PATH="${state_dir}/app.db"
export CHECKPOINT_DATABASE_PATH="${state_dir}/checkpoints.db"
export PERSISTENCE_ENABLED=true

uv run \
  --python "${UV_PYTHON:-3.11}" \
  --project "${repo_root}/packages/agent-chat-minimal" \
  --extra persistence \
  python "${script_dir}/openai-persistence-server.py" &
server_pid=$!

ready=false
for _ in $(seq 1 90); do
  if curl --fail --silent http://127.0.0.1:8011/health >/dev/null; then
    ready=true
    break
  fi
  if ! kill -0 "${server_pid}" 2>/dev/null; then
    wait "${server_pid}"
  fi
  sleep 1
done

if [[ "${ready}" != true ]]; then
  echo "OpenAI persistence E2E server did not become ready." >&2
  exit 1
fi

PERSISTENCE_E2E=1 \
  FULL_UI_URL=http://localhost:8011 \
  FULL_API_URL=http://localhost:8011 \
  pnpm exec playwright test \
    --project=full-desktop \
    specs/persistence-e2e.spec.ts
