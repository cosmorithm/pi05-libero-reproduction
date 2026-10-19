#!/usr/bin/env bash
# Queue a full third-seed benchmark without competing with the active GPU evaluation.
set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$project_root"

predecessor_screen=${1:-pi05-s2000-libero10}
log_path=logs/benchmark-seed3000-full.log
exit_path=logs/benchmark-seed3000-full.exitcode
output_root=outputs/benchmark/pi05-libero-seed3000
task_id=task-libero-seed3000-full

while screen -ls 2>/dev/null | grep -q "[.]${predecessor_screen}"; do
  sleep 15
done

touch "$log_path"
./.venv/bin/python scripts/project_memory.py task update \
  --task-id "$task_id" \
  --status running \
  --summary "GPU released by ${predecessor_screen}; seed=3000 four-suite robustness benchmark is starting." \
  --evidence "$log_path" \
  --evidence scripts/benchmark_libero.py \
  --tag benchmark --tag libero --tag seed=3000

source .venv/bin/activate
export LIBERO_CONFIG_PATH="$project_root/home/.libero"
export HF_HOME="$project_root/cache/huggingface"
export HF_ENDPOINT=https://hf-mirror.com
export HF_HUB_DISABLE_XET=1
export MUJOCO_GL=egl

set +e
.venv/bin/python scripts/benchmark_libero.py \
  --suites libero_spatial,libero_object,libero_goal,libero_10 \
  --n-episodes 10 \
  --seed 3000 \
  --output-root "$output_root" >>"$log_path" 2>&1
exit_code=$?
set -e
printf '%s\n' "$exit_code" >"$exit_path"

if [[ $exit_code -eq 0 ]]; then
  terminal_status=complete
  terminal_summary="seed=3000 four-suite Pi0.5-LIBERO robustness benchmark completed successfully."
else
  terminal_status=failed
  terminal_summary="seed=3000 four-suite Pi0.5-LIBERO robustness benchmark failed with exit code ${exit_code}."
fi
finish_args=(./.venv/bin/python scripts/project_memory.py task finish
  --task-id "$task_id" --status "$terminal_status" --summary "$terminal_summary"
  --evidence "$log_path" --evidence "$exit_path")
if [[ $exit_code -eq 0 ]]; then
  finish_args+=(--evidence "$output_root/status.json" --evidence "$output_root/summary.json")
fi
finish_args+=(--tag benchmark --tag libero --tag seed=3000)
"${finish_args[@]}"
exit "$exit_code"
