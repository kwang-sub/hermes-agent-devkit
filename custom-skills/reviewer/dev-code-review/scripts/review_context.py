#!/usr/bin/env python3
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys


class ReviewError(RuntimeError):
    pass


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if check and proc.returncode != 0:
        raise ReviewError((proc.stderr or proc.stdout).strip() or "command failed")
    return proc


def ensure_safe_directory(path: Path) -> None:
    resolved = str(path.resolve())
    current = run(["git", "config", "--global", "--get-all", "safe.directory"], check=False)
    configured = {line.strip() for line in current.stdout.splitlines() if line.strip()}
    if resolved not in configured:
        added = run(["git", "config", "--global", "--add", "safe.directory", resolved], check=False)
        if added.returncode != 0:
            raise ReviewError((added.stderr or added.stdout).strip() or f"cannot register safe.directory: {resolved}")


def resolve_commit(root: Path, value: str, label: str) -> str:
    resolved = run(["git", "-C", str(root), "rev-parse", "--verify", f"{value}^{{commit}}"], check=False)
    if resolved.returncode != 0:
        raise ReviewError(f"{label} does not resolve to a commit: {value}")
    return resolved.stdout.strip()


def split_includes(root: Path, values: list[str]) -> tuple[list[str], list[str]]:
    local: list[str] = []
    external: list[str] = []
    for raw in values:
        candidate = (root / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
        try:
            rel = candidate.relative_to(root)
        except ValueError:
            if not Path(raw).is_absolute():
                raise ReviewError(f"included path escapes workspace: {raw}")
            external.append(candidate.as_posix())
            continue
        local.append(rel.as_posix())
    return sorted(dict.fromkeys(local)), sorted(dict.fromkeys(external))


def git_paths(root: Path, args: list[str], includes: list[str]) -> list[str]:
    cmd = ["git", "-C", str(root), *args]
    if includes:
        cmd.extend(["--", *includes])
    return [line.strip() for line in run(cmd).stdout.splitlines() if line.strip()]


def classify_tracked(root: Path, base_sha: str, raw_paths: list[str]) -> tuple[list[str], list[str]]:
    effective: list[str] = []
    eol_only: list[str] = []
    for path in raw_paths:
        result = run(
            ["git", "-C", str(root), "diff", "--quiet", "--ignore-cr-at-eol", base_sha, "--", path],
            check=False,
        )
        if result.returncode == 0:
            eol_only.append(path)
        elif result.returncode == 1:
            effective.append(path)
        else:
            raise ReviewError(
                (result.stderr or result.stdout).strip()
                or f"cannot classify tracked change for {path}: rc={result.returncode}"
            )
    return effective, eol_only


def untracked_paths(root: Path, includes: list[str]) -> list[str]:
    return git_paths(root, ["ls-files", "--others", "--exclude-standard"], includes)


def diff_checker_command() -> list[str]:
    override = os.getenv("HERMES_DIFF_CHECK")
    if override:
        return [override]
    installed = Path("/usr/local/bin/hermes-diff-check")
    if installed.is_file():
        return [str(installed)]
    repo_candidate = Path(__file__).resolve().parents[4] / "scripts" / "hermes-diff-check.py"
    if repo_candidate.is_file():
        return [sys.executable, str(repo_candidate)]
    raise ReviewError("CRLF-aware diff checker is unavailable; rebuild/update the DevKit runtime")


def check_whitespace(root: Path, base_sha: str, tracked: list[str], untracked: list[str]) -> None:
    cmd = [*diff_checker_command(), "--repo", str(root), "--base", base_sha]
    for path in tracked:
        cmd.extend(["--tracked", path])
    for path in untracked:
        cmd.extend(["--untracked", path])
    result = run(cmd, check=False)
    if result.returncode == 0:
        return
    if result.returncode == 1:
        details = [
            line.split("=", 1)[1]
            for line in result.stdout.splitlines()
            if re.match(r"^WHITESPACE_ERROR_\d+=", line)
        ]
        raise ReviewError(" | ".join(details) or "CRLF-aware whitespace validation failed")
    raise ReviewError((result.stderr or result.stdout).strip() or "CRLF-aware diff checker failed")


def scope_sha256(root: Path, paths: list[str]) -> str:
    digest = sha256()
    for path in sorted(dict.fromkeys(paths)):
        file_path = root / path
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        if file_path.is_file():
            digest.update(b"F\0")
            digest.update(file_path.read_bytes().replace(b"\r\n", b"\n"))
        else:
            digest.update(b"MISSING\0")
        digest.update(b"\0")
    return digest.hexdigest()


def external_sha256(paths: list[str]) -> str:
    digest = sha256()
    for raw in sorted(dict.fromkeys(paths)):
        path = Path(raw)
        digest.update(raw.encode("utf-8"))
        digest.update(b"\0")
        if path.is_file():
            digest.update(b"F\0")
            digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
        else:
            digest.update(b"MISSING\0")
        digest.update(b"\0")
    return digest.hexdigest()


def handoff_state_path(root: Path) -> Path:
    raw = run(["git", "-C", str(root), "rev-parse", "--git-path", "hermes/review-handoff.json"]).stdout.strip()
    path = Path(raw)
    return path if path.is_absolute() else (root / path).resolve()


def load_handoff_state(root: Path) -> dict[str, object] | None:
    path = handoff_state_path(root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    fingerprint = data.get("effective_scope_sha256")
    effective_paths = data.get("effective_paths")
    if data.get("status") != "valid":
        return None
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        return None
    if not isinstance(effective_paths, list) or not all(isinstance(item, str) for item in effective_paths):
        return None
    return data


def handoff_gate(root: Path, current_paths: list[str], current_hash: str) -> tuple[bool, str]:
    state = load_handoff_state(root)
    if not state:
        return False, "missing"
    state_paths = [str(item) for item in state["effective_paths"]]
    state_hash = str(state["effective_scope_sha256"])
    if scope_sha256(root, state_paths) != state_hash:
        return False, "stale"
    if sorted(state_paths) != sorted(current_paths):
        return False, "scope_mismatch"
    if state_hash != current_hash:
        return False, "fingerprint_mismatch"
    return True, "matched"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-branch", required=True)
    ap.add_argument("--base-sha", required=True)
    ap.add_argument("--expected-branch", required=True)
    ap.add_argument("--workspace")
    ap.add_argument("--expected-workspace")
    ap.add_argument("--include", action="append", default=[])
    ap.add_argument(
        "--allow-full-scan",
        action="store_true",
        help="Explicit diagnostic mode only. Allows repository-wide review discovery.",
    )
    args = ap.parse_args()

    root = Path(args.workspace or ".").resolve()
    ensure_safe_directory(root)
    top = Path(run(["git", "-C", str(root), "rev-parse", "--show-toplevel"]).stdout.strip()).resolve()
    if top != root:
        raise ReviewError(f"review must start at workspace root: workspace={root}, root={top}")
    if args.expected_workspace and root != Path(args.expected_workspace).resolve():
        raise ReviewError(f"workspace mismatch: expected={Path(args.expected_workspace).resolve()}, actual={root}")

    branch = run(["git", "-C", str(root), "branch", "--show-current"]).stdout.strip()
    if branch != args.expected_branch:
        raise ReviewError(f"branch mismatch: expected={args.expected_branch}, actual={branch}")
    if not re.fullmatch(r"[0-9a-fA-F]{40}", args.base_sha):
        raise ReviewError("base SHA must be a full 40-character hexadecimal commit ID")

    base_sha = resolve_commit(root, args.base_sha, "base SHA")
    base_branch_sha = resolve_commit(root, args.base_branch, "base branch/ref")
    ancestor = run(["git", "-C", str(root), "merge-base", "--is-ancestor", base_sha, "HEAD"], check=False)
    if ancestor.returncode == 1:
        raise ReviewError(f"base SHA is not an ancestor of HEAD: {base_sha}")
    if ancestor.returncode != 0:
        raise ReviewError((ancestor.stderr or ancestor.stdout).strip() or "cannot compare base SHA to HEAD")

    includes, external = split_includes(root, args.include)
    if not includes and not args.allow_full_scan:
        raise ReviewError(
            "scoped --include paths from the coder handoff are required for Standard Flow; "
            "use --allow-full-scan only for explicit diagnostics"
        )

    raw_tracked = git_paths(root, ["diff", "--name-only", base_sha], includes)
    effective_tracked, eol_only = classify_tracked(root, base_sha, raw_tracked)
    untracked = untracked_paths(root, includes)
    effective_paths = sorted(set(effective_tracked) | set(untracked))
    current_hash = scope_sha256(root, effective_paths)
    gate_ok, gate_reason = handoff_gate(root, effective_paths, current_hash)

    check_whitespace(root, base_sha, effective_tracked, untracked)

    print(f"WORKSPACE={root}")
    print(f"BRANCH={branch}")
    print(f"BASE_BRANCH={args.base_branch}")
    print(f"BASE_BRANCH_SHA={base_branch_sha}")
    print(f"BASE_SHA={base_sha}")
    print(f"BASE_BRANCH_DRIFTED={'true' if base_branch_sha != base_sha else 'false'}")
    print(f"SCAN_MODE={'scoped' if includes else 'full-diagnostic'}")
    print(f"SCOPE={','.join(args.include) if args.include else 'ALL'}")
    print(f"PRIMARY_SCOPE={','.join(includes) if includes else 'ALL'}")
    print(f"TRACKED_CHANGED_COUNT={len(effective_tracked)}")
    for index, path in enumerate(effective_tracked, 1):
        print(f"TRACKED_{index}={path}")
    print(f"EOL_ONLY_COUNT={len(eol_only)}")
    for index, path in enumerate(eol_only, 1):
        print(f"EOL_ONLY_{index}={path}")
    print(f"UNTRACKED_COUNT={len(untracked)}")
    for index, path in enumerate(untracked, 1):
        print(f"UNTRACKED_{index}={path}")
    print(f"CURRENT_SCOPE_SHA256={current_hash}")
    print(f"CODER_HANDOFF_GATE={'PASS' if gate_ok else 'FAIL'}")
    print(f"CODER_HANDOFF_GATE_REASON={gate_reason}")
    print(f"VERIFICATION_REUSE_ELIGIBLE={'true' if gate_ok else 'false'}")
    print(f"REVIEWER_TEST_RERUN_REQUIRED={'false' if gate_ok else 'true'}")
    if gate_ok:
        print(f"EFFECTIVE_SCOPE_SHA256={current_hash}")
    print(f"EXTERNAL_INCLUDE_COUNT={len(external)}")
    for index, path in enumerate(external, 1):
        print(f"EXTERNAL_INCLUDE_{index}={path}")
    if external:
        print(f"EXTERNAL_SCOPE_SHA256={external_sha256(external)}")
        print("EXTERNAL_SCOPE_POLICY=docs-or-secondary-workspace;do-not-invalidate-primary-executable-verification")
    print("RERUN_POLICY=minimal-once;no-rerun-tasks-for-confidence")
    print("DIFF_CHECK=PASS")
    print("GIT_SAFE_DIRECTORY=true")
    print("STATUS=valid")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReviewError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
