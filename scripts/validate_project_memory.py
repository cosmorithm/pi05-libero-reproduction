#!/usr/bin/env python3
"""Validate the structured project memory directory."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

REQUIRED_FILES = (
    "README.md",
    "CURRENT.md",
    "EXPERIMENTS.md",
    "DECISIONS.md",
    "OPEN_QUESTIONS.md",
    "RUNBOOK.md",
    "events.jsonl",
)
REQUIRED_EVENT_KEYS = {"time", "event", "status", "summary", "evidence", "tags"}
ALLOWED_EVENTS = {
    "task_started",
    "task_finished",
    "experiment_completed",
    "incident",
    "decision",
    "environment_changed",
    "handoff",
    "open_question",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "docs" / "memory",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors: list[str] = []
    if not args.dir.is_dir():
        print(f"missing memory directory: {args.dir}", file=sys.stderr)
        return 2

    for name in REQUIRED_FILES:
        path = args.dir / name
        if not path.is_file():
            errors.append(f"missing file: {name}")
        elif not path.read_text(encoding="utf-8").strip():
            errors.append(f"empty file: {name}")

    event_path = args.dir / "events.jsonl"
    count = 0
    if event_path.is_file():
        for line_number, line in enumerate(event_path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            count += 1
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"events.jsonl:{line_number}: invalid JSON: {exc}")
                continue
            missing = REQUIRED_EVENT_KEYS - event.keys()
            if missing:
                errors.append(f"events.jsonl:{line_number}: missing keys: {sorted(missing)}")
            if event.get("event") not in ALLOWED_EVENTS:
                errors.append(f"events.jsonl:{line_number}: invalid event type: {event.get('event')!r}")
            try:
                datetime.fromisoformat(str(event.get("time", "")).replace("Z", "+00:00"))
            except ValueError:
                errors.append(f"events.jsonl:{line_number}: invalid ISO time")
            if not isinstance(event.get("evidence"), list):
                errors.append(f"events.jsonl:{line_number}: evidence must be a list")
            if not isinstance(event.get("tags"), list):
                errors.append(f"events.jsonl:{line_number}: tags must be a list")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"project memory ok: {len(REQUIRED_FILES)} files, {count} events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
