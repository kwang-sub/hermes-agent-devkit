#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

DEFAULT_HERMES_CLI = "/opt/hermes/.venv/bin/hermes"
MANAGED_MARKER = "# managed-by: dev-project-bootstrap"
TERMINAL_STATUSES = {"done", "archived"}
ACTIVE_STATUSES = {"todo", "ready", "running", "blocked", "scheduled", "review"}


class FollowUpError(RuntimeError):
    pass


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, text=True, capture_output=True)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise FollowUpError(f"command failed ({result.returncode}): {' '.join(cmd)}\n{detail}")
    return result


def ensure_repo_root(path: Path) -> Path:
    result = run(["git", "-C", str(path), "rev-parse", "--show-toplevel"], check=False)
    if result.returncode != 0:
        raise FollowUpError(f"workspace is not a Git repository: {path}")
    root = Path(result.stdout.strip()).resolve()
    requested = path.resolve()
    if root != requested:
        raise FollowUpError(f"workspace must be the Git repository root: requested={requested}, root={root}")
    return root


def parse_board(metadata_file: Path) -> str:
    if not metadata_file.is_file():
        raise FollowUpError(f"project metadata is missing: {metadata_file}")
    text = metadata_file.read_text(encoding="utf-8")
    if MANAGED_MARKER not in text.splitlines()[:5]:
        raise FollowUpError(f"project metadata is not managed by dev-project-bootstrap: {metadata_file}")
    match = re.search(r"^kanban:\s*\n\s{2}board:\s*(.+?)\s*$", text, flags=re.MULTILINE)
    if not match:
        raise FollowUpError("kanban.board is missing from project metadata")
    return match.group(1).strip().strip("'\"")


def parse_task(payload: str) -> dict:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise FollowUpError(f"kanban show returned invalid JSON: {exc}") from exc
    if isinstance(data, dict) and isinstance(data.get("task"), dict):
        return data["task"]
    if isinstance(data, dict):
        return data
    raise FollowUpError("kanban show JSON did not contain a task object")


def direction_comment(instruction: str) -> str:
    normalized = " ".join(instruction.split())
    if not normalized:
        raise FollowUpError("instruction must not be blank")
    return (
        "USER_DIRECTION_CHANGE\n"
        f"- {normalized}\n\n"
        "Contract:\n"
        "- Treat this as the latest requirement for the active FAST task.\n"
        "- Re-evaluate the current implementation against this instruction.\n"
        "- Preserve unrelated/pre-existing user changes."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Route an interactive FAST follow-up to the existing Kanban task.")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--instruction", required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = ensure_repo_root(Path(args.workspace))
    board = parse_board(repo / ".hermes" / "project.yaml")
    hermes_cli = os.environ.get("HERMES_CLI", DEFAULT_HERMES_CLI)

    show = run([hermes_cli, "kanban", "--board", board, "show", args.task, "--json"])
    task = parse_task(show.stdout)
    status = str(task.get("status") or "").strip().lower()
    task_id = str(task.get("id") or args.task).strip()
    task_workspace = task.get("workspace_path")

    if task_workspace and Path(str(task_workspace)).resolve() != repo:
        raise FollowUpError(
            f"task workspace mismatch: task={Path(str(task_workspace)).resolve()}, requested={repo}"
        )
    if status in TERMINAL_STATUSES:
        raise FollowUpError(f"task {task_id} is terminal ({status}); create a new task instead of mutating it")
    if status not in ACTIVE_STATUSES:
        raise FollowUpError(f"task {task_id} is not an active FAST follow-up target: status={status or '<missing>'}")

    comment = direction_comment(args.instruction)
    print("=== Fast Flow Active Task Follow-up ===")
    print(f"BOARD={board}")
    print(f"TASK_ID={task_id}")
    print(f"TASK_STATUS={status}")
    print(f"WORKSPACE={repo}")

    if args.dry_run:
        print("--- COMMENT ---")
        print(comment)
        print("STATUS=dry-run")
        return 0

    if status == "review":
        run([
            hermes_cli, "kanban", "--board", board, "reopen-review", task_id,
            "--reason", "USER_DIRECTION_CHANGE: implementation requirements changed during review",
        ])
        print("REVIEW_REOPENED=true")

    run([
        hermes_cli, "kanban", "--board", board, "comment", task_id, comment,
        "--author", "coder-fast-flow-followup",
    ])
    print("STATUS=updated")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FollowUpError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
