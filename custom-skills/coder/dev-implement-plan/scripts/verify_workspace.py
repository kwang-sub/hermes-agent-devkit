#!/usr/bin/env python3
from __future__ import annotations
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import time


class GuardError(RuntimeError):
    pass


PHASE_TIMINGS: list[tuple[str, float]] = []


def run(cmd: list[str], check=True, phase: str | None = None):
    started = time.monotonic()
    p = subprocess.run(cmd, text=True, capture_output=True)
    duration = time.monotonic() - started
    if phase:
        PHASE_TIMINGS.append((phase, duration))
    if check and p.returncode != 0:
        raise GuardError((p.stderr or p.stdout).strip() or "command failed")
    return p


def ensure_safe_directory(path: Path) -> None:
    resolved = str(path.resolve())
    current = run(
        ["git", "config", "--global", "--get-all", "safe.directory"],
        check=False,
        phase="SAFE_DIRECTORY_READ",
    )
    configured = {line.strip() for line in current.stdout.splitlines() if line.strip()}
    if resolved not in configured:
        added = run(
            ["git", "config", "--global", "--add", "safe.directory", resolved],
            check=False,
            phase="SAFE_DIRECTORY_WRITE",
        )
        if added.returncode != 0:
            raise GuardError((added.stderr or added.stdout).strip() or f"cannot register safe.directory: {resolved}")


def resolve_base_sha(root: Path, value: str) -> str:
    if not re.fullmatch(r"[0-9a-fA-F]{40}", value):
        raise GuardError("base SHA must be a full 40-character hexadecimal commit ID")
    resolved = run(
        ["git", "-C", str(root), "rev-parse", "--verify", f"{value}^{{commit}}"],
        check=False,
        phase="BASE_SHA_RESOLVE",
    )
    if resolved.returncode != 0:
        raise GuardError(f"base SHA does not resolve to a commit: {value}")
    return resolved.stdout.strip()


def _clean(value: str | None) -> str:
    return str(value or "").strip()


def verify_kanban_context(
    *,
    task_id: str,
    board: str,
    workspace: Path,
    expected_profile: str,
) -> tuple[str, str | None]:
    """Fail closed when a Coder run did not come from the patched dispatcher.

    A server/container restart may legitimately lose the prior chat session, but
    it must never lose task identity. The dispatcher rebuilds the Kanban worker
    environment for every NEW or RESUME spawn. A manually resumed shell or any
    alternate path missing that environment must not continue implementation.
    """
    expected = {
        "HERMES_KANBAN_TASK": task_id,
        "HERMES_KANBAN_BOARD": board,
        "HERMES_KANBAN_WORKSPACE": str(workspace.resolve()),
        "HERMES_PROFILE": expected_profile,
        "HERMES_SESSION_SOURCE": "kanban",
        "HERMES_KANBAN_CONTEXT_VERSION": "1",
    }
    problems: list[str] = []
    for key, wanted in expected.items():
        actual = _clean(os.environ.get(key))
        if key == "HERMES_KANBAN_WORKSPACE" and actual:
            try:
                actual = str(Path(actual).resolve())
            except OSError:
                pass
        if actual != wanted:
            problems.append(f"{key}: expected={wanted!r}, actual={actual!r}")

    kanban_db = _clean(os.environ.get("HERMES_KANBAN_DB"))
    if not kanban_db:
        problems.append("HERMES_KANBAN_DB: missing")

    if problems:
        raise GuardError(
            "Kanban worker context is missing or mismatched. "
            "Do not continue from a manual `hermes --resume`/direct chat process; "
            "requeue the same card so the dispatcher creates a fresh worker context. "
            + " | ".join(problems)
        )

    return _clean(os.environ.get("HERMES_KANBAN_SESSION_MODE")) or "NEW", (
        _clean(os.environ.get("HERMES_KANBAN_AFFINITY_SESSION_ID")) or None
    )


def emit_timings(total_started: float) -> None:
    for name, duration in PHASE_TIMINGS:
        print(f"WORKSPACE_VERIFY_PHASE_{name}_SECONDS={duration:.3f}")
    print(f"WORKSPACE_VERIFY_TOTAL_SECONDS={time.monotonic() - total_started:.3f}")


def main():
    total_started = time.monotonic()
    ap = argparse.ArgumentParser()
    ap.add_argument("--task-key", required=True)
    ap.add_argument("--expected-branch", required=True)
    ap.add_argument("--base-sha", required=True)
    ap.add_argument("--workspace")
    ap.add_argument("--expected-workspace")
    ap.add_argument("--require-kanban-context", action="store_true")
    ap.add_argument("--kanban-task-id")
    ap.add_argument("--kanban-board")
    ap.add_argument("--expected-profile", default="coder")
    args = ap.parse_args()

    resolve_started = time.monotonic()
    workspace = Path(args.workspace or ".").resolve()
    PHASE_TIMINGS.append(("PATH_RESOLVE", time.monotonic() - resolve_started))

    session_mode = "-"
    affinity_session_id: str | None = None
    if args.require_kanban_context:
        if not args.kanban_task_id or not args.kanban_board:
            raise GuardError(
                "--require-kanban-context requires --kanban-task-id and --kanban-board"
            )
        context_started = time.monotonic()
        session_mode, affinity_session_id = verify_kanban_context(
            task_id=args.kanban_task_id,
            board=args.kanban_board,
            workspace=workspace,
            expected_profile=args.expected_profile,
        )
        PHASE_TIMINGS.append(("KANBAN_CONTEXT", time.monotonic() - context_started))

    ensure_safe_directory(workspace)
    top = run(
        ["git", "-C", str(workspace), "rev-parse", "--show-toplevel"],
        phase="REPO_ROOT",
    ).stdout.strip()
    root = Path(top).resolve()
    if root != workspace:
        raise GuardError(f"workspace must be the Git repository root: workspace={workspace}, root={root}")

    if args.expected_workspace and root != Path(args.expected_workspace).resolve():
        raise GuardError(
            f"workspace mismatch: expected={Path(args.expected_workspace).resolve()}, actual={root}"
        )

    branch = run(
        ["git", "-C", str(root), "branch", "--show-current"],
        phase="BRANCH",
    ).stdout.strip()
    if branch != args.expected_branch:
        raise GuardError(f"branch mismatch: expected={args.expected_branch}, actual={branch}")

    inside = run(
        ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
        phase="WORKTREE_CHECK",
    ).stdout.strip()
    if inside != "true":
        raise GuardError("not inside Git workspace")

    base_sha = resolve_base_sha(root, args.base_sha)
    ancestor = run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", base_sha, "HEAD"],
        check=False,
        phase="ANCESTOR_CHECK",
    )
    if ancestor.returncode == 1:
        raise GuardError(f"base SHA is not an ancestor of HEAD: {base_sha}")
    if ancestor.returncode != 0:
        raise GuardError((ancestor.stderr or ancestor.stdout).strip() or "cannot compare base SHA to HEAD")

    print(f"WORKSPACE={root}")
    print(f"BRANCH={branch}")
    print(f"BASE_SHA={base_sha}")
    print(f"TASK_KEY={args.task_key}")
    if args.require_kanban_context:
        print("KANBAN_CONTEXT=valid")
        print(f"KANBAN_TASK_ID={args.kanban_task_id}")
        print(f"KANBAN_BOARD={args.kanban_board}")
        print(f"KANBAN_PROFILE={args.expected_profile}")
        print(f"KANBAN_SESSION_MODE={session_mode}")
        print(f"KANBAN_AFFINITY_SESSION_ID={affinity_session_id or '-'}")
    print("GIT_SAFE_DIRECTORY=true")
    print("GIT_WORKSPACE=true")
    emit_timings(total_started)
    print("STATUS=valid")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GuardError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
