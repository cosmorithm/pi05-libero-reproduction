#!/usr/bin/env bash
# Complete the JAX VLM probe only after its independent prerequisites are valid.
set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$project_root"

task_cli=(./.venv/bin/python scripts/project_memory.py)
probe_python=.venv-openpi/bin/python
probe_script=scripts/probe_pi05_vlm_language_jax.py
checkpoint=checkpoints/openpi-pi05-libero
image=outputs/smoke/image.png
tokenizer=assets/paligemma-processor/tokenizer.model
install_log=logs/openpi-setup.log
install_exit=logs/openpi-setup.exitcode
assets_log=logs/openpi-assets.log
task_id=task-openpi-jax-vlm-probe

finish_task() {
  local id=$1
  local status=$2
  local summary=$3
  shift 3
  "${task_cli[@]}" task finish --task-id "$id" --status "$status" --summary "$summary" "$@"
}

wait_for_install() {
  while [[ ! -f "$install_exit" ]]; do
    sleep 20
  done
  local code
  code=$(tr -d '[:space:]' < "$install_exit")
  if [[ "$code" != "0" ]]; then
    finish_task task-openpi-jax-install failed "OpenPI JAX editable install exited with code ${code}." \
      --evidence "$install_log" --evidence "$install_exit" --tag openpi --tag jax --tag environment
    finish_task "$task_id" blocked "JAX probe blocked because the OpenPI environment install failed." \
      --evidence "$install_log" --evidence "$install_exit" --tag openpi --tag jax --tag vlm-probe
    return 1
  fi
  "$probe_python" -c 'import flax, jax, openpi, orbax.checkpoint; print(jax.__version__)'
  finish_task task-openpi-jax-install complete "OpenPI JAX editable install and import verification completed." \
    --evidence "$install_log" --evidence "$install_exit" --tag openpi --tag jax --tag environment
}

wait_for_assets() {
  while ! grep -q '^OPENPI_CHECKPOINT_DOWNLOAD_COMPLETE$' "$assets_log" 2>/dev/null; do
    if ! screen -ls 2>/dev/null | grep -q '[.]openpi-assets'; then
      finish_task task-openpi-checkpoint-download failed "OpenPI checkpoint downloader exited without its completion marker." \
        --evidence "$assets_log" --tag openpi --tag checkpoint --tag network
      finish_task "$task_id" blocked "JAX probe blocked because the checkpoint downloader did not verify completion." \
        --evidence "$assets_log" --tag openpi --tag jax --tag vlm-probe
      return 1
    fi
    sleep 20
  done
  test -d "$checkpoint/params"
  finish_task task-openpi-checkpoint-download complete "Official OpenPI pi05_libero checkpoint download verified by the downloader." \
    --evidence "$assets_log" --evidence "$checkpoint/params" --tag openpi --tag checkpoint --tag network
}

wait_for_gpu() {
  while screen -ls 2>/dev/null | grep -q '[.]pi05-s2000-libero10'; do
    sleep 15
  done
  if [[ -f logs/benchmark-libero10-seed2000.exitcode ]] && [[ $(tr -d '[:space:]' < logs/benchmark-libero10-seed2000.exitcode) == 0 ]]; then
    finish_task task-libero-seed2000-10 complete "seed=2000 libero_10 evaluator exited successfully; its output is ready for later multi-seed aggregation." \
      --evidence logs/benchmark-libero10-seed2000.log \
      --evidence logs/benchmark-libero10-seed2000.exitcode \
      --evidence outputs/benchmark/pi05-libero-seed2000/status.json \
      --tag benchmark --tag libero --tag seed=2000
  fi
}

run_probe() {
  local output_dir=$1
  shift
  XLA_PYTHON_CLIENT_PREALLOCATE=false \
  XLA_PYTHON_CLIENT_MEM_FRACTION=0.70 \
  "$probe_python" "$probe_script" \
    --checkpoint "$checkpoint" \
    --image "$image" \
    --tokenizer-model "$tokenizer" \
    --output-dir "$output_dir" "$@"
}

wait_for_install
wait_for_assets
wait_for_gpu

"${task_cli[@]}" task update --task-id "$task_id" --status running \
  --summary "OpenPI JAX environment, official checkpoint, and GPU are ready; running controlled direct-VLM pilots and the formal batch." \
  --evidence "$probe_script" --evidence "$install_log" --evidence "$assets_log" \
  --tag openpi --tag jax --tag vlm-probe

pilot_flip=outputs/vlm_probe/jax_pilot_flip_20261019
pilot_no_flip=outputs/vlm_probe/jax_pilot_no_flip_20261019
full_output=outputs/vlm_probe/jax_full_100_20261019

set +e
run_probe "$pilot_flip" --limit 1 --max-new-tokens 8
code=$?
set -e
if [[ $code -ne 0 ]]; then
  finish_task "$task_id" failed "JAX direct-VLM flipped-image pilot failed with exit code ${code}." \
    --evidence "$pilot_flip/status.json" --tag openpi --tag jax --tag vlm-probe
  exit "$code"
fi

set +e
run_probe "$pilot_no_flip" --limit 1 --max-new-tokens 8 --no-flip-image
code=$?
set -e
if [[ $code -ne 0 ]]; then
  finish_task "$task_id" failed "JAX direct-VLM unflipped-image pilot failed with exit code ${code}." \
    --evidence "$pilot_flip/status.json" --evidence "$pilot_no_flip/status.json" --tag openpi --tag jax --tag vlm-probe
  exit "$code"
fi

set +e
run_probe "$full_output" --limit 100 --max-new-tokens 32
code=$?
set -e
if [[ $code -ne 0 ]]; then
  finish_task "$task_id" failed "JAX direct-VLM 100-question batch failed with exit code ${code}." \
    --evidence "$pilot_flip/status.json" --evidence "$pilot_no_flip/status.json" \
    --evidence "$full_output/status.json" --tag openpi --tag jax --tag vlm-probe
  exit "$code"
fi

finish_task "$task_id" complete "Official OpenPI JAX direct-VLM probe completed: two one-question image-preprocessing pilots and a 100-question formal batch." \
  --evidence "$pilot_flip/status.json" --evidence "$pilot_no_flip/status.json" \
  --evidence "$full_output/status.json" --evidence "$full_output/results.jsonl" \
  --tag openpi --tag jax --tag vlm-probe
