#!/bin/bash
cd "$(dirname "$0")"
uv run uvicorn server:app --port 8011 --reload
