#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from cleanup_lib import (
    CleanupError,
    emit,
    inspect_cleanup,
    parse_worktrees,
    push_delete_command,
    remote_branch_sha,
    run,
    worktree_snapshot,
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Remove an approved merged linked worktree safely")
    value.add_argument("--workspace", required=True)
    value.add_argument("--remote", default="origin")
    value.add_argument("--base-branch")
    value.add_argument("--fingerprint", required=True)
    value.add_argument("--delete-remote", action="store_true")
    return value


def local_branch_sha(root: Path, branch: str) -> str | None:
    result = run(["git", "rev-parse", "--verify", f"refs/heads/{branch}"], cwd=root, check=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def main() -> int:
    args = parser().parse_args()
    worktree_removed = False
    local_branch_removed = False
    remote_branch_removed = False
    try:
        state = inspect_cleanup(
            args.workspace,
            remote=args.remote,
            explicit_base=args.base_branch,
        )
        if state.fingerprint != args.fingerprint:
            raise CleanupError(
                "cleanup fingerprint changed after approval; regenerate cleanup preview and approve again"
            )
        if args.delete_remote and state.remote_branch_sha and not state.remote_delete_available:
            raise CleanupError("remote branch deletion is not available with the current authentication/remote")

        main = state.main_worktree
        os.chdir(main)

        removed = run(
            ["git", "worktree", "remove", str(state.worktree)],
            cwd=main,
            check=False,
        )
        if removed.returncode != 0:
            detail = (removed.stdout + "\n" + removed.stderr).strip()
            raise CleanupError(
                "git worktree remove failed without force; no branch refs were deleted\n" + detail
            )
        worktree_removed = True

        remaining_paths = {entry.path for entry in parse_worktrees(worktree_snapshot(main))}
        if state.worktree in remaining_paths:
            emit("STATUS", "partial")
            emit("WORKTREE_REMOVED", "false")
            print("ERROR=worktree removal returned success but the worktree is still registered", file=sys.stderr)
            return 3

        current_local = local_branch_sha(main, state.branch)
        if current_local is None:
            local_branch_removed = True
        elif current_local != state.head_sha:
            emit("STATUS", "partial")
            emit("WORKTREE_REMOVED", "true")
            emit("LOCAL_BRANCH_REMOVED", "false")
            print(
                "ERROR=local branch moved after cleanup approval; branch ref was preserved",
                file=sys.stderr,
            )
            return 3
        else:
            deleted = run(
                ["git", "update-ref", "-d", f"refs/heads/{state.branch}", state.head_sha],
                cwd=main,
                check=False,
            )
            if deleted.returncode != 0:
                detail = (deleted.stdout + "\n" + deleted.stderr).strip()
                emit("STATUS", "partial")
                emit("WORKTREE_REMOVED", "true")
                emit("LOCAL_BRANCH_REMOVED", "false")
                print(f"ERROR=local branch ref deletion failed\n{detail}", file=sys.stderr)
                return 3
            local_branch_removed = True

        run(["git", "worktree", "prune"], cwd=main)

        if args.delete_remote and state.remote_branch_sha:
            current_remote = remote_branch_sha(main, state.remote, state.branch)
            if current_remote is None:
                remote_branch_removed = True
            elif current_remote != state.remote_branch_sha:
                emit("STATUS", "partial")
                emit("WORKTREE_REMOVED", "true")
                emit("LOCAL_BRANCH_REMOVED", "true")
                emit("REMOTE_BRANCH_REMOVED", "false")
                print(
                    "ERROR=remote branch moved after cleanup approval; remote branch was preserved",
                    file=sys.stderr,
                )
                return 4
            else:
                pushed = run(push_delete_command(state), cwd=main, check=False)
                if pushed.returncode != 0:
                    detail = (pushed.stdout + "\n" + pushed.stderr).strip()
                    emit("STATUS", "partial")
                    emit("WORKTREE_REMOVED", "true")
                    emit("LOCAL_BRANCH_REMOVED", "true")
                    emit("REMOTE_BRANCH_REMOVED", "false")
                    print(f"ERROR=remote branch deletion failed\n{detail}", file=sys.stderr)
                    return 4
                remote_branch_removed = True

        emit("STATUS", "cleaned")
        emit("WORKTREE", state.worktree)
        emit("WORKTREE_NAME", state.worktree.name)
        emit("BRANCH", state.branch)
        emit("BASE_BRANCH", state.base_branch)
        emit("MERGE_EVIDENCE", state.merge_evidence)
        emit("WORKTREE_REMOVED", str(worktree_removed).lower())
        emit("LOCAL_BRANCH_REMOVED", str(local_branch_removed).lower())
        if args.delete_remote:
            emit("REMOTE_BRANCH_REMOVED", str(remote_branch_removed).lower())
        else:
            emit("REMOTE_BRANCH_REMOVED", "skipped")
        return 0
    except CleanupError as exc:
        emit("STATUS", "blocked")
        emit("WORKTREE_REMOVED", str(worktree_removed).lower())
        emit("LOCAL_BRANCH_REMOVED", str(local_branch_removed).lower())
        emit("REMOTE_BRANCH_REMOVED", str(remote_branch_removed).lower())
        print(f"ERROR={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
