#!/usr/bin/env bash
set -e

echo "========================================"
echo "  STARTING FULL AGENT (CPU MODE)"
echo "========================================"

# Ensure we are in the correct directory
if [ ! -f "pyproject.toml" ]; then
    echo "ERROR: Run this script from application/backend/full/"
    exit 1
fi

# Create virtual environment if missing
if [ ! -d ".venv" ]; then
    echo "[CPU] Creating virtual environment..."
    uv venv
    source .venv/bin/activate
    echo "[CPU] Installing CPU-only dependencies..."
    uv pip install .
else
    source .venv/bin/activate
fi

# Ensure CPU-safe environment
unset ENABLE_SENTENCE_TRANSFORMERS
unset CUDA_VISIBLE_DEVICES
export AGENT_MODE=react
export PORT=${PORT:-8000}

echo "Embedding Provider: fastembed (default)"
echo "Agent Mode: $AGENT_MODE"
echo "Port: $PORT"
echo "========================================"

uvicorn fastlang.server.server:app \
    --reload \
    --host 0.0.0.0 \
    --port $PORT
