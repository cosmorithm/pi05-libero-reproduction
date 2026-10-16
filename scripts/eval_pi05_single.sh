#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODEL_PATH="${MODEL_PATH:-$ROOT_DIR/checkpoints/lerobot-pi05-libero-finetuned}"
SUITE="${SUITE:-libero_spatial}"
TASK_ID="${TASK_ID:-0}"
SEED="${SEED:-7}"
N_EPISODES="${N_EPISODES:-1}"
RUN_NAME="${RUN_NAME:-pi05-${SUITE}-task${TASK_ID}-seed${SEED}}"
OUTPUT_DIR="${OUTPUT_DIR:-$ROOT_DIR/outputs/eval/$RUN_NAME}"

export LIBERO_CONFIG_PATH="${LIBERO_CONFIG_PATH:-$ROOT_DIR/home/.libero}"
export HF_HOME="${HF_HOME:-$ROOT_DIR/cache/huggingface}"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
export HF_HUB_DISABLE_XET="${HF_HUB_DISABLE_XET:-1}"
export MUJOCO_GL="${MUJOCO_GL:-egl}"

if [[ ! -x "$ROOT_DIR/.venv/bin/lerobot-eval" ]]; then
  echo "error: LeRobot environment is missing: $ROOT_DIR/.venv" >&2
  exit 2
fi

if [[ ! -f "$MODEL_PATH/model.safetensors" ]]; then
  echo "error: checkpoint is incomplete: $MODEL_PATH/model.safetensors" >&2
  echo "check logs/pi05-download.log or resume the server-side mirror download" >&2
  exit 2
fi

model_bytes="$(stat -c %s "$MODEL_PATH/model.safetensors")"
if (( model_bytes < 7000000000 )); then
  echo "error: checkpoint weight file is too small ($model_bytes bytes); download is incomplete" >&2
  exit 2
fi

if ! HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$ROOT_DIR/.venv/bin/python" - <<'PY' >/dev/null 2>&1
from transformers import AutoTokenizer

AutoTokenizer.from_pretrained("google/paligemma-3b-pt-224", local_files_only=True)
PY
then
  if ! "$ROOT_DIR/.venv/bin/hf" auth whoami >/dev/null 2>&1; then
    echo "error: the PaliGemma tokenizer is not cached and Hugging Face is not logged in" >&2
    echo "accept https://huggingface.co/google/paligemma-3b-pt-224 and run:" >&2
    echo "  HF_HOME=$HF_HOME $ROOT_DIR/.venv/bin/hf auth login" >&2
    exit 3
  fi
fi

mkdir -p "$OUTPUT_DIR" "$ROOT_DIR/logs"

echo "model=$MODEL_PATH"
echo "suite=$SUITE task_id=$TASK_ID seed=$SEED episodes=$N_EPISODES"
echo "output=$OUTPUT_DIR"

set -o pipefail
"$ROOT_DIR/.venv/bin/lerobot-eval" \
  --output_dir="$OUTPUT_DIR" \
  --env.type=libero \
  --env.task="$SUITE" \
  --env.task_ids="[$TASK_ID]" \
  --env.observation_height=256 \
  --env.observation_width=256 \
  --env.max_parallel_tasks=1 \
  --env.control_mode=relative \
  --eval.batch_size=1 \
  --eval.n_episodes="$N_EPISODES" \
  --policy.path="$MODEL_PATH" \
  --policy.n_action_steps=10 \
  --policy.compile_model=false \
  --seed="$SEED" \
  2>&1 | tee "$OUTPUT_DIR/run.log"
