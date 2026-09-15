#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from cleanup_lib import CleanupError, emit, inspect_cleanup


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Read-only preflight for merged Git worktree cleanup")
    value.add_argument("--workspace", required=True)
    value.add_argument("--remote", default="origin")
    value.add_argument("--base-branch")
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        state = inspect_cleanup(
            args.workspace,
            remote=args.remote,
            explicit_base=args.base_branch,
        )
        emit("STATUS", "ready")
        emit("REPO_ROOT", state.repo_root)
        emit("COMMON_GIT_DIR", state.common_git_dir)
        emit("MAIN_WORKTREE", state.main_worktree)
        emit("WORKTREE", state.worktree)
        emit("BRANCH", state.branch)
        emit("HEAD_SHA", state.head_sha)
        emit("BASE_BRANCH", state.base_branch)
        emit("BASE_REF", state.base_ref)
        emit("BASE_SHA", state.base_sha)
        emit("REMOTE", state.remote)
        emit("REMOTE_URL", state.remote_url)
        emit("REMOTE_BRANCH_EXISTS", str(bool(state.remote_branch_sha)).lower())
        emit("REMOTE_BRANCH_SHA", state.remote_branch_sha)
        emit("GITHUB_STATUS", state.github_status)
        emit("MERGE_EVIDENCE", state.merge_evidence)
        emit("PR_NUMBER", state.pr.number if state.pr else "")
        emit("PR_URL", state.pr.url if state.pr else "")
        emit("PR_MERGED_AT", state.pr.merged_at if state.pr else "")
        emit("REMOTE_DELETE_AVAILABLE", str(state.remote_delete_available).lower())
        emit("CLEANUP_FINGERPRINT", state.fingerprint)
        return 0
    except CleanupError as exc:
        print(f"STATUS=blocked\nERROR={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
