#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from cleanup_lib import CleanupError, emit, inspect_cleanup
from worktree_only import try_inspect_base_worktree


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Read-only preflight for selected merged Git worktree cleanup")
    value.add_argument("--workspace", required=True)
    value.add_argument("--remote", default="origin")
    value.add_argument("--base-branch")
    return value


def add_process_safe_directory(path: str | Path) -> None:
    """Trust only this process' selected worktree; never mutate global Git config."""
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
    add_process_safe_directory(args.workspace)
    try:
        worktree_only = try_inspect_base_worktree(
            args.workspace,
            remote=args.remote,
            explicit_base=args.base_branch,
        )
        if worktree_only is not None:
            tracked_allowed = worktree_only.tracked_previous_cleanup_allowed
            scope = "worktree-and-tracked-branch" if tracked_allowed else "worktree-only"
            emit("STATUS", "ready")
            emit("CLEANUP_SCOPE", scope)
            emit("BRANCH_CLEANUP_ALLOWED", "false")
            emit("TRACKED_BRANCH_CLEANUP_ALLOWED", str(tracked_allowed).lower())
            emit("REPO_ROOT", worktree_only.repo_root)
            emit("PRIMARY_WORKTREE", worktree_only.main_worktree)
            emit("WORKTREE", worktree_only.worktree)
            emit("WORKTREE_NAME", worktree_only.worktree.name)
            emit("BRANCH", worktree_only.branch)
            emit("HEAD_SHA", worktree_only.head_sha)
            emit("BASE_BRANCH", worktree_only.base_branch)
            emit("BASE_REF", worktree_only.base_ref)
            emit("BASE_SHA", worktree_only.base_sha)
            emit("REMOTE", worktree_only.remote)
            emit("REMOTE_URL", worktree_only.remote_url)
            emit("REMOTE_BRANCH", f"{worktree_only.remote}/{worktree_only.branch}")
            emit("REMOTE_BRANCH_EXISTS", str(bool(worktree_only.remote_branch_sha)).lower())
            emit("REMOTE_BRANCH_SHA", worktree_only.remote_branch_sha)
            emit("GITHUB_STATUS", worktree_only.github_status)
            emit("MERGE_EVIDENCE", "base-branch-worktree")
            emit("PR_NUMBER", "")
            emit("PR_URL", "")
            emit("PR_MERGED_AT", "")
            emit("REMOTE_DELETE_AVAILABLE", "false")
            emit("TRACKED_PREVIOUS_BRANCH", worktree_only.tracked_previous_branch)
            emit("TRACKED_PREVIOUS_HEAD_SHA", worktree_only.tracked_previous_head_sha)
            emit(
                "TRACKED_PREVIOUS_REMOTE_BRANCH",
                f"{worktree_only.remote}/{worktree_only.tracked_previous_branch}"
                if worktree_only.tracked_previous_branch else "",
            )
            emit("TRACKED_PREVIOUS_REMOTE_EXISTS", str(bool(worktree_only.tracked_previous_remote_sha)).lower())
            emit("TRACKED_PREVIOUS_REMOTE_SHA", worktree_only.tracked_previous_remote_sha)
            emit("TRACKED_PREVIOUS_MERGE_EVIDENCE", worktree_only.tracked_previous_merge_evidence)
            emit("TRACKED_PREVIOUS_PR_NUMBER", worktree_only.tracked_previous_pr.number if worktree_only.tracked_previous_pr else "")
            emit("TRACKED_PREVIOUS_PR_URL", worktree_only.tracked_previous_pr.url if worktree_only.tracked_previous_pr else "")
            emit("TRACKED_PREVIOUS_REMOTE_DELETE_AVAILABLE", str(worktree_only.tracked_previous_remote_delete_available).lower())
            emit("TRACKED_PREVIOUS_REASON", worktree_only.tracked_previous_reason)
            emit("TRACKED_REFLOG_MESSAGE", worktree_only.tracked_reflog_message)
            emit("CLEANUP_FINGERPRINT", worktree_only.fingerprint)
            return 0

        state = inspect_cleanup(
            args.workspace,
            remote=args.remote,
            explicit_base=args.base_branch,
        )
        emit("STATUS", "ready")
        emit("CLEANUP_SCOPE", "worktree-and-branch")
        emit("BRANCH_CLEANUP_ALLOWED", "true")
        emit("TRACKED_BRANCH_CLEANUP_ALLOWED", "false")
        emit("REPO_ROOT", state.repo_root)
        emit("COMMON_GIT_DIR", state.common_git_dir)
        emit("PRIMARY_WORKTREE", state.main_worktree)
        emit("WORKTREE", state.worktree)
        emit("WORKTREE_NAME", state.worktree.name)
        emit("BRANCH", state.branch)
        emit("HEAD_SHA", state.head_sha)
        emit("BASE_BRANCH", state.base_branch)
        emit("BASE_REF", state.base_ref)
        emit("BASE_SHA", state.base_sha)
        emit("REMOTE", state.remote)
        emit("REMOTE_URL", state.remote_url)
        emit("REMOTE_BRANCH", f"{state.remote}/{state.branch}")
        emit("REMOTE_BRANCH_EXISTS", str(bool(state.remote_branch_sha)).lower())
        emit("REMOTE_BRANCH_SHA", state.remote_branch_sha)
        emit("GITHUB_STATUS", state.github_status)
        emit("MERGE_EVIDENCE", state.merge_evidence)
        emit("PR_NUMBER", state.pr.number if state.pr else "")
        emit("PR_URL", state.pr.url if state.pr else "")
        emit("PR_MERGED_AT", state.pr.merged_at if state.pr else "")
        emit("REMOTE_DELETE_AVAILABLE", str(state.remote_delete_available).lower())
        emit("TRACKED_PREVIOUS_BRANCH", "")
        emit("CLEANUP_FINGERPRINT", state.fingerprint)
        return 0
    except CleanupError as exc:
        print(f"STATUS=blocked\nERROR={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
