#!/usr/bin/env bash
# Run a state-changing command with a mandatory task-memory lifecycle.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/run_tracked_task.sh --task-id task-... --summary TEXT --log PATH \
    [--evidence PATH]... [--tag TAG]... -- command [arg ...]

The wrapper creates a running task record before execution and a terminal
record afterwards. It appends command stdout/stderr to --log and returns the
underlying command's exit code.
EOF
}

task_id=""
summary=""
log_path=""
evidence=()
tags=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --task-id) task_id=${2:?missing task id}; shift 2 ;;
    --summary) summary=${2:?missing summary}; shift 2 ;;
    --log) log_path=${2:?missing log path}; shift 2 ;;
    --evidence) evidence+=("${2:?missing evidence path}"); shift 2 ;;
    --tag) tags+=("${2:?missing tag}"); shift 2 ;;
    --help|-h) usage; exit 0 ;;
    --) shift; break ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$task_id" || -z "$summary" || -z "$log_path" || $# -eq 0 ]]; then
  usage >&2
  exit 2
fi

mkdir -p "$(dirname "$log_path")"
touch "$log_path"
evidence+=("$log_path")
task_command=$(printf '%q ' "$@")
task_args=(./.venv/bin/python scripts/project_memory.py task start
  --task-id "$task_id" --status running --summary "$summary" --command "$task_command")
for item in "${evidence[@]}"; do task_args+=(--evidence "$item"); done
for item in "${tags[@]}"; do task_args+=(--tag "$item"); done
"${task_args[@]}"

set +e
"$@" >>"$log_path" 2>&1
exit_code=$?
set -e
if [[ $exit_code -eq 0 ]]; then
  terminal_status=complete
else
  terminal_status=failed
fi
finish_args=(./.venv/bin/python scripts/project_memory.py task finish
  --task-id "$task_id" --status "$terminal_status"
  --summary "$summary (exit code $exit_code)" --evidence "$log_path")
for item in "${evidence[@]}"; do finish_args+=(--evidence "$item"); done
for item in "${tags[@]}"; do finish_args+=(--tag "$item"); done
"${finish_args[@]}"
exit "$exit_code"
