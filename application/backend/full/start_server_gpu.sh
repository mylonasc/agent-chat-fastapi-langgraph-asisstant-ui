#!/usr/bin/env bash
set -e

echo "========================================"
echo "  STARTING FULL AGENT (GPU MODE)"
echo "========================================"

# Ensure we are in the correct directory
if [ ! -f "pyproject.toml" ]; then
    echo "ERROR: Run this script from application/backend/full/"
    exit 1
fi

# Ensure CUDA is available
if ! command -v nvidia-smi &> /dev/null; then
    echo "ERROR: CUDA GPU not detected (nvidia-smi not found)."
    exit 1
fi

# Create virtual environment if missing
if [ ! -d ".venv" ]; then
    echo "[GPU] Creating virtual environment..."
    uv venv
    source .venv/bin/activate
    echo "[GPU] Installing GPU-enabled dependencies..."
    uv pip install .[sentence-gpu,gpu]
else
    source .venv/bin/activate
fi

# Required environment for sentence-transformers
export ENABLE_SENTENCE_TRANSFORMERS=1
export TRANSFORMERS_NO_TORCHVISION=1
export AGENT_MODE=enforced_rag
export PORT=${PORT:-8000}

echo "CUDA: detected"
echo "Embedding Provider: sentence_transformers"
echo "Agent Mode: $AGENT_MODE"
echo "Port: $PORT"
echo "========================================"

uvicorn fastlang.server.server:app \
    --host 0.0.0.0 \
    --port $PORT
