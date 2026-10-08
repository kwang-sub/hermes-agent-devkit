"""Task-scoped transient review handoff; never stores permanent task history.

No Task files, snapshots, source changes or verification receipts are removed.
Legacy callers without a task_id use the repository-global filename for
compatibility, but all active workers must pass the actual Kanban task ID.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile

TASK_ID_PATTERN = re.compile(r"t_[A-Za-z0-9_-]{1,96}\Z")


def handoff_path(root: Path, task_id: str | None = None) -> Path:
    """Resolve the git administrative directory correctly in linked worktrees."""
    if task_id is not None and not TASK_ID_PATTERN.fullmatch(task_id):
        raise ValueError("invalid Kanban task ID")
    name = (
        f"hermes/task-handoffs/{task_id}/current.json"
        if task_id else "hermes/review-handoff.json"
    )
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--git-path", name],
        text=True, capture_output=True, check=True,
    )
    path = Path(result.stdout.strip())
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def clear_handoff(root: Path, task_id: str | None = None) -> bool:
    try:
        handoff_path(root, task_id).unlink()
        return True
    except FileNotFoundError:
        return False


def load_handoff(root: Path, task_id: str | None = None) -> dict[str, object] | None:
    try:
        data = json.loads(handoff_path(root, task_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("status") != "valid":
        return None
    if task_id is not None and data.get("task_id") != task_id:
        return None
    if data.get("workspace") != str(root.resolve()):
        return None
    paths = data.get("effective_paths")
    fingerprint = data.get("effective_scope_sha256")
    if not isinstance(paths, list) or not all(isinstance(item, str) for item in paths):
        return None
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        return None
    return data


def save_handoff(
    root: Path, *, scope: list[str], effective_paths: list[str],
    fingerprint: str, task_id: str | None = None,
) -> Path:
    if not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise ValueError("invalid scope fingerprint")
    path = handoff_path(root, task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "schema": 2 if task_id else 1,
        "workspace": str(root.resolve()),
        "scope": scope,
        "effective_paths": effective_paths,
        "effective_scope_sha256": fingerprint,
        "status": "valid",
    }
    if task_id is not None:
        payload["task_id"] = task_id
    # Readers see either the last complete version or the next complete version.
    fd, temporary = tempfile.mkstemp(prefix=".handoff-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return path


def cleanup_completed_handoff(*, board_db: Path, workspace: Path, task_id: str) -> bool:
    """Remove only ephemeral handoff after authoritative Kanban DONE."""
    if not TASK_ID_PATTERN.fullmatch(task_id) or not workspace.is_dir():
        return False
    uri = f"file:{board_db.resolve().as_posix()}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True, timeout=1.0) as connection:
            row = connection.execute(
                "SELECT status, workspace_path FROM tasks WHERE id = ?", (task_id,),
            ).fetchone()
    except (OSError, sqlite3.Error):
        return False
    if row is None or str(row[0] or "").lower() not in {"done", "completed"}:
        return False
    if not row[1] or Path(str(row[1])).resolve() != workspace.resolve():
        return False
    try:
        return clear_handoff(workspace, task_id)
    except (OSError, subprocess.CalledProcessError, ValueError):
        return False
