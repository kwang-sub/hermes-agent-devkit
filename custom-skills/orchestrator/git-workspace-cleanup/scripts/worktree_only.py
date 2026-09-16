#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from cleanup_lib import (
    CleanupError,
    current_branch,
    head_sha,
    parse_worktrees,
    remote_branch_sha,
    remote_url,
    repo_root,
    resolve_remote_head,
    resolve_workspace,
    status_bytes,
    worktree_snapshot,
)


@dataclass(frozen=True)
class WorktreeOnlyInspection:
    repo_root: Path
    main_worktree: Path
    worktree: Path
    branch: str
    head_sha: str
    base_branch: str
    remote: str
    remote_url: str
    remote_branch_sha: str | None
    worktree_snapshot: str
    status_snapshot: bytes
    fingerprint: str


def _fingerprint(
    *,
    worktree: Path,
    branch: str,
    head: str,
    base: str,
    remote: str,
    remote_url_value: str,
    remote_sha: str | None,
    worktrees: str,
    status: bytes,
) -> str:
    digest = hashlib.sha256()
    payload = {
        "version": "dev-workspace-cleanup-worktree-only-v1",
        "worktree": str(worktree),
        "branch": branch,
        "head": head,
        "base": base,
        "remote": remote,
        "remote_url": remote_url_value,
        "remote_sha": remote_sha or "",
        "worktrees": worktrees,
    }
    digest.update(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    digest.update(b"\0")
    digest.update(status)
    return digest.hexdigest()


def try_inspect_base_worktree(
    workspace_value: str,
    *,
    remote: str = "origin",
    explicit_base: str | None = None,
) -> WorktreeOnlyInspection | None:
    workspace = resolve_workspace(workspace_value)
    root = repo_root(workspace)
    branch = current_branch(root)
    explicit = explicit_base.strip() if explicit_base and explicit_base.strip() else None
    base = explicit or resolve_remote_head(root, remote) or ""
    if not base or branch != base:
        return None

    raw_status = status_bytes(root)
    if raw_status:
        raise CleanupError(
            "worktree contains modified or untracked files; cleanup is blocked"
        )

    wt_raw = worktree_snapshot(root)
    worktrees = parse_worktrees(wt_raw)
    main = worktrees[0].path
    target_matches = [entry for entry in worktrees if entry.path == root]
    if len(target_matches) != 1:
        raise CleanupError(f"target worktree is not uniquely registered: {root}")
    target = target_matches[0]
    if target.path == main:
        raise CleanupError("the primary worktree cannot be removed by dev-workspace-cleanup")
    if target.detached:
        raise CleanupError("detached HEAD worktree cannot be cleaned automatically")
    if target.locked:
        raise CleanupError("target worktree is locked; unlock it explicitly before cleanup")
    if target.prunable:
        raise CleanupError("target worktree is marked prunable; repair/prune metadata before cleanup")

    url = remote_url(root, remote)
    remote_sha = remote_branch_sha(root, remote, branch)
    head = head_sha(root)
    fingerprint = _fingerprint(
        worktree=target.path,
        branch=branch,
        head=head,
        base=base,
        remote=remote,
        remote_url_value=url,
        remote_sha=remote_sha,
        worktrees=wt_raw,
        status=raw_status,
    )

    return WorktreeOnlyInspection(
        repo_root=root,
        main_worktree=main,
        worktree=target.path,
        branch=branch,
        head_sha=head,
        base_branch=base,
        remote=remote,
        remote_url=url,
        remote_branch_sha=remote_sha,
        worktree_snapshot=wt_raw,
        status_snapshot=raw_status,
        fingerprint=fingerprint,
    )
