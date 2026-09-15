#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Iterable


class PublishError(RuntimeError):
    pass


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
        raise PublishError(f"command failed ({completed.returncode}): {' '.join(args)}\n{detail}")
    return completed


def resolve_workspace(value: str) -> Path:
    workspace = Path(value).expanduser().resolve()
    if not workspace.is_dir():
        raise PublishError(f"workspace does not exist: {workspace}")
    return workspace


def repo_root(workspace: Path) -> Path:
    result = run(["git", "rev-parse", "--show-toplevel"], cwd=workspace)
    return Path(result.stdout.strip()).resolve()


def current_branch(root: Path) -> str:
    result = run(["git", "branch", "--show-current"], cwd=root)
    branch = result.stdout.strip()
    if not branch:
        raise PublishError("detached HEAD is not publishable")
    return branch


def head_sha(root: Path) -> str:
    return run(["git", "rev-parse", "HEAD"], cwd=root).stdout.strip()


def remote_url(root: Path, remote: str) -> str:
    value = run(["git", "remote", "get-url", remote], cwd=root).stdout.strip()
    if not value:
        raise PublishError(f"remote URL is empty: {remote}")
    return value


def resolve_base_branch(root: Path, remote: str, explicit: str | None) -> str | None:
    if explicit:
        return explicit.strip()
    result = run(
        ["git", "symbolic-ref", "--quiet", "--short", f"refs/remotes/{remote}/HEAD"],
        cwd=root,
        check=False,
    )
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    prefix = f"{remote}/"
    return value[len(prefix):] if value.startswith(prefix) else value or None


def _pathspec_args(includes: Iterable[str]) -> list[str]:
    values = [value for value in includes if value]
    return ["--", *(values or ["."])]


def status_bytes(root: Path, includes: Iterable[str]) -> bytes:
    result = run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all", *_pathspec_args(includes)],
        cwd=root,
        text=False,
    )
    return result.stdout


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
            raise PublishError(f"unexpected porcelain entry: {entry!r}")
        status = entry[:2].decode("ascii", "replace")
        path = entry[3:].decode("utf-8", "surrogateescape")
        original = None
        if "R" in status or "C" in status:
            index += 1
            if index >= len(parts) or not parts[index]:
                raise PublishError("rename/copy porcelain entry is missing the original path")
            original = parts[index].decode("utf-8", "surrogateescape")
        rows.append((status, path, original))
        index += 1
    return rows


def changed_rows(root: Path, includes: Iterable[str]) -> list[tuple[str, str, str | None]]:
    return parse_status(status_bytes(root, includes))


def diff_stat(root: Path, includes: Iterable[str]) -> str:
    result = run(["git", "diff", "--stat", "HEAD", *_pathspec_args(includes)], cwd=root)
    tracked = result.stdout.rstrip()
    rows = changed_rows(root, includes)
    untracked = [path for status, path, _ in rows if status == "??"]
    if untracked:
        suffix = "\n".join(f" {path} | untracked" for path in untracked)
        return "\n".join(part for part in (tracked, suffix) if part)
    return tracked


def publish_fingerprint(root: Path, includes: Iterable[str]) -> str:
    includes = list(includes)
    digest = hashlib.sha256()
    digest.update(b"dev-pr-publish-v1\0")
    digest.update(current_branch(root).encode("utf-8") + b"\0")
    digest.update(head_sha(root).encode("ascii") + b"\0")

    raw_status = status_bytes(root, includes)
    digest.update(raw_status)
    diff = run(
        ["git", "diff", "--binary", "HEAD", *_pathspec_args(includes)],
        cwd=root,
        text=False,
    ).stdout
    digest.update(diff)

    for status, path, _ in parse_status(raw_status):
        if status != "??":
            continue
        target = root / path
        digest.update(path.encode("utf-8", "surrogateescape") + b"\0")
        if target.is_symlink():
            digest.update(b"symlink\0" + os.readlink(target).encode("utf-8", "surrogateescape"))
        elif target.is_file():
            digest.update(b"file\0")
            with target.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        else:
            digest.update(b"missing-or-special\0")
    return digest.hexdigest()


def ensure_gh(root: Path) -> None:
    if shutil.which("gh") is None:
        raise PublishError("gh CLI is required for PR publishing but was not found")
    result = run(["gh", "auth", "status"], cwd=root, check=False)
    if result.returncode != 0:
        detail = (result.stdout + "\n" + result.stderr).strip()
        raise PublishError(f"gh authentication is not ready\n{detail}")


def list_open_prs(root: Path, *, base: str, head: str) -> list[dict]:
    ensure_gh(root)
    result = run(
        [
            "gh",
            "pr",
            "list",
            "--state",
            "open",
            "--base",
            base,
            "--head",
            head,
            "--json",
            "number,url,title,baseRefName,headRefName",
        ],
        cwd=root,
    )
    try:
        value = json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise PublishError(f"failed to parse gh pr list JSON: {exc}") from exc
    if not isinstance(value, list):
        raise PublishError("gh pr list did not return a JSON list")
    return [item for item in value if isinstance(item, dict)]


def remote_head_sha(root: Path, remote: str, branch: str) -> str | None:
    result = run(
        ["git", "ls-remote", "--heads", remote, f"refs/heads/{branch}"],
        cwd=root,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stdout + "\n" + result.stderr).strip()
        raise PublishError(f"failed to read remote branch {remote}/{branch}\n{detail}")
    line = result.stdout.strip()
    if not line:
        return None
    return line.split()[0]


def validate_conventional_commit(message: str) -> None:
    import re

    pattern = re.compile(
        r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([^)]+\))?!?:\s+\S.+$"
    )
    if not pattern.match(message.strip()):
        raise PublishError(
            "commit message must use Conventional Commits prefix, e.g. 'feat: 한국어 설명'"
        )


def emit(key: str, value: object) -> None:
    if value is None:
        value = ""
    print(f"{key}={value}")
