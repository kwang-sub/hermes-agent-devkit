#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any


class CleanupError(RuntimeError):
    pass


@dataclass(frozen=True)
class WorktreeEntry:
    path: Path
    head: str | None
    branch: str | None
    detached: bool
    locked: bool
    prunable: bool


@dataclass(frozen=True)
class PullRequestEvidence:
    number: int
    url: str
    state: str
    merged_at: str | None
    base: str
    head_ref: str
    head_sha: str


@dataclass(frozen=True)
class CleanupInspection:
    repo_root: Path
    common_git_dir: Path
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
    github_detail: str
    pr: PullRequestEvidence | None
    merge_evidence: str
    remote_delete_available: bool
    worktree_snapshot: str
    status_snapshot: bytes
    semantic_status_snapshot: bytes
    eol_only_paths: tuple[str, ...]
    eol_only_force_allowed: bool
    fingerprint: str


def run(
    args: list[str],
    *,
    cwd: Path,
    check: bool = True,
    text: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    completed = subprocess.run(
        args,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
        env=env,
    )
    if check and completed.returncode != 0:
        stdout = completed.stdout if text else completed.stdout.decode("utf-8", "replace")
        stderr = completed.stderr if text else completed.stderr.decode("utf-8", "replace")
        detail = (stdout + "\n" + stderr).strip()
        raise CleanupError(f"command failed ({completed.returncode}): {' '.join(args)}\n{detail}")
    return completed


def emit(key: str, value: object) -> None:
    if value is None:
        value = ""
    print(f"{key}={value}")


def resolve_workspace(value: str) -> Path:
    workspace = Path(value).expanduser().resolve()
    if not workspace.is_dir():
        raise CleanupError(f"workspace does not exist: {workspace}")
    return workspace


def repo_root(workspace: Path) -> Path:
    value = run(["git", "rev-parse", "--show-toplevel"], cwd=workspace).stdout.strip()
    if not value:
        raise CleanupError(f"workspace is not a Git worktree: {workspace}")
    return Path(value).resolve()


def common_git_dir(root: Path) -> Path:
    value = run(["git", "rev-parse", "--git-common-dir"], cwd=root).stdout.strip()
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def current_branch(root: Path) -> str:
    branch = run(["git", "branch", "--show-current"], cwd=root).stdout.strip()
    if not branch:
        raise CleanupError("detached HEAD worktree cannot be cleaned automatically")
    return branch


def head_sha(root: Path) -> str:
    return run(["git", "rev-parse", "HEAD"], cwd=root).stdout.strip()


def remote_url(root: Path, remote: str) -> str:
    result = run(["git", "config", "--get", f"remote.{remote}.url"], cwd=root, check=False)
    value = result.stdout.strip()
    if result.returncode != 0 or not value:
        raise CleanupError(f"remote URL is not configured: {remote}")
    return value


def status_bytes(root: Path) -> bytes:
    return run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=root,
        text=False,
    ).stdout


def parse_status(raw: bytes) -> list[tuple[str, str, str | None]]:
    parts = raw.split(b"\0")
    rows: list[tuple[str, str, str | None]] = []
    index = 0
    while index < len(parts):
        entry = parts[index]
        if not entry:
            index += 1
            continue
        if len(entry) < 4:
            raise CleanupError(f"unexpected porcelain entry: {entry!r}")
        status = entry[:2].decode("ascii", "replace")
        path = entry[3:].decode("utf-8", "surrogateescape")
        original = None
        if "R" in status or "C" in status:
            index += 1
            if index >= len(parts) or not parts[index]:
                raise CleanupError("rename/copy porcelain entry is missing the original path")
            original = parts[index].decode("utf-8", "surrogateescape")
        rows.append((status, path, original))
        index += 1
    return rows


def _normalize_crlf(value: bytes) -> bytes:
    return value.replace(b"\r\n", b"\n")


def _looks_utf8_text(value: bytes) -> bool:
    if b"\x00" in value:
        return False
    try:
        value.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _index_blob(root: Path, path: str) -> bytes | None:
    result = run(["git", "show", f":{path}"], cwd=root, check=False, text=False)
    if result.returncode != 0:
        return None
    return result.stdout


def is_eol_only_worktree_change(
    root: Path,
    row: tuple[str, str, str | None],
) -> bool:
    status, path, original = row
    if status != " M" or original is not None:
        return False
    target = root / path
    if not target.is_file() or target.is_symlink():
        return False
    index = _index_blob(root, path)
    if index is None:
        return False
    worktree = target.read_bytes()
    if index == worktree:
        return False
    if not (_looks_utf8_text(index) and _looks_utf8_text(worktree)):
        return False
    return _normalize_crlf(index) == _normalize_crlf(worktree)


def encode_status_rows(rows: list[tuple[str, str, str | None]]) -> bytes:
    parts: list[bytes] = []
    for status, path, original in rows:
        parts.append(
            status.encode("ascii", "replace")
            + b" "
            + path.encode("utf-8", "surrogateescape")
        )
        if original:
            parts.append(original.encode("utf-8", "surrogateescape"))
    return b"\0".join(parts) + (b"\0" if parts else b"")


def classify_worktree_status(
    root: Path,
    raw: bytes | None = None,
) -> tuple[
    list[tuple[str, str, str | None]],
    list[tuple[str, str, str | None]],
]:
    actual = status_bytes(root) if raw is None else raw
    semantic: list[tuple[str, str, str | None]] = []
    eol_only: list[tuple[str, str, str | None]] = []
    for row in parse_status(actual):
        if is_eol_only_worktree_change(root, row):
            eol_only.append(row)
        else:
            semantic.append(row)
    return semantic, eol_only


def format_dirty_status(raw: bytes, limit: int = 8) -> str:
    rows = [item.decode("utf-8", "replace") for item in raw.split(b"\0") if item]
    shown = rows[:limit]
    suffix = "" if len(rows) <= limit else f"\n... and {len(rows) - limit} more"
    return "\n".join(shown) + suffix


def worktree_snapshot(root: Path) -> str:
    return run(["git", "worktree", "list", "--porcelain"], cwd=root).stdout


def parse_worktrees(raw: str) -> list[WorktreeEntry]:
    entries: list[WorktreeEntry] = []
    current: dict[str, Any] | None = None

    def flush() -> None:
        nonlocal current
        if not current:
            return
        path_raw = current.get("path")
        if not path_raw:
            raise CleanupError("git worktree list returned an entry without a path")
        branch_ref = current.get("branch")
        branch = None
        if isinstance(branch_ref, str):
            prefix = "refs/heads/"
            branch = branch_ref[len(prefix):] if branch_ref.startswith(prefix) else branch_ref
        entries.append(
            WorktreeEntry(
                path=Path(str(path_raw)).resolve(),
                head=current.get("head"),
                branch=branch,
                detached=bool(current.get("detached")),
                locked=bool(current.get("locked")),
                prunable=bool(current.get("prunable")),
            )
        )
        current = None

    for line in raw.splitlines():
        if not line:
            flush()
            continue
        if line.startswith("worktree "):
            flush()
            current = {"path": line[len("worktree "): ]}
            continue
        if current is None:
            continue
        if line.startswith("HEAD "):
            current["head"] = line[len("HEAD "):]
        elif line.startswith("branch "):
            current["branch"] = line[len("branch "):]
        elif line == "detached":
            current["detached"] = True
        elif line.startswith("locked"):
            current["locked"] = True
        elif line.startswith("prunable"):
            current["prunable"] = True
    flush()

    if not entries:
        raise CleanupError("git worktree list returned no worktrees")
    return entries


def remote_branch_sha(root: Path, remote: str, branch: str) -> str | None:
    result = run(
        ["git", "ls-remote", "--heads", remote, f"refs/heads/{branch}"],
        cwd=root,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stdout + "\n" + result.stderr).strip()
        raise CleanupError(f"failed to inspect remote branch {remote}/{branch}\n{detail}")
    line = result.stdout.strip()
    if not line:
        return None
    return line.split()[0]


def resolve_remote_head(root: Path, remote: str) -> str | None:
    result = run(
        ["git", "symbolic-ref", "--quiet", "--short", f"refs/remotes/{remote}/HEAD"],
        cwd=root,
        check=False,
    )
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    prefix = f"{remote}/"
    if value.startswith(prefix):
        value = value[len(prefix):]
    return value or None


def resolve_base_ref(root: Path, remote: str, base: str) -> tuple[str | None, str | None]:
    for ref in (f"refs/remotes/{remote}/{base}", f"refs/heads/{base}"):
        result = run(["git", "rev-parse", "--verify", ref], cwd=root, check=False)
        if result.returncode == 0:
            return ref, result.stdout.strip()
    return None, None


def github_slug(url: str) -> str | None:
    patterns = (
        r"^https?://github\.com/([^/]+/[^/]+?)(?:\.git)?/?$",
        r"^git@github\.com:([^/]+/[^/]+?)(?:\.git)?$",
        r"^ssh://git@github\.com/([^/]+/[^/]+?)(?:\.git)?/?$",
    )
    for pattern in patterns:
        match = re.match(pattern, url.strip())
        if match:
            return match.group(1)
    return None


def ensure_gh_config_env() -> None:
    if not os.environ.get("GH_CONFIG_DIR"):
        os.environ["GH_CONFIG_DIR"] = os.environ.get("HERMES_GH_CONFIG_DIR", "/opt/data/gh")


def github_auth_status(root: Path, url: str) -> tuple[str, str]:
    if github_slug(url) is None:
        return "not-github", ""
    if shutil.which("gh") is None:
        return "unavailable", "gh CLI was not found"
    ensure_gh_config_env()
    result = run(
        ["gh", "auth", "status", "--hostname", "github.com"],
        cwd=root,
        check=False,
    )
    detail = (result.stdout + "\n" + result.stderr).strip()
    if result.returncode != 0:
        return "unavailable", detail
    return "ready", detail


def github_pull_requests(
    root: Path,
    *,
    url: str,
    branch: str,
    github_status: str,
) -> list[PullRequestEvidence]:
    slug = github_slug(url)
    if slug is None or github_status != "ready":
        return []
    owner = slug.split("/", 1)[0]
    ensure_gh_config_env()
    listing = run(
        [
            "gh",
            "api",
            "--hostname",
            "github.com",
            "-X",
            "GET",
            f"repos/{slug}/pulls",
            "-f",
            "state=all",
            "-f",
            f"head={owner}:{branch}",
            "-f",
            "per_page=100",
        ],
        cwd=root,
        check=False,
    )
    if listing.returncode != 0:
        detail = (listing.stdout + "\n" + listing.stderr).strip()
        raise CleanupError(f"failed to inspect GitHub pull requests for {branch}\n{detail}")
    try:
        items = json.loads(listing.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise CleanupError(f"failed to parse GitHub pull request list: {exc}") from exc
    if not isinstance(items, list):
        raise CleanupError("GitHub pull request list did not return a JSON array")

    evidence: list[PullRequestEvidence] = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("number"), int):
            continue
        number = int(item["number"])
        detail_result = run(
            [
                "gh",
                "api",
                "--hostname",
                "github.com",
                f"repos/{slug}/pulls/{number}",
            ],
            cwd=root,
            check=False,
        )
        if detail_result.returncode != 0:
            detail = (detail_result.stdout + "\n" + detail_result.stderr).strip()
            raise CleanupError(f"failed to inspect GitHub pull request #{number}\n{detail}")
        try:
            pr = json.loads(detail_result.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise CleanupError(f"failed to parse GitHub pull request #{number}: {exc}") from exc
        if not isinstance(pr, dict):
            continue
        head = pr.get("head") if isinstance(pr.get("head"), dict) else {}
        base = pr.get("base") if isinstance(pr.get("base"), dict) else {}
        head_ref = str(head.get("ref") or "")
        if head_ref != branch:
            continue
        evidence.append(
            PullRequestEvidence(
                number=number,
                url=str(pr.get("html_url") or ""),
                state=str(pr.get("state") or "").lower(),
                merged_at=str(pr.get("merged_at")) if pr.get("merged_at") else None,
                base=str(base.get("ref") or ""),
                head_ref=head_ref,
                head_sha=str(head.get("sha") or ""),
            )
        )
    return evidence


def select_merged_pr(
    prs: list[PullRequestEvidence],
    *,
    head: str,
    explicit_base: str | None,
) -> PullRequestEvidence | None:
    candidates = [
        pr
        for pr in prs
        if pr.merged_at
        and pr.head_sha == head
        and (explicit_base is None or pr.base == explicit_base)
    ]
    if not candidates:
        return None
    bases = {pr.base for pr in candidates if pr.base}
    if explicit_base is None and len(bases) > 1:
        raise CleanupError(
            "multiple merged PR base branches match this worktree; provide --base-branch explicitly"
        )
    candidates.sort(key=lambda pr: (pr.merged_at or "", pr.number), reverse=True)
    return candidates[0]


def branch_is_ancestor(root: Path, head: str, base_ref: str | None) -> bool:
    if not base_ref:
        return False
    return (
        run(["git", "merge-base", "--is-ancestor", head, base_ref], cwd=root, check=False).returncode
        == 0
    )


def fingerprint_payload(
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
    github_status_value: str,
    pr: PullRequestEvidence | None,
    merge_evidence: str,
    worktrees: str,
    status: bytes,
) -> str:
    digest = hashlib.sha256()
    payload = {
        "version": "dev-workspace-cleanup-v2-eol-aware",
        "worktree": str(worktree),
        "branch": branch,
        "head": head,
        "base": base,
        "base_ref": base_ref or "",
        "base_sha": base_sha or "",
        "remote": remote,
        "remote_url": remote_url_value,
        "remote_sha": remote_sha or "",
        "github_status": github_status_value,
        "pr_number": pr.number if pr else 0,
        "pr_url": pr.url if pr else "",
        "pr_merged_at": pr.merged_at if pr else "",
        "pr_base": pr.base if pr else "",
        "pr_head_sha": pr.head_sha if pr else "",
        "merge_evidence": merge_evidence,
        "worktrees": worktrees,
    }
    digest.update(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    digest.update(b"\0")
    digest.update(status)
    return digest.hexdigest()


def remote_delete_supported(url: str, github_status_value: str) -> bool:
    if url.startswith("https://") or url.startswith("http://"):
        if github_slug(url) is not None:
            return github_status_value == "ready"
    return True


def inspect_cleanup(
    workspace_value: str,
    *,
    remote: str = "origin",
    explicit_base: str | None = None,
) -> CleanupInspection:
    workspace = resolve_workspace(workspace_value)
    root = repo_root(workspace)
    common = common_git_dir(root)
    branch = current_branch(root)
    head = head_sha(root)
    raw_status = status_bytes(root)
    semantic_rows, eol_only_rows = classify_worktree_status(root, raw_status)
    semantic_status = encode_status_rows(semantic_rows)
    eol_only_paths = tuple(path for _status, path, _original in eol_only_rows)
    if semantic_rows:
        raise CleanupError(
            "worktree contains semantic modified/staged/untracked files; cleanup is blocked\n"
            + format_dirty_status(semantic_status)
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
    if target.locked:
        raise CleanupError("target worktree is locked; unlock it explicitly before cleanup")
    if target.prunable:
        raise CleanupError("target worktree is marked prunable; repair/prune metadata before cleanup")

    same_branch = [entry for entry in worktrees if entry.branch == branch]
    if len(same_branch) != 1 or same_branch[0].path != target.path:
        raise CleanupError(f"branch is associated with another worktree: {branch}")

    url = remote_url(root, remote)
    remote_sha = remote_branch_sha(root, remote, branch)
    if remote_sha and remote_sha != head:
        raise CleanupError(
            f"local HEAD differs from {remote}/{branch}; publish/synchronize the branch before cleanup"
        )

    gh_status, gh_detail = github_auth_status(root, url)
    prs = github_pull_requests(root, url=url, branch=branch, github_status=gh_status)
    open_prs = [pr for pr in prs if pr.state == "open"]
    if open_prs:
        urls = ", ".join(pr.url or f"#{pr.number}" for pr in open_prs)
        raise CleanupError(f"branch still has an open pull request: {urls}")

    explicit = explicit_base.strip() if explicit_base and explicit_base.strip() else None
    merged_pr = select_merged_pr(prs, head=head, explicit_base=explicit)

    if explicit:
        base = explicit
    elif merged_pr and merged_pr.base:
        base = merged_pr.base
    else:
        base = resolve_remote_head(root, remote) or ""

    if not base:
        raise CleanupError(
            "base branch could not be resolved; provide --base-branch or ensure remote HEAD is configured"
        )
    if base == branch:
        raise CleanupError(f"cleanup branch must differ from base branch: {branch}")

    base_ref, base_sha = resolve_base_ref(root, remote, base)
    if merged_pr and merged_pr.base == base and merged_pr.head_sha == head:
        merge_evidence = "github-pr-merged"
    elif branch_is_ancestor(root, head, base_ref):
        merge_evidence = "git-ancestor"
    else:
        if gh_status != "ready" and github_slug(url):
            raise CleanupError(
                "branch is not proven merged into the base branch and GitHub PR evidence is unavailable; "
                f"GitHub status={gh_status}"
            )
        raise CleanupError(
            f"branch is not proven merged into base '{base}'; merge the PR/branch before cleanup"
        )

    delete_available = bool(remote_sha) and remote_delete_supported(url, gh_status)
    fingerprint = fingerprint_payload(
        worktree=target.path,
        branch=branch,
        head=head,
        base=base,
        base_ref=base_ref,
        base_sha=base_sha,
        remote=remote,
        remote_url_value=url,
        remote_sha=remote_sha,
        github_status_value=gh_status,
        pr=merged_pr,
        merge_evidence=merge_evidence,
        worktrees=wt_raw,
        status=raw_status,
    )

    return CleanupInspection(
        repo_root=root,
        common_git_dir=common,
        main_worktree=main,
        worktree=target.path,
        branch=branch,
        head_sha=head,
        base_branch=base,
        base_ref=base_ref,
        base_sha=base_sha,
        remote=remote,
        remote_url=url,
        remote_branch_sha=remote_sha,
        github_status=gh_status,
        github_detail=gh_detail,
        pr=merged_pr,
        merge_evidence=merge_evidence,
        remote_delete_available=delete_available,
        worktree_snapshot=wt_raw,
        status_snapshot=raw_status,
        semantic_status_snapshot=semantic_status,
        eol_only_paths=eol_only_paths,
        eol_only_force_allowed=bool(eol_only_paths) and not semantic_rows,
        fingerprint=fingerprint,
    )


def push_delete_command(state: CleanupInspection) -> list[str]:
    url = state.remote_url
    if url.startswith("https://") or url.startswith("http://"):
        if github_slug(url) is not None:
            if state.github_status != "ready":
                raise CleanupError("GitHub authentication is required to delete the HTTPS remote branch")
            ensure_gh_config_env()
            return [
                "git",
                "-c",
                "credential.helper=",
                "-c",
                "credential.helper=!gh auth git-credential",
                "push",
                state.remote,
                "--delete",
                state.branch,
            ]
    return ["git", "push", state.remote, "--delete", state.branch]
