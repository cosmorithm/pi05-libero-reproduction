#!/usr/bin/env python3
"""Run resumable, reproducible LIBERO evaluations for the Pi0.5 checkpoint."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path("/root/autodl-tmp/pi05-libero-reproduction")
DEFAULT_OUTPUT_ROOT = ROOT / "outputs" / "benchmark" / "pi05-libero"
DEFAULT_POLICY_PATH = ROOT / "checkpoints" / "lerobot-pi05-libero-finetuned"
STANDARD_SUITES = (
    "libero_spatial",
    "libero_object",
    "libero_goal",
    "libero_10",
)
WILSON_Z = 1.959963984540054


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suites",
        default=",".join(STANDARD_SUITES),
        help="Comma-separated LIBERO suites to evaluate",
    )
    parser.add_argument("--n-episodes", type=int, default=10)
    parser.add_argument("--seed", type=int, default=1000)
    parser.add_argument("--policy-path", type=Path, default=DEFAULT_POLICY_PATH)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--force", action="store_true", help="Rerun suites with existing results")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    args.suite_list = [part.strip() for part in args.suites.split(",") if part.strip()]
    unknown = [suite for suite in args.suite_list if suite not in STANDARD_SUITES]
    if unknown:
        parser.error(f"unsupported suite(s): {', '.join(unknown)}")
    if args.n_episodes < 1:
        parser.error("--n-episodes must be positive")
    if args.seed < 0:
        parser.error("--seed must be non-negative")
    return args


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def wilson_interval(successes: int, episodes: int) -> tuple[float, float]:
    if episodes <= 0:
        return 0.0, 0.0
    proportion = successes / episodes
    denominator = 1.0 + WILSON_Z**2 / episodes
    center = (proportion + WILSON_Z**2 / (2.0 * episodes)) / denominator
    margin = (
        WILSON_Z
        * math.sqrt(
            proportion * (1.0 - proportion) / episodes
            + WILSON_Z**2 / (4.0 * episodes**2)
        )
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def git_head() -> str:
    return subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        text=True,
    ).strip()


def base_environment(output_root: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        MUJOCO_GL="egl",
        LIBERO_CONFIG_PATH=str(ROOT / "home/.libero"),
        HF_HOME=str(ROOT / "cache/huggingface"),
        HF_ENDPOINT="https://hf-mirror.com",
        HF_HUB_DISABLE_XET="1",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        PYTHONUNBUFFERED="1",
        TOKENIZERS_PARALLELISM="false",
        CUDA_VISIBLE_DEVICES="0",
        BENCHMARK_OUTPUT_ROOT=str(output_root),
    )
    return environment


def preflight(policy_path: Path, environment: dict[str, str]) -> None:
    lerobot_eval = ROOT / ".venv/bin/lerobot-eval"
    python = ROOT / ".venv/bin/python"
    weights = policy_path / "model.safetensors"
    if not lerobot_eval.is_file() or not os.access(lerobot_eval, os.X_OK):
        raise FileNotFoundError(f"missing executable: {lerobot_eval}")
    if not weights.is_file():
        raise FileNotFoundError(f"missing checkpoint weights: {weights}")
    if weights.stat().st_size < 7_000_000_000:
        raise RuntimeError(f"checkpoint looks incomplete: {weights} ({weights.stat().st_size} bytes)")
    tokenizer_check = (
        "from transformers import AutoTokenizer; "
        "AutoTokenizer.from_pretrained('google/paligemma-3b-pt-224', local_files_only=True); "
        "print('tokenizer-ok')"
    )
    result = subprocess.run(
        [str(python), "-c", tokenizer_check],
        cwd=ROOT,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0 or "tokenizer-ok" not in result.stdout:
        raise RuntimeError("PaliGemma tokenizer is not available offline")


def build_eval_command(
    suite: str,
    suite_dir: Path,
    policy_path: Path,
    n_episodes: int,
    seed: int,
) -> list[str]:
    return [
        str(ROOT / ".venv/bin/lerobot-eval"),
        f"--output_dir={suite_dir}",
        "--env.type=libero",
        f"--env.task={suite}",
        "--env.observation_height=256",
        "--env.observation_width=256",
        "--env.max_parallel_tasks=1",
        "--env.control_mode=relative",
        "--env.init_states=true",
        "--env.hard_reset=true",
        "--eval.batch_size=1",
        f"--eval.n_episodes={n_episodes}",
        "--eval.use_async_envs=false",
        f"--policy.path={policy_path}",
        "--policy.device=cuda",
        "--policy.dtype=bfloat16",
        "--policy.n_action_steps=10",
        "--policy.compile_model=false",
        f"--seed={seed}",
        f"--job_name=pi05-baseline-{suite}",
    ]


def update_status(status_path: Path, **changes: Any) -> None:
    status: dict[str, Any] = {}
    if status_path.exists():
        try:
            status = read_json(status_path)
        except Exception:
            status = {}
    status.update(changes)
    status["updated_at"] = utc_now()
    write_json_atomic(status_path, status)


def run_suite(
    suite: str,
    args: argparse.Namespace,
    environment: dict[str, str],
    status_path: Path,
) -> Path:
    suite_dir = args.output_root / suite
    eval_info = suite_dir / "eval_info.json"
    if eval_info.is_file() and not args.force:
        print(f"[{suite}] found existing eval_info.json; skipping")
        return eval_info

    suite_dir.mkdir(parents=True, exist_ok=True)
    command = build_eval_command(suite, suite_dir, args.policy_path, args.n_episodes, args.seed)
    command_text = shlex.join(command)
    (suite_dir / "command.txt").write_text(command_text + "\n", encoding="utf-8")
    write_json_atomic(
        suite_dir / "metadata.json",
        {
            "suite": suite,
            "n_episodes": args.n_episodes,
            "seed": args.seed,
            "policy_path": str(args.policy_path),
            "policy_weights_bytes": (args.policy_path / "model.safetensors").stat().st_size,
            "git_commit": git_head(),
            "started_at": utc_now(),
            "command": command,
        },
    )
    if args.dry_run:
        print(command_text)
        return eval_info

    update_status(
        status_path,
        state="running",
        current_suite=suite,
        current_command=command,
    )
    log_path = suite_dir / "run.log"
    started_at = time.time()
    print(f"[{suite}] starting {args.n_episodes} episodes per task")
    print(f"[{suite}] log: {log_path}")
    with log_path.open("w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        try:
            for line in process.stdout:
                print(line, end="")
                log_file.write(line)
                log_file.flush()
        except KeyboardInterrupt:
            process.terminate()
            process.wait(timeout=30)
            raise
        return_code = process.wait()

    duration = time.time() - started_at
    if return_code != 0:
        update_status(
            status_path,
            state="error",
            current_suite=suite,
            return_code=return_code,
            duration_seconds=round(duration, 3),
        )
        raise RuntimeError(f"[{suite}] lerobot-eval exited with code {return_code}")
    if not eval_info.is_file():
        raise RuntimeError(f"[{suite}] evaluation finished without eval_info.json")
    print(f"[{suite}] complete in {duration:.1f}s")
    update_status(
        status_path,
        state="running",
        current_suite=suite,
        last_completed_suite=suite,
        last_duration_seconds=round(duration, 3),
    )
    return eval_info


def extract_row(suite: str, eval_info: dict[str, Any]) -> dict[str, Any]:
    per_group = eval_info.get("per_group") or {}
    metrics = per_group.get(suite) or eval_info.get("overall") or {}
    overall = eval_info.get("overall") or {}
    if metrics.get("eval_s") is None:
        metrics = {**metrics, "eval_s": overall.get("eval_s")}
    per_task = eval_info.get("per_task") or []
    ci = metrics.get("pc_success_ci95") or [None, None]
    return {
        "suite": suite,
        "tasks": len(per_task),
        "episodes": int(metrics.get("n_episodes", 0)),
        "successes": int(metrics.get("n_success", 0)),
        "success_rate_pct": float(metrics.get("pc_success", 0.0)),
        "ci95_low_pct": ci[0],
        "ci95_high_pct": ci[1],
        "avg_sum_reward": metrics.get("avg_sum_reward"),
        "eval_seconds": metrics.get("eval_s"),
    }


def write_summary(
    output_root: Path,
    suite_rows: list[dict[str, Any]],
    args: argparse.Namespace,
) -> dict[str, Any]:
    episodes = sum(row["episodes"] for row in suite_rows)
    successes = sum(row["successes"] for row in suite_rows)
    ci_low, ci_high = wilson_interval(successes, episodes)
    overall = {
        "episodes": episodes,
        "successes": successes,
        "success_rate_pct": (100.0 * successes / episodes) if episodes else 0.0,
        "ci95_low_pct": 100.0 * ci_low,
        "ci95_high_pct": 100.0 * ci_high,
    }
    summary = {
        "generated_at": utc_now(),
        "git_commit": git_head(),
        "policy_path": str(args.policy_path),
        "seed": args.seed,
        "n_episodes_per_task": args.n_episodes,
        "protocol": {
            "batch_size": 1,
            "n_action_steps": 10,
            "compile_model": False,
            "control_mode": "relative",
            "init_states": True,
            "hard_reset": True,
            "observation": "2 x 256x256 RGB + 8D state",
            "action": "7D relative control",
        },
        "suites": suite_rows,
        "overall": overall,
    }
    write_json_atomic(output_root / "summary.json", summary)

    fieldnames = list(suite_rows[0].keys()) if suite_rows else ["suite"]
    with (output_root / "summary.csv").open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(suite_rows)

    lines = [
        "# Pi0.5 LIBERO Baseline",
        "",
        f"- Policy: `{args.policy_path}`",
        f"- Git commit: `{summary['git_commit']}`",
        f"- Seed: `{args.seed}`",
        f"- Episodes per task: `{args.n_episodes}`",
        "",
        "| Suite | Tasks | Episodes | Success | Success rate | 95% CI | Eval seconds |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in suite_rows:
        ci_text = "n/a"
        if row["ci95_low_pct"] is not None and row["ci95_high_pct"] is not None:
            ci_text = f"{row['ci95_low_pct']:.1f}% to {row['ci95_high_pct']:.1f}%"
        eval_seconds = row["eval_seconds"]
        eval_text = f"{eval_seconds:.1f}" if eval_seconds is not None else "n/a"
        lines.append(
            f"| `{row['suite']}` | {row['tasks']} | {row['episodes']} | "
            f"{row['successes']} | {row['success_rate_pct']:.1f}% | {ci_text} | {eval_text} |"
        )
    lines.extend(
        [
            "",
            f"Overall: **{successes}/{episodes} = {overall['success_rate_pct']:.1f}%** "
            f"(95% Wilson {overall['ci95_low_pct']:.1f}% to {overall['ci95_high_pct']:.1f}%)",
            "",
        ]
    )
    (output_root / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def main() -> None:
    args = parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    environment = base_environment(args.output_root)
    print("Pi0.5 LIBERO benchmark")
    print(f"  git:    {git_head()}")
    print(f"  policy: {args.policy_path}")
    print(f"  suites: {', '.join(args.suite_list)}")
    print(f"  seed:   {args.seed}")
    print(f"  output: {args.output_root}")

    preflight(args.policy_path, environment)
    status_path = args.output_root / "status.json"
    update_status(
        status_path,
        state="starting",
        started_at=utc_now(),
        suites=args.suite_list,
        n_episodes=args.n_episodes,
        seed=args.seed,
        policy_path=str(args.policy_path),
        git_commit=git_head(),
    )

    try:
        for suite in args.suite_list:
            run_suite(suite, args, environment, status_path)
        rows = []
        for suite in args.suite_list:
            eval_info = args.output_root / suite / "eval_info.json"
            if eval_info.is_file():
                rows.append(extract_row(suite, read_json(eval_info)))
        summary = write_summary(args.output_root, rows, args)
        update_status(
            status_path,
            state="complete",
            finished_at=utc_now(),
            overall=summary["overall"],
        )
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    except Exception as exc:
        update_status(
            status_path,
            state="error",
            finished_at=utc_now(),
            error=f"{type(exc).__name__}: {exc}",
        )
        raise


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
