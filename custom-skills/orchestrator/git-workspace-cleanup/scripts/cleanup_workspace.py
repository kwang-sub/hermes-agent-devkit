#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from cleanup_lib import (
    CleanupError,
    emit,
    ensure_gh_config_env,
    github_slug,
    inspect_cleanup,
    parse_worktrees,
    push_delete_command,
    remote_branch_sha,
    run,
    worktree_snapshot,
)
from worktree_only import try_inspect_base_worktree


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Remove an approved merged linked worktree safely")
    value.add_argument("--workspace", required=True)
    value.add_argument("--remote", default="origin")
    value.add_argument("--base-branch")
    value.add_argument("--fingerprint", required=True)
    value.add_argument("--delete-tracked-branch", action="store_true")
    value.add_argument("--delete-remote", action="store_true")
    return value


def add_process_safe_directory(path: str | Path) -> None:
    """Trust only this process' selected paths; never mutate global Git config."""
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


def local_branch_sha(root: Path, branch: str) -> str | None:
    result = run(["git", "rev-parse", "--verify", f"refs/heads/{branch}"], cwd=root, check=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def remove_worktree(
    main: Path,
    worktree: Path,
    *,
    allow_eol_only_force: bool = False,
) -> None:
    command = ["git", "worktree", "remove"]
    if allow_eol_only_force:
        command.append("--force")
    command.append(str(worktree))
    removed = run(command, cwd=main, check=False)
    if removed.returncode != 0:
        detail = (removed.stdout + "\n" + removed.stderr).strip()
        raise CleanupError("git worktree remove failed without force; no branch refs were deleted\n" + detail)
    remaining_paths = {entry.path for entry in parse_worktrees(worktree_snapshot(main))}
    if worktree in remaining_paths:
        raise CleanupError("worktree removal returned success but the worktree is still registered")


def push_delete_named_branch(*, remote_url: str, github_status: str, remote: str, branch: str) -> list[str]:
    if (remote_url.startswith("https://") or remote_url.startswith("http://")) and github_slug(remote_url):
        if github_status != "ready":
            raise CleanupError("GitHub authentication is required to delete the HTTPS remote branch")
        ensure_gh_config_env()
        return [
            "git", "-c", "credential.helper=", "-c", "credential.helper=!gh auth git-credential",
            "push", remote, "--delete", branch,
        ]
    return ["git", "push", remote, "--delete", branch]


def emit_base_result(state, *, worktree_removed: bool, tracked_local, tracked_remote) -> None:
    emit("STATUS", "cleaned")
    emit(
        "CLEANUP_SCOPE",
        "worktree-and-tracked-branch" if tracked_local is True else "worktree-only",
    )
    emit("WORKTREE", state.worktree)
    emit("WORKTREE_NAME", state.worktree.name)
    emit("BRANCH", state.branch)
    emit("BASE_BRANCH", state.base_branch)
    emit("MERGE_EVIDENCE", "base-branch-worktree")
    emit("WORKTREE_REMOVED", str(worktree_removed).lower())
    emit("LOCAL_BRANCH_REMOVED", "preserved-base")
    emit("REMOTE_BRANCH_REMOVED", "preserved-base")
    emit("TRACKED_PREVIOUS_BRANCH", state.tracked_previous_branch)
    emit("TRACKED_LOCAL_BRANCH_REMOVED", str(tracked_local).lower() if isinstance(tracked_local, bool) else tracked_local)
    emit("TRACKED_REMOTE_BRANCH_REMOVED", str(tracked_remote).lower() if isinstance(tracked_remote, bool) else tracked_remote)


def main() -> int:
    args = parser().parse_args()
    worktree_removed = False
    local_branch_removed: bool | str = False
    remote_branch_removed: bool | str = False
    add_process_safe_directory(args.workspace)
    try:
        worktree_only = try_inspect_base_worktree(
            args.workspace,
            remote=args.remote,
            explicit_base=args.base_branch,
        )
        if worktree_only is not None:
            if worktree_only.fingerprint != args.fingerprint:
                raise CleanupError("cleanup fingerprint changed after approval; regenerate cleanup preview and approve again")
            if args.delete_remote and not args.delete_tracked_branch:
                raise CleanupError("remote deletion requires explicit --delete-tracked-branch approval in base-worktree mode")
            if args.delete_tracked_branch and not worktree_only.tracked_previous_cleanup_allowed:
                raise CleanupError("tracked previous branch is not proven safe for deletion")
            if (
                args.delete_remote
                and worktree_only.tracked_previous_remote_sha
                and not worktree_only.tracked_previous_remote_delete_available
            ):
                raise CleanupError("tracked previous remote branch deletion is not available or its SHA differs")

            main_worktree = worktree_only.main_worktree
            add_process_safe_directory(main_worktree)
            os.chdir(main_worktree)
            remove_worktree(
                main_worktree,
                worktree_only.worktree,
                allow_eol_only_force=worktree_only.eol_only_force_allowed,
            )
            worktree_removed = True

            tracked_local_removed: bool | str = "skipped"
            tracked_remote_removed: bool | str = "skipped"
            tracked_branch = worktree_only.tracked_previous_branch
            tracked_head = worktree_only.tracked_previous_head_sha

            if args.delete_tracked_branch and tracked_branch and tracked_head:
                current_local = local_branch_sha(main_worktree, tracked_branch)
                if current_local is None:
                    tracked_local_removed = True
                elif current_local != tracked_head:
                    emit("STATUS", "partial")
                    emit("WORKTREE_REMOVED", "true")
                    emit("TRACKED_PREVIOUS_BRANCH", tracked_branch)
                    emit("TRACKED_LOCAL_BRANCH_REMOVED", "false")
                    print("ERROR=tracked local branch moved after cleanup approval; branch ref was preserved", file=sys.stderr)
                    return 3
                else:
                    deleted = run(
                        ["git", "update-ref", "-d", f"refs/heads/{tracked_branch}", tracked_head],
                        cwd=main_worktree,
                        check=False,
                    )
                    if deleted.returncode != 0:
                        detail = (deleted.stdout + "\n" + deleted.stderr).strip()
                        emit("STATUS", "partial")
                        emit("WORKTREE_REMOVED", "true")
                        emit("TRACKED_PREVIOUS_BRANCH", tracked_branch)
                        emit("TRACKED_LOCAL_BRANCH_REMOVED", "false")
                        print(f"ERROR=tracked local branch ref deletion failed\n{detail}", file=sys.stderr)
                        return 3
                    tracked_local_removed = True

            run(["git", "worktree", "prune"], cwd=main_worktree)

            if args.delete_remote and tracked_branch and worktree_only.tracked_previous_remote_sha:
                current_remote = remote_branch_sha(main_worktree, worktree_only.remote, tracked_branch)
                if current_remote is None:
                    tracked_remote_removed = True
                elif current_remote != worktree_only.tracked_previous_remote_sha:
                    emit("STATUS", "partial")
                    emit("WORKTREE_REMOVED", "true")
                    emit("TRACKED_PREVIOUS_BRANCH", tracked_branch)
                    emit("TRACKED_LOCAL_BRANCH_REMOVED", "true")
                    emit("TRACKED_REMOTE_BRANCH_REMOVED", "false")
                    print("ERROR=tracked remote branch moved after cleanup approval; remote branch was preserved", file=sys.stderr)
                    return 4
                else:
                    pushed = run(
                        push_delete_named_branch(
                            remote_url=worktree_only.remote_url,
                            github_status=worktree_only.github_status,
                            remote=worktree_only.remote,
                            branch=tracked_branch,
                        ),
                        cwd=main_worktree,
                        check=False,
                    )
                    if pushed.returncode != 0:
                        detail = (pushed.stdout + "\n" + pushed.stderr).strip()
                        emit("STATUS", "partial")
                        emit("WORKTREE_REMOVED", "true")
                        emit("TRACKED_PREVIOUS_BRANCH", tracked_branch)
                        emit("TRACKED_LOCAL_BRANCH_REMOVED", "true")
                        emit("TRACKED_REMOTE_BRANCH_REMOVED", "false")
                        print(f"ERROR=tracked remote branch deletion failed\n{detail}", file=sys.stderr)
                        return 4
                    tracked_remote_removed = True
            elif args.delete_remote:
                tracked_remote_removed = True

            emit_base_result(
                worktree_only,
                worktree_removed=True,
                tracked_local=tracked_local_removed,
                tracked_remote=tracked_remote_removed,
            )
            return 0

        if args.delete_tracked_branch:
            raise CleanupError("--delete-tracked-branch is valid only when a base-branch worktree has a proven previous branch")

        state = inspect_cleanup(args.workspace, remote=args.remote, explicit_base=args.base_branch)
        if state.fingerprint != args.fingerprint:
            raise CleanupError("cleanup fingerprint changed after approval; regenerate cleanup preview and approve again")
        if args.delete_remote and state.remote_branch_sha and not state.remote_delete_available:
            raise CleanupError("remote branch deletion is not available with the current authentication/remote")

        main_worktree = state.main_worktree
        add_process_safe_directory(main_worktree)
        os.chdir(main_worktree)
        remove_worktree(
            main_worktree,
            state.worktree,
            allow_eol_only_force=state.eol_only_force_allowed,
        )
        worktree_removed = True

        current_local = local_branch_sha(main_worktree, state.branch)
        if current_local is None:
            local_branch_removed = True
        elif current_local != state.head_sha:
            emit("STATUS", "partial")
            emit("WORKTREE_REMOVED", "true")
            emit("LOCAL_BRANCH_REMOVED", "false")
            print("ERROR=local branch moved after cleanup approval; branch ref was preserved", file=sys.stderr)
            return 3
        else:
            deleted = run(
                ["git", "update-ref", "-d", f"refs/heads/{state.branch}", state.head_sha],
                cwd=main_worktree,
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

        run(["git", "worktree", "prune"], cwd=main_worktree)

        if args.delete_remote and state.remote_branch_sha:
            current_remote = remote_branch_sha(main_worktree, state.remote, state.branch)
            if current_remote is None:
                remote_branch_removed = True
            elif current_remote != state.remote_branch_sha:
                emit("STATUS", "partial")
                emit("WORKTREE_REMOVED", "true")
                emit("LOCAL_BRANCH_REMOVED", "true")
                emit("REMOTE_BRANCH_REMOVED", "false")
                print("ERROR=remote branch moved after cleanup approval; remote branch was preserved", file=sys.stderr)
                return 4
            else:
                pushed = run(push_delete_command(state), cwd=main_worktree, check=False)
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
        emit("CLEANUP_SCOPE", "worktree-and-branch")
        emit("WORKTREE", state.worktree)
        emit("WORKTREE_NAME", state.worktree.name)
        emit("BRANCH", state.branch)
        emit("BASE_BRANCH", state.base_branch)
        emit("MERGE_EVIDENCE", state.merge_evidence)
        emit("WORKTREE_REMOVED", str(worktree_removed).lower())
        emit("LOCAL_BRANCH_REMOVED", str(local_branch_removed).lower())
        emit("REMOTE_BRANCH_REMOVED", str(remote_branch_removed).lower() if args.delete_remote else "skipped")
        return 0
    except CleanupError as exc:
        emit("STATUS", "blocked")
        emit("WORKTREE_REMOVED", str(worktree_removed).lower())
        emit("LOCAL_BRANCH_REMOVED", str(local_branch_removed).lower() if isinstance(local_branch_removed, bool) else local_branch_removed)
        emit("REMOTE_BRANCH_REMOVED", str(remote_branch_removed).lower() if isinstance(remote_branch_removed, bool) else remote_branch_removed)
        print(f"ERROR={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
