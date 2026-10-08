#!/usr/bin/env python3
"""Canonical compact Kanban snapshot reader and owned Task scratch workspace.

Temporary scripts belong in owned /opt/data DevKit scratch rather than in
project .hermes/tasks. Cleanup is restricted to marked directories after Kanban
records DONE. No project source, baseline, evidence or session history is deleted.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys

TASK_RE = re.compile(r"t_[A-Za-z0-9_-]{1,96}\Z")
PROFILE_NAMES = ("coder", "reviewer")
DEFAULT_ROOT = Path(os.getenv("HERMES_DEVKIT_TASK_SCRATCH_ROOT", "/opt/data/devkit/task-scratch"))
MAX_SNAPSHOT_BYTES = 10 * 1024 * 1024
ALLOWED_FIELDS = {
    "id", "title", "status", "assignee", "body", "workspace_path",
    "workspace_version_control", "model_override", "provider_override",
    "current_run_id", "children", "result", "completed_at",
}


class ArtifactError(RuntimeError):
    pass


def _task_key(task_id: str) -> str:
    if not TASK_RE.fullmatch(task_id):
        raise ArtifactError("invalid task ID")
    return task_id


def scratch_path(root: Path, workspace: Path, task_id: str) -> Path:
    key = sha256(str(workspace.resolve()).encode("utf-8")).hexdigest()[:20]
    return root.resolve() / key / _task_key(task_id)


def allocate_scratch(root: Path, workspace: Path, task_id: str) -> Path:
    if not workspace.is_dir() or workspace.is_symlink():
        raise ArtifactError("workspace missing or not a real directory")
    directory = scratch_path(root, workspace, task_id)
    if directory.is_symlink():
        raise ArtifactError("scratch path must not be a symlink")
    directory.mkdir(parents=True, exist_ok=True)
    marker = directory / ".devkit-owned.json"
    identity = {"schema": 1, "task_id": task_id, "workspace": str(workspace.resolve())}
    if marker.exists():
        try:
            current = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ArtifactError("owned scratch marker corrupt") from exc
        if current != identity:
            raise ArtifactError("owned scratch marker mismatch")
    else:
        marker.write_text(json.dumps(identity, sort_keys=True) + "\n", encoding="utf-8")
    return directory


def _confirmed_done(board_db: Path, workspace: Path, task_id: str) -> bool:
    uri = f"file:{board_db.resolve().as_posix()}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True, timeout=1.0) as conn:
            row = conn.execute(
                "SELECT status, workspace_path FROM tasks WHERE id = ?",
                (_task_key(task_id),),
            ).fetchone()
    except (sqlite3.Error, OSError):
        return False
    return bool(
        row and str(row[0] or "").lower() in {"done", "completed"}
        and row[1] and Path(str(row[1])).resolve() == workspace.resolve()
    )


def cleanup_completed_scratch(
    *, board_db: Path, workspace: Path, task_id: str, root: Path = DEFAULT_ROOT,
) -> bool:
    """Best-effort removal of scratch owned by one confirmed completed Task."""
    if not workspace.is_dir() or not _confirmed_done(board_db, workspace, task_id):
        return False
    directory = scratch_path(root, workspace, task_id)
    marker = directory / ".devkit-owned.json"
    if directory.is_symlink() or marker.is_symlink() or not marker.is_file():
        return False
    try:
        actual = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if actual != {
        "schema": 1, "task_id": task_id, "workspace": str(workspace.resolve()),
    }:
        return False
    # Python shutil does not follow a symlink to a directory when recursing.
    # Never recurse into source workspace or other Task directories.
    shutil.rmtree(directory)
    return True


def inspect_snapshot(
    *, source: Path, profile: str, fields: list[str], last_comments: int = 4,
) -> dict[str, object]:
    if profile not in PROFILE_NAMES:
        raise ArtifactError("invalid profile")
    approved_root = Path("/opt/data/profiles") / profile / "cache" / "spillover"
    if not approved_root.is_dir():
        # Repository unit tests can supply an isolated fixture through this
        # explicit environment setting; runtime defaults never allow arbitrary paths.
        override = os.getenv("HERMES_DEVKIT_SNAPSHOT_FIXTURE_ROOT")
        if not override:
            raise ArtifactError("profile spillover directory unavailable")
        approved_root = Path(override)
    if source.is_symlink() or approved_root.resolve() not in source.resolve().parents:
        raise ArtifactError("snapshot is not within the selected profile spillover")
    if not source.is_file() or source.stat().st_size > MAX_SNAPSHOT_BYTES:
        raise ArtifactError("snapshot missing or too large")
    if any(field not in ALLOWED_FIELDS for field in fields):
        raise ArtifactError("unsupported snapshot field requested")
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("task"), dict):
        raise ArtifactError("invalid Kanban task snapshot")
    task = data["task"]
    selected = {field: task.get(field) for field in fields}
    if last_comments:
        comments = task.get("comments", [])
        if isinstance(comments, list):
            selected["comments"] = comments[-min(last_comments, 12):]
    return selected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    snap = sub.add_parser("inspect-snapshot")
    snap.add_argument("--source", required=True)
    snap.add_argument("--profile", choices=PROFILE_NAMES, required=True)
    snap.add_argument("--fields", default="id,title,status,assignee,body")
    snap.add_argument("--comments", type=int, default=4)
    scratch = sub.add_parser("scratch")
    scratch.add_argument("--task-id", required=True)
    scratch.add_argument("--workspace", required=True)
    scratch.add_argument("--root", default=str(DEFAULT_ROOT))
    args = parser.parse_args(argv)
    try:
        if args.action == "inspect-snapshot":
            data = inspect_snapshot(
                source=Path(args.source), profile=args.profile,
                fields=[part.strip() for part in args.fields.split(",") if part.strip()],
                last_comments=max(0, args.comments),
            )
            print(json.dumps(data, ensure_ascii=False, indent=2))
            return 0
        path = allocate_scratch(Path(args.root), Path(args.workspace), args.task_id)
        print(f"TASK_SCRATCH={path}")
        return 0
    except (ArtifactError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"TASK_ARTIFACT_STATUS=BLOCKED\nTASK_ARTIFACT_ERROR={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
