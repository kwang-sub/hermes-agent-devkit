#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from cleanup_lib import (
    CleanupError,
    emit,
    parse_worktrees,
    remote_branch_sha,
    remote_url,
    repo_root,
    resolve_remote_head,
    resolve_workspace,
    status_bytes,
    worktree_snapshot,
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="List Git worktrees for interactive cleanup selection")
    value.add_argument("--repo", required=True, help="Primary repository or any registered worktree path")
    value.add_argument("--remote", default="origin")
    return value


def add_process_safe_directory(path: str | Path) -> None:
    """Trust only this process' selected repository; never mutate global Git config."""
    resolved = str(Path(path).expanduser().resolve())
    count = int(os.environ.get("GIT_CONFIG_COUNT", "0") or "0")
    existing = {
        os.environ.get(f"GIT_CONFIG_VALUE_{index}")
        for index in range(count)
        if os.environ.get(f"GIT_CONFIG_KEY_{index}") == "safe.directory"
    }
    if resolved in existing:
        return
    os.environ[f"GIT_CONFIG_KEY_{count}"] = "safe.directory"
    os.environ[f"GIT_CONFIG_VALUE_{count}"] = resolved
    os.environ["GIT_CONFIG_COUNT"] = str(count + 1)


def main() -> int:
    args = parser().parse_args()
    add_process_safe_directory(args.repo)
    try:
        start = resolve_workspace(args.repo)
        root = repo_root(start)
        entries = parse_worktrees(worktree_snapshot(root))
        primary = entries[0].path

        remote_ready = True
        default_base = ""
        try:
            remote_url(root, args.remote)
            default_base = resolve_remote_head(root, args.remote) or ""
        except CleanupError:
            remote_ready = False

        rows: list[dict[str, object]] = []
        linked_index = 0
        for entry in entries:
            is_primary = entry.path == primary
            if not is_primary:
                linked_index += 1

            clean_state = "UNKNOWN"
            if entry.path.is_dir() and not entry.prunable:
                try:
                    add_process_safe_directory(entry.path)
                    clean_state = "CLEAN" if not status_bytes(entry.path) else "DIRTY"
                except CleanupError:
                    clean_state = "UNKNOWN"

            remote_sha = None
            remote_error = ""
            if remote_ready and entry.branch:
                try:
                    remote_sha = remote_branch_sha(root, args.remote, entry.branch)
                except CleanupError as exc:
                    remote_error = str(exc).splitlines()[0]

            base_branch_worktree = bool(entry.branch and default_base and entry.branch == default_base)
            cleanup_scope_hint = "worktree-only" if base_branch_worktree else "worktree-and-branch"
            row = {
                "index": linked_index if not is_primary else 0,
                "path": str(entry.path),
                "name": entry.path.name,
                "branch": entry.branch or "",
                "head": entry.head or "",
                "primary": is_primary,
                "clean": clean_state,
                "detached": entry.detached,
                "locked": entry.locked,
                "prunable": entry.prunable,
                "remote": args.remote,
                "remote_branch_exists": bool(remote_sha),
                "remote_branch_sha": remote_sha or "",
                "remote_error": remote_error,
                "base_branch_worktree": base_branch_worktree,
                "cleanup_scope_hint": cleanup_scope_hint,
                "selectable": (not is_primary and bool(entry.branch) and not entry.detached),
            }
            rows.append(row)

        linked = [row for row in rows if not bool(row["primary"])]
        selectable = [row for row in linked if bool(row["selectable"])]

        emit("STATUS", "ready")
        emit("REPO_ROOT", root)
        emit("PRIMARY_WORKTREE", primary)
        emit("REMOTE", args.remote)
        emit("DEFAULT_BASE_BRANCH", default_base)
        emit("TOTAL_WORKTREES", len(rows))
        emit("LINKED_WORKTREES", len(linked))
        emit("SELECTABLE_WORKTREES", len(selectable))
        for row in rows:
            slot = "PRIMARY" if bool(row["primary"]) else f"WORKTREE_{row['index']}"
            emit(f"{slot}_PATH", row["path"])
            emit(f"{slot}_NAME", row["name"])
            emit(f"{slot}_BRANCH", row["branch"])
            emit(f"{slot}_HEAD", row["head"])
            emit(f"{slot}_STATUS", row["clean"])
            emit(f"{slot}_REMOTE_EXISTS", str(bool(row["remote_branch_exists"])).lower())
            emit(f"{slot}_BASE_BRANCH_WORKTREE", str(bool(row["base_branch_worktree"])).lower())
            emit(f"{slot}_CLEANUP_SCOPE_HINT", row["cleanup_scope_hint"])
            emit(f"{slot}_LOCKED", str(bool(row["locked"])).lower())
            emit(f"{slot}_PRUNABLE", str(bool(row["prunable"])).lower())
            emit(f"{slot}_SELECTABLE", str(bool(row["selectable"])).lower())
        emit("WORKTREES_JSON", json.dumps(rows, ensure_ascii=False, separators=(",", ":")))
        return 0
    except CleanupError as exc:
        print(f"STATUS=blocked\nERROR={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
