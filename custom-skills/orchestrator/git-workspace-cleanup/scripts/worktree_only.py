#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

from cleanup_lib import (
    CleanupError,
    PullRequestEvidence,
    branch_is_ancestor,
    classify_worktree_status,
    current_branch,
    encode_status_rows,
    github_auth_status,
    github_pull_requests,
    github_slug,
    head_sha,
    parse_worktrees,
    remote_branch_sha,
    remote_delete_supported,
    remote_url,
    repo_root,
    resolve_base_ref,
    resolve_remote_head,
    resolve_workspace,
    run,
    select_merged_pr,
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
    base_ref: str | None
    base_sha: str | None
    remote: str
    remote_url: str
    remote_branch_sha: str | None
    github_status: str
    worktree_snapshot: str
    status_snapshot: bytes
    semantic_status_snapshot: bytes
    eol_only_paths: tuple[str, ...]
    eol_only_force_allowed: bool
    tracked_previous_branch: str | None
    tracked_previous_head_sha: str | None
    tracked_previous_remote_sha: str | None
    tracked_previous_merge_evidence: str
    tracked_previous_pr: PullRequestEvidence | None
    tracked_previous_cleanup_allowed: bool
    tracked_previous_remote_delete_available: bool
    tracked_previous_reason: str
    tracked_reflog_message: str
    fingerprint: str


def _local_branch_sha(root: Path, branch: str) -> str | None:
    result = run(["git", "rev-parse", "--verify", f"refs/heads/{branch}"], cwd=root, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def _previous_checkout_branch(root: Path, current_branch_name: str) -> tuple[str | None, str | None, str]:
    """Return the branch immediately preceding the latest checkout into current branch.

    We intentionally do not infer from worktree directory names. If the reflog transition does not
    point at an existing local branch, no deletion candidate is returned.
    """
    result = run(["git", "reflog", "show", "--format=%gs", "HEAD"], cwd=root, check=False)
    if result.returncode != 0:
        return None, None, ""
    pattern = re.compile(r"^checkout: moving from (.+) to (.+)$")
    for raw in result.stdout.splitlines():
        message = raw.strip()
        match = pattern.match(message)
        if not match:
            continue
        source, target = match.group(1), match.group(2)
        if target != current_branch_name:
            continue
        if source == current_branch_name:
            return None, None, message
        source_sha = _local_branch_sha(root, source)
        if not source_sha:
            return None, None, message
        return source, source_sha, message
    return None, None, ""


def _fingerprint(
    *,
    worktree: Path,
    branch: str,
    head: str,
    base: str,
    base_ref: str | None,
    base_sha: str | None,
    remote: str,
    remote_url_value: str,
    remote_sha: str | None,
    github_status: str,
    tracked_branch: str | None,
    tracked_head: str | None,
    tracked_remote_sha: str | None,
    tracked_merge_evidence: str,
    tracked_pr: PullRequestEvidence | None,
    tracked_cleanup_allowed: bool,
    tracked_remote_delete_available: bool,
    tracked_reason: str,
    tracked_reflog_message: str,
    worktrees: str,
    status: bytes,
) -> str:
    digest = hashlib.sha256()
    payload = {
        "version": "git-workspace-cleanup-worktree-only-v2",
        "worktree": str(worktree),
        "branch": branch,
        "head": head,
        "base": base,
        "base_ref": base_ref or "",
        "base_sha": base_sha or "",
        "remote": remote,
        "remote_url": remote_url_value,
        "remote_sha": remote_sha or "",
        "github_status": github_status,
        "tracked_branch": tracked_branch or "",
        "tracked_head": tracked_head or "",
        "tracked_remote_sha": tracked_remote_sha or "",
        "tracked_merge_evidence": tracked_merge_evidence,
        "tracked_pr_number": tracked_pr.number if tracked_pr else 0,
        "tracked_pr_url": tracked_pr.url if tracked_pr else "",
        "tracked_pr_merged_at": tracked_pr.merged_at if tracked_pr else "",
        "tracked_cleanup_allowed": tracked_cleanup_allowed,
        "tracked_remote_delete_available": tracked_remote_delete_available,
        "tracked_reason": tracked_reason,
        "tracked_reflog_message": tracked_reflog_message,
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
    semantic_rows, eol_only_rows = classify_worktree_status(root, raw_status)
    semantic_status = encode_status_rows(semantic_rows)
    eol_only_paths = tuple(path for _status, path, _original in eol_only_rows)
    if semantic_rows:
        raise CleanupError("worktree contains semantic modified/staged/untracked files; cleanup is blocked")

    wt_raw = worktree_snapshot(root)
    worktrees = parse_worktrees(wt_raw)
    main = worktrees[0].path
    target_matches = [entry for entry in worktrees if entry.path == root]
    if len(target_matches) != 1:
        raise CleanupError(f"target worktree is not uniquely registered: {root}")
    target = target_matches[0]
    if target.path == main:
        raise CleanupError("the primary worktree cannot be removed by git-workspace-cleanup")
    if target.detached:
        raise CleanupError("detached HEAD worktree cannot be cleaned automatically")
    if target.locked:
        raise CleanupError("target worktree is locked; unlock it explicitly before cleanup")
    if target.prunable:
        raise CleanupError("target worktree is marked prunable; repair/prune metadata before cleanup")

    url = remote_url(root, remote)
    base_remote_sha = remote_branch_sha(root, remote, branch)
    head = head_sha(root)
    base_ref, base_sha = resolve_base_ref(root, remote, base)
    gh_status, _ = github_auth_status(root, url)

    tracked_branch, tracked_head, reflog_message = _previous_checkout_branch(root, branch)
    tracked_remote_sha: str | None = None
    tracked_merge_evidence = ""
    tracked_pr: PullRequestEvidence | None = None
    tracked_cleanup_allowed = False
    tracked_remote_delete_available = False
    tracked_reason = "HEAD reflog에서 삭제 가능한 이전 local branch를 확인하지 못했습니다."

    if tracked_branch and tracked_head:
        tracked_reason = ""
        if tracked_branch == base:
            tracked_reason = "이전 branch가 base branch와 동일하여 삭제 대상에서 제외합니다."
        elif any(entry.branch == tracked_branch for entry in worktrees):
            tracked_reason = "이전 branch가 다른 worktree에서 checkout 중이라 삭제할 수 없습니다."
        elif github_slug(url) is not None and gh_status != "ready":
            tracked_reason = "GitHub 인증이 없어 이전 branch의 open PR 여부를 검증할 수 없습니다."
        else:
            prs = github_pull_requests(root, url=url, branch=tracked_branch, github_status=gh_status)
            open_prs = [pr for pr in prs if pr.state == "open"]
            if open_prs:
                tracked_reason = "이전 branch에 open Pull Request가 남아 있어 삭제하지 않습니다."
            else:
                tracked_pr = select_merged_pr(prs, head=tracked_head, explicit_base=base)
                if tracked_pr and tracked_pr.base == base and tracked_pr.head_sha == tracked_head:
                    tracked_merge_evidence = "github-pr-merged"
                elif branch_is_ancestor(root, tracked_head, base_ref):
                    tracked_merge_evidence = "git-ancestor"
                else:
                    tracked_reason = f"이전 branch가 base '{base}'에 merge되었다는 증거가 없습니다."

                if tracked_merge_evidence:
                    tracked_cleanup_allowed = True
                    tracked_remote_sha = remote_branch_sha(root, remote, tracked_branch)
                    if tracked_remote_sha and tracked_remote_sha != tracked_head:
                        tracked_reason = (
                            f"로컬 branch는 정리 가능하지만 {remote}/{tracked_branch}가 승인 대상 SHA와 달라 "
                            "원격 branch는 보존합니다."
                        )
                    tracked_remote_delete_available = bool(
                        tracked_remote_sha
                        and tracked_remote_sha == tracked_head
                        and remote_delete_supported(url, gh_status)
                    )

    fingerprint = _fingerprint(
        worktree=target.path,
        branch=branch,
        head=head,
        base=base,
        base_ref=base_ref,
        base_sha=base_sha,
        remote=remote,
        remote_url_value=url,
        remote_sha=base_remote_sha,
        github_status=gh_status,
        tracked_branch=tracked_branch,
        tracked_head=tracked_head,
        tracked_remote_sha=tracked_remote_sha,
        tracked_merge_evidence=tracked_merge_evidence,
        tracked_pr=tracked_pr,
        tracked_cleanup_allowed=tracked_cleanup_allowed,
        tracked_remote_delete_available=tracked_remote_delete_available,
        tracked_reason=tracked_reason,
        tracked_reflog_message=reflog_message,
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
        base_ref=base_ref,
        base_sha=base_sha,
        remote=remote,
        remote_url=url,
        remote_branch_sha=base_remote_sha,
        github_status=gh_status,
        worktree_snapshot=wt_raw,
        status_snapshot=raw_status,
        semantic_status_snapshot=semantic_status,
        eol_only_paths=eol_only_paths,
        eol_only_force_allowed=bool(eol_only_paths) and not semantic_rows,
        tracked_previous_branch=tracked_branch,
        tracked_previous_head_sha=tracked_head,
        tracked_previous_remote_sha=tracked_remote_sha,
        tracked_previous_merge_evidence=tracked_merge_evidence,
        tracked_previous_pr=tracked_pr,
        tracked_previous_cleanup_allowed=tracked_cleanup_allowed,
        tracked_previous_remote_delete_available=tracked_remote_delete_available,
        tracked_previous_reason=tracked_reason,
        tracked_reflog_message=reflog_message,
        fingerprint=fingerprint,
    )
