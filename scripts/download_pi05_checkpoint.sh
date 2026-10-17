#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT=/root/autodl-tmp/pi05-libero-reproduction
CHECKPOINT_DIR="$PROJECT_ROOT/checkpoints/lerobot-pi05-libero-finetuned"
REPO_ID=lerobot/pi05_libero_finetuned
REVISION=7152f13e34c6c115d808aea0e5d08aca74eac14b
EXPECTED_MODEL_BYTES=7473096344
MODEL_URL="${HF_ENDPOINT:-https://hf-mirror.com}/$REPO_ID/resolve/$REVISION/model.safetensors"

export HF_HOME="$PROJECT_ROOT/cache/huggingface"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
export HF_HUB_DISABLE_XET=1
export HF_HUB_DOWNLOAD_TIMEOUT=600
export HF_HUB_ETAG_TIMEOUT=60

mkdir -p "$CHECKPOINT_DIR" "$PROJECT_ROOT/logs"

# Download the small repository files with huggingface_hub. The large model is
# intentionally excluded because a single mirror connection can stall at
# 10 MiB boundaries on SeetaCloud.
rc=1
for attempt in $(seq 1 10); do
  echo "Checkpoint metadata download attempt $attempt/10"
  if "$PROJECT_ROOT/.venv/bin/hf" download "$REPO_ID" \
      --revision "$REVISION" \
      --exclude model.safetensors \
      --local-dir "$CHECKPOINT_DIR"; then
    rc=0
    break
  else
    rc=$?
  fi
  delay=$((attempt * 30))
  if (( delay > 180 )); then
    delay=180
  fi
  echo "Checkpoint metadata download failed with exit code $rc; retrying in ${delay}s"
  sleep "$delay"
done

if (( rc != 0 )); then
  echo "Checkpoint metadata did not complete after 10 attempts" >&2
  exit "$rc"
fi

model="$CHECKPOINT_DIR/model.safetensors"
part="$CHECKPOINT_DIR/model.safetensors.part"
if [[ ! -f "$model" ]] || [[ "$(stat -c '%s' "$model")" != "$EXPECTED_MODEL_BYTES" ]]; then
  if ! command -v aria2c >/dev/null 2>&1; then
    echo "aria2c is required for the large checkpoint download" >&2
    exit 1
  fi

  rc=1
  for attempt in $(seq 1 10); do
    echo "Checkpoint model download attempt $attempt/10"
    if aria2c \
        --continue=true \
        --auto-file-renaming=false \
        --allow-overwrite=true \
        --file-allocation=none \
        --max-connection-per-server=4 \
        --split=4 \
        --min-split-size=10M \
        --connect-timeout=30 \
        --timeout=120 \
        --max-tries=0 \
        --retry-wait=5 \
        --dir "$CHECKPOINT_DIR" \
        --out "$(basename "$part")" \
        "$MODEL_URL"; then
      rc=0
      break
    else
      rc=$?
    fi
    echo "Checkpoint model download failed with exit code $rc; retrying in 30s"
    sleep 30
  done

  if (( rc != 0 )); then
    echo "Checkpoint model did not complete after 10 attempts" >&2
    exit "$rc"
  fi
  mv "$part" "$model"
fi

actual_bytes="$(stat -c '%s' "$model")"
if [[ "$actual_bytes" != "$EXPECTED_MODEL_BYTES" ]]; then
  echo "Unexpected model size: $actual_bytes (expected $EXPECTED_MODEL_BYTES)" >&2
  exit 1
fi

"$PROJECT_ROOT/.venv/bin/python" - <<'PY'
from pathlib import Path
from safetensors import safe_open

model = Path("/root/autodl-tmp/pi05-libero-reproduction/checkpoints/lerobot-pi05-libero-finetuned/model.safetensors")
with safe_open(model, framework="pt", device="cpu") as tensors:
    keys = list(tensors.keys())
if not keys:
    raise RuntimeError("model.safetensors contains no tensor keys")
print(f"Validated {model.stat().st_size} bytes and {len(keys)} tensor keys")
PY

echo "Checkpoint download and validation complete"
