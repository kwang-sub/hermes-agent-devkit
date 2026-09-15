#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from cleanup_lib import (
    CleanupError,
    emit,
    parse_worktrees,
    remote_branch_sha,
    remote_url,
    repo_root,
    resolve_workspace,
    status_bytes,
    worktree_snapshot,
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="List Git worktrees for interactive cleanup selection")
    value.add_argument("--repo", required=True, help="Primary repository or any registered worktree path")
    value.add_argument("--remote", default="origin")
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        start = resolve_workspace(args.repo)
        root = repo_root(start)
        entries = parse_worktrees(worktree_snapshot(root))
        primary = entries[0].path

        remote_ready = True
        try:
            remote_url(root, args.remote)
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
                "selectable": (not is_primary and bool(entry.branch) and not entry.detached),
            }
            rows.append(row)

        linked = [row for row in rows if not bool(row["primary"])]
        selectable = [row for row in linked if bool(row["selectable"])]

        emit("STATUS", "ready")
        emit("REPO_ROOT", root)
        emit("PRIMARY_WORKTREE", primary)
        emit("REMOTE", args.remote)
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
