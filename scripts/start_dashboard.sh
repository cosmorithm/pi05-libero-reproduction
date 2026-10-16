#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT=/root/autodl-tmp/pi05-libero-reproduction

cd "$PROJECT_ROOT"
export MUJOCO_GL=egl
export LIBERO_CONFIG_PATH="$PROJECT_ROOT/home/.libero"
export HF_HOME="$PROJECT_ROOT/cache/huggingface"
export HF_ENDPOINT=https://hf-mirror.com
export HF_HUB_DISABLE_XET=1

exec "$PROJECT_ROOT/.venv/bin/python" "$PROJECT_ROOT/scripts/libero_dashboard.py" --host 0.0.0.0 --port 6006
