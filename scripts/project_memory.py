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
    "TASKS.md",
    "schema.json",
    "templates/experiment.md",
    "templates/handoff.md",
    "events.jsonl",
    "tasks.jsonl",
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
TASK_TRANSITIONS = {"started", "updated", "finished"}
TERMINAL_STATUSES = {"complete", "failed", "blocked"}
TASK_RECORD_KEYS = {
    "id",
    "task_id",
    "time",
    "transition",
    "status",
    "summary",
    "command",
    "evidence",
    "commit",
    "tags",
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


def validate_task_record(record: dict, line_number: int) -> list[str]:
    """Validate one append-only task-lifecycle record."""
    prefix = f"tasks.jsonl:{line_number}"
    errors: list[str] = []
    missing = TASK_RECORD_KEYS - record.keys()
    if missing:
        errors.append(f"{prefix}: missing keys: {sorted(missing)}")
    if not re.fullmatch(r"taskevt-[A-Za-z0-9-]+", str(record.get("id", ""))):
        errors.append(f"{prefix}: invalid record id")
    if not re.fullmatch(r"task-[A-Za-z0-9-]+", str(record.get("task_id", ""))):
        errors.append(f"{prefix}: invalid task id")
    try:
        parse_time(str(record["time"]))
    except (KeyError, ValueError):
        errors.append(f"{prefix}: invalid ISO time")
    if record.get("transition") not in TASK_TRANSITIONS:
        errors.append(f"{prefix}: invalid transition: {record.get('transition')!r}")
    if record.get("status") not in ALLOWED_STATUSES:
        errors.append(f"{prefix}: invalid status: {record.get('status')!r}")
    if not isinstance(record.get("summary"), str) or not record["summary"].strip():
        errors.append(f"{prefix}: summary must be a non-empty string")
    if record.get("command") is not None and not isinstance(record.get("command"), str):
        errors.append(f"{prefix}: command must be a string or null")
    if not isinstance(record.get("evidence"), list) or not all(
        isinstance(item, str) and item for item in record["evidence"]
    ):
        errors.append(f"{prefix}: evidence must be a list of non-empty strings")
    if not isinstance(record.get("tags"), list) or not all(
        isinstance(item, str) and item for item in record["tags"]
    ):
        errors.append(f"{prefix}: tags must be a list of non-empty strings")
    if record.get("commit") is not None and not isinstance(record.get("commit"), str):
        errors.append(f"{prefix}: commit must be a string or null")
    transition = record.get("transition")
    status = record.get("status")
    if transition == "started" and status in TERMINAL_STATUSES:
        errors.append(f"{prefix}: started task cannot have terminal status")
    if transition == "updated" and status in TERMINAL_STATUSES:
        errors.append(f"{prefix}: use finished transition for terminal status")
    if transition == "finished" and status not in TERMINAL_STATUSES:
        errors.append(f"{prefix}: finished task requires terminal status")
    if transition == "started" and not str(record.get("command") or "").strip():
        errors.append(f"{prefix}: started task requires a command or manual procedure")
    return errors


def read_jsonl(path: Path, *, label: str, errors: list[str]) -> list[dict]:
    records: list[dict] = []
    if not path.is_file():
        return records
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            errors.append(f"{label}:{line_number}: invalid JSON: {exc}")
    return records


def validate_task_lifecycle(records: list[dict]) -> list[str]:
    """Check that each task has one start and legal append-only transitions."""
    errors: list[str] = []
    histories: dict[str, list[dict]] = {}
    seen_record_ids: set[str] = set()
    previous_time: datetime | None = None
    for line_number, record in enumerate(records, start=1):
        errors.extend(validate_task_record(record, line_number))
        record_id = record.get("id")
        if record_id in seen_record_ids:
            errors.append(f"tasks.jsonl:{line_number}: duplicate record id {record_id!r}")
        seen_record_ids.add(record_id)
        try:
            record_time = parse_time(str(record["time"]))
            if previous_time and record_time < previous_time:
                errors.append(f"tasks.jsonl:{line_number}: time is earlier than previous record")
            previous_time = record_time
        except (KeyError, ValueError):
            pass
        task_id = record.get("task_id")
        if isinstance(task_id, str):
            histories.setdefault(task_id, []).append(record)

    for task_id, history in histories.items():
        if not history:
            continue
        if history[0].get("transition") != "started":
            errors.append(f"tasks.jsonl: {task_id} does not begin with started")
        if sum(row.get("transition") == "started" for row in history) != 1:
            errors.append(f"tasks.jsonl: {task_id} must have exactly one started record")
        finished = False
        for row in history:
            if finished:
                errors.append(f"tasks.jsonl: {task_id} has records after finished")
                break
            if row.get("transition") == "finished":
                finished = True
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

    tasks_path = memory_dir / "tasks.jsonl"
    task_errors: list[str] = []
    task_records = read_jsonl(tasks_path, label="tasks.jsonl", errors=task_errors)
    errors.extend(task_errors)
    errors.extend(validate_task_lifecycle(task_records))
    if check_paths:
        for line_number, record in enumerate(task_records, start=1):
            for item in record.get("evidence", []):
                if not evidence_exists(project_root, item):
                    errors.append(f"tasks.jsonl:{line_number}: missing evidence path {item}")

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
            for path in [*memory_dir.rglob("*.md"), *memory_dir.rglob("*.json"), events_path, tasks_path]:
                if path.is_file() and token in path.read_text(encoding="utf-8", errors="ignore"):
                    errors.append(f"{path.relative_to(project_root)}: contains Dashboard token")
    for path in [*memory_dir.rglob("*.md"), *memory_dir.rglob("*.json"), events_path, tasks_path]:
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


def task_records(memory_dir: Path) -> list[dict]:
    errors: list[str] = []
    return read_jsonl(memory_dir / "tasks.jsonl", label="tasks.jsonl", errors=errors)


def append_task_record(
    *,
    task_id: str,
    transition: str,
    status: str,
    summary: str,
    command: str | None,
    evidence: list[str],
    tags: list[str],
    commit: str | None,
    memory_dir: Path,
    project_root: Path,
    check_paths: bool,
) -> int:
    """Append a validated task transition, rejecting an invalid lifecycle first."""
    existing = task_records(memory_dir)
    history = [row for row in existing if row.get("task_id") == task_id]
    if transition == "started" and history:
        print(f"ERROR: task {task_id} already exists", file=sys.stderr)
        return 1
    if transition != "started" and not history:
        print(f"ERROR: task {task_id} has no started record", file=sys.stderr)
        return 1
    if history and history[-1].get("transition") == "finished":
        print(f"ERROR: task {task_id} is already finished", file=sys.stderr)
        return 1

    candidate = {
        "id": f"taskevt-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}",
        "task_id": task_id,
        "time": utc_now(),
        "transition": transition,
        "status": status,
        "summary": summary,
        "command": command,
        "evidence": sorted(set(evidence)),
        "commit": commit,
        "tags": sorted(set(tags)),
    }
    errors = validate_task_record(candidate, 0)
    if check_paths:
        errors.extend(
            f"missing evidence path: {item}"
            for item in candidate["evidence"]
            if not evidence_exists(project_root, item)
        )
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        return 1

    tasks_path = memory_dir / "tasks.jsonl"
    lock_path = memory_dir / ".tasks.lock"
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        with tasks_path.open("a", encoding="utf-8") as handle:
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


def task_summary(memory_dir: Path) -> int:
    """Print the latest state for every task without changing project files."""
    latest: dict[str, dict] = {}
    for record in task_records(memory_dir):
        if isinstance(record.get("task_id"), str):
            latest[record["task_id"]] = record
    for task_id in sorted(latest):
        record = latest[task_id]
        print(
            f"{task_id}\t{record.get('status')}\t{record.get('transition')}\t"
            f"{record.get('time')}\t{record.get('summary')}"
        )
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
    task = subparsers.add_parser("task", help="append or inspect task lifecycle records")
    task_subparsers = task.add_subparsers(dest="task_command", required=True)

    def add_task_arguments(command_parser: argparse.ArgumentParser, *, start: bool = False) -> None:
        command_parser.add_argument("--task-id", required=True)
        command_parser.add_argument("--summary", required=True)
        command_parser.add_argument("--command", dest="task_shell_command", required=start)
        command_parser.add_argument("--evidence", action="append", default=[])
        command_parser.add_argument("--tag", action="append", default=[])
        command_parser.add_argument("--commit")

    task_start = task_subparsers.add_parser("start", help="record a task before it changes state")
    task_start.add_argument("--status", choices=sorted(ALLOWED_STATUSES - TERMINAL_STATUSES), default="running")
    add_task_arguments(task_start, start=True)
    task_update = task_subparsers.add_parser("update", help="record non-terminal task progress")
    task_update.add_argument("--status", choices=sorted(ALLOWED_STATUSES - TERMINAL_STATUSES), default="running")
    add_task_arguments(task_update)
    task_finish = task_subparsers.add_parser("finish", help="record a task terminal result")
    task_finish.add_argument("--status", choices=sorted(TERMINAL_STATUSES), required=True)
    add_task_arguments(task_finish)
    task_subparsers.add_parser("list", help="show latest status of each task")
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
        task_count = sum(
            1
            for line in (memory_dir / "tasks.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        print(
            f"project memory ok: {len(REQUIRED_FILES)} required files, "
            f"{event_count} events, {task_count} task records"
        )
        return 0

    if args.command == "task":
        if args.task_command == "list":
            return task_summary(memory_dir)
        transition = {"start": "started", "update": "updated", "finish": "finished"}[args.task_command]
        commit = args.commit or current_commit(project_root)
        return append_task_record(
            task_id=args.task_id,
            transition=transition,
            status=args.status,
            summary=args.summary,
            command=getattr(args, "task_shell_command", None),
            evidence=args.evidence,
            tags=args.tag,
            commit=commit,
            memory_dir=memory_dir,
            project_root=project_root,
            check_paths=not args.no_path_check,
        )

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
