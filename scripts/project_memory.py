#!/usr/bin/env python3
"""Maintain and validate the project's human- and machine-readable memory."""

from __future__ import annotations

import argparse
import fcntl
import json
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MEMORY_DIR = PROJECT_ROOT / "docs" / "memory"
REQUIRED_FILES = (
    "README.md",
    "CURRENT.md",
    "EXPERIMENTS.md",
    "DECISIONS.md",
    "OPEN_QUESTIONS.md",
    "RUNBOOK.md",
    "schema.json",
    "templates/experiment.md",
    "templates/handoff.md",
    "events.jsonl",
)
REQUIRED_EVENT_KEYS = {
    "id",
    "time",
    "event",
    "status",
    "summary",
    "evidence",
    "commit",
    "tags",
}
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
ALLOWED_STATUSES = {
    "planned",
    "preparing",
    "running",
    "complete",
    "failed",
    "blocked",
}
SECRET_PATTERNS = (
    re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def current_commit(root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate_event(event: dict, line_number: int) -> list[str]:
    prefix = f"events.jsonl:{line_number}"
    errors: list[str] = []
    missing = REQUIRED_EVENT_KEYS - event.keys()
    if missing:
        errors.append(f"{prefix}: missing keys: {sorted(missing)}")
    if not re.fullmatch(r"evt-[A-Za-z0-9-]+", str(event.get("id", ""))):
        errors.append(f"{prefix}: invalid event id")
    try:
        parse_time(str(event["time"]))
    except (KeyError, ValueError):
        errors.append(f"{prefix}: invalid ISO time")
    if event.get("event") not in ALLOWED_EVENTS:
        errors.append(f"{prefix}: invalid event type: {event.get('event')!r}")
    if event.get("status") not in ALLOWED_STATUSES:
        errors.append(f"{prefix}: invalid status: {event.get('status')!r}")
    if not isinstance(event.get("summary"), str) or not event["summary"].strip():
        errors.append(f"{prefix}: summary must be a non-empty string")
    if not isinstance(event.get("evidence"), list) or not all(
        isinstance(item, str) and item for item in event["evidence"]
    ):
        errors.append(f"{prefix}: evidence must be a list of non-empty strings")
    if not isinstance(event.get("tags"), list) or not all(
        isinstance(item, str) and item for item in event["tags"]
    ):
        errors.append(f"{prefix}: tags must be a list of non-empty strings")
    if event.get("commit") is not None and not isinstance(event.get("commit"), str):
        errors.append(f"{prefix}: commit must be a string or null")
    return errors


def evidence_exists(root: Path, item: str) -> bool:
    if item.startswith(("http://", "https://", "gs://")):
        return True
    if item.startswith("<") and item.endswith(">"):
        return True
    target = Path(item)
    if not target.is_absolute():
        target = root / target
    if "*" in item:
        return bool(list(root.glob(item)))
    return target.exists()


def validate_memory(
    memory_dir: Path = DEFAULT_MEMORY_DIR,
    project_root: Path = PROJECT_ROOT,
    *,
    check_paths: bool = True,
) -> list[str]:
    errors: list[str] = []
    if not memory_dir.is_dir():
        return [f"missing memory directory: {memory_dir}"]

    for relative in REQUIRED_FILES:
        path = memory_dir / relative
        if not path.is_file():
            errors.append(f"missing file: {relative}")
        elif not path.read_text(encoding="utf-8").strip():
            errors.append(f"empty file: {relative}")

    schema_path = memory_dir / "schema.json"
    if schema_path.is_file():
        try:
            json.loads(schema_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"schema.json: invalid JSON: {exc}")

    events_path = memory_dir / "events.jsonl"
    previous_time: datetime | None = None
    seen_ids: set[str] = set()
    events: list[dict] = []
    if events_path.is_file():
        for line_number, line in enumerate(events_path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"events.jsonl:{line_number}: invalid JSON: {exc}")
                continue
            events.append(event)
            errors.extend(validate_event(event, line_number))
            event_id = event.get("id")
            if event_id in seen_ids:
                errors.append(f"events.jsonl:{line_number}: duplicate id {event_id!r}")
            seen_ids.add(event_id)
            try:
                event_time = parse_time(str(event["time"]))
                if previous_time and event_time < previous_time:
                    errors.append(f"events.jsonl:{line_number}: time is earlier than previous event")
                previous_time = event_time
            except (KeyError, ValueError):
                pass
            if check_paths:
                for item in event.get("evidence", []):
                    if not evidence_exists(project_root, item):
                        errors.append(f"events.jsonl:{line_number}: missing evidence path {item}")

    current_path = memory_dir / "CURRENT.md"
    if current_path.is_file():
        current_text = current_path.read_text(encoding="utf-8")
        if not re.search(r"最后核验：\d{4}-\d{2}-\d{2} \d{2}:\d{2}", current_text):
            errors.append("CURRENT.md: missing '最后核验：YYYY-MM-DD HH:MM'")

    if check_paths:
        # Check local Markdown links in the project entry points and memory files.
        markdown_files = [
            project_root / "README.md",
            project_root / "PROJECT_MEMORY.md",
            *memory_dir.glob("*.md"),
            *memory_dir.glob("templates/*.md"),
        ]
        link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
        for markdown in markdown_files:
            if not markdown.is_file():
                continue
            for target in link_pattern.findall(markdown.read_text(encoding="utf-8")):
                target = target.strip()
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                target = target.split("#", 1)[0]
                if not target or target.startswith("<"):
                    continue
                candidate = (markdown.parent / target).resolve()
                if not candidate.exists():
                    errors.append(f"{markdown.relative_to(project_root)}: broken link {target}")

    token_path = project_root / ".dashboard_token"
    if token_path.is_file():
        token = token_path.read_text(encoding="utf-8").strip()
        if len(token) >= 16:
            for path in [*memory_dir.rglob("*.md"), *memory_dir.rglob("*.json"), events_path]:
                if path.is_file() and token in path.read_text(encoding="utf-8", errors="ignore"):
                    errors.append(f"{path.relative_to(project_root)}: contains Dashboard token")
    for path in [*memory_dir.rglob("*.md"), *memory_dir.rglob("*.json"), events_path]:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"{path.relative_to(project_root)}: possible secret pattern")

    return errors


def append_event(
    *,
    event_type: str,
    status: str,
    summary: str,
    evidence: list[str],
    tags: list[str],
    commit: str | None,
    memory_dir: Path,
    project_root: Path,
    check_paths: bool,
) -> int:
    candidate = {
        "id": f"evt-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}",
        "time": utc_now(),
        "event": event_type,
        "status": status,
        "summary": summary,
        "evidence": sorted(set(evidence)),
        "commit": commit,
        "tags": sorted(set(tags)),
    }
    errors = validate_event(candidate, 0)
    if check_paths:
        errors.extend(
            f"missing evidence path: {item}"
            for item in candidate["evidence"]
            if not evidence_exists(project_root, item)
        )
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        return 1

    events_path = memory_dir / "events.jsonl"
    lock_path = memory_dir / ".events.lock"
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        with events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(candidate, ensure_ascii=False) + "\n")
            handle.flush()
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    print(json.dumps(candidate, ensure_ascii=False, indent=2))
    validation_errors = validate_memory(
        memory_dir=memory_dir,
        project_root=project_root,
        check_paths=check_paths,
    )
    if validation_errors:
        print("\n".join(f"ERROR: {error}" for error in validation_errors), file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=DEFAULT_MEMORY_DIR)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--no-path-check", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate", help="validate all memory files and events")
    add = subparsers.add_parser("add-event", help="append one validated event")
    add.add_argument("--event", required=True, choices=sorted(ALLOWED_EVENTS))
    add.add_argument("--status", required=True, choices=sorted(ALLOWED_STATUSES))
    add.add_argument("--summary", required=True)
    add.add_argument("--evidence", action="append", default=[])
    add.add_argument("--tag", action="append", default=[])
    add.add_argument("--commit")
    args = parser.parse_args(argv)
    memory_dir = args.dir.resolve()
    project_root = args.project_root.resolve()

    if args.command == "validate":
        errors = validate_memory(
            memory_dir=memory_dir,
            project_root=project_root,
            check_paths=not args.no_path_check,
        )
        if errors:
            print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
            return 1
        event_count = sum(
            1
            for line in (memory_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        print(f"project memory ok: {len(REQUIRED_FILES)} required files, {event_count} events")
        return 0

    commit = args.commit or current_commit(project_root)
    return append_event(
        event_type=args.event,
        status=args.status,
        summary=args.summary,
        evidence=args.evidence,
        tags=args.tag,
        commit=commit,
        memory_dir=memory_dir,
        project_root=project_root,
        check_paths=not args.no_path_check,
    )


if __name__ == "__main__":
    raise SystemExit(main())
