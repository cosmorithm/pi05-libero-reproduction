#!/usr/bin/env bash
# Start the staged JAX VLM probe only when the GPU and all local prerequisites exist.
set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$project_root"

[[ $(tr -d '[:space:]' < logs/openpi-lean-setup.exitcode) == 0 ]]
grep -q '^OPENPI_CHECKPOINT_DOWNLOAD_COMPLETE$' logs/openpi-assets.log
test -d checkpoints/openpi-pi05-libero/params
test -s assets/paligemma-processor/tokenizer.model
nvidia-smi -L

if screen -ls 2>/dev/null | grep -q '[.]openpi-jax-probe'; then
  echo "openpi-jax-probe is already running"
  exit 0
fi

rm -f logs/openpi-jax-probe-orchestrator.exitcode
./.venv/bin/python scripts/project_memory.py task update \
  --task-id task-openpi-jax-vlm-probe \
  --status running \
  --summary "GPU is visible and all offline JAX/checkpoint prerequisites passed; starting the controlled pilots and formal batch." \
  --evidence logs/openpi-lean-setup.exitcode \
  --evidence logs/openpi-assets.log \
  --tag openpi --tag jax --tag vlm-probe

screen -dmS openpi-jax-probe bash -lc \
  "cd '$project_root' && ./scripts/run_openpi_jax_probe_after_prereqs.sh > logs/openpi-jax-probe-orchestrator.log 2>&1; code=\$?; echo \$code > logs/openpi-jax-probe-orchestrator.exitcode"

screen -ls
