#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="/root/autodl-tmp/pi05-libero-reproduction"
cd "$PROJECT_ROOT"

mkdir -p logs

# Wait for the shorter interactive spatial run, if it is still active. The full
# runner skips suites that already have eval_info.json, so this is safe to run
# even when spatial finishes before this watcher starts.
while screen -list | grep -Eq '[0-9]+\.pi05-baseline[[:space:]]'; do
  sleep 60
done

exec "$PROJECT_ROOT/.venv/bin/python" \
  "$PROJECT_ROOT/scripts/benchmark_libero.py" \
  --suites libero_spatial,libero_object,libero_goal,libero_10 \
  --n-episodes 10 \
  --seed 1000 \
  --output-root "$PROJECT_ROOT/outputs/benchmark/pi05-libero" \
  >> "$PROJECT_ROOT/logs/benchmark-overnight.log" 2>&1
