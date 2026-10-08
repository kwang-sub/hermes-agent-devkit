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


_TASK_LIB = Path(__file__).resolve().parents[3] / "_lib"
if str(_TASK_LIB) not in sys.path:
    sys.path.insert(0, str(_TASK_LIB))
from task_handoff import handoff_path, clear_handoff, save_handoff
from task_scope import semantic_tracked_paths, scope_sha256 as shared_scope_sha256, ScopeError


class SummaryError(RuntimeError):
    pass


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, text=True, capture_output=True)
    if check and result.returncode != 0:
        raise SummaryError((result.stderr or result.stdout).strip() or "command failed")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize scoped Git changes for implementation verification.")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--version-control", choices=("git", "none"), default="git")
    parser.add_argument("--task-id", help="Task-scoped Handoff; mandatory in active worker contract")
    parser.add_argument("--include", action="append", default=[])
    parser.add_argument("--allow-full-scan", action="store_true", help="Explicit diagnostic mode only. Allows repository-wide change discovery.")
    parser.add_argument("--check-only", action="store_true", help="Run fast scoped checks without changing any handoff state")
    parser.add_argument("--compact", action="store_true", help="Print only handoff-critical summary fields without changing the process exit code.")
    return parser.parse_args()


def repo_root(workspace: Path) -> Path:
    top = run(["git", "-C", str(workspace), "rev-parse", "--show-toplevel"]).stdout.strip()
    root = Path(top).resolve()
    if root != workspace.resolve():
        raise SummaryError(f"workspace must be repository root: workspace={workspace.resolve()}, root={root}")
    return root


def normalize_includes(root: Path, values: list[str]) -> list[str]:
    normalized: list[str] = []
    for raw in values:
        candidate = (root / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
        try:
            relative = candidate.relative_to(root)
        except ValueError as exc:
            raise SummaryError(f"included path is outside workspace: {raw}; summarize each Git workspace separately") from exc
        normalized.append(relative.as_posix())
    return sorted(dict.fromkeys(normalized))


def git_paths(root: Path, base: list[str], includes: list[str]) -> list[str]:
    cmd = ["git", "-C", str(root), *base]
    if includes:
        cmd.extend(["--", *includes])
    return [line.strip() for line in run(cmd).stdout.splitlines() if line.strip()]


def tracked_changes(root: Path, includes: list[str]) -> tuple[list[str], list[str]]:
    raw = git_paths(root, ["diff", "--name-only", "HEAD"], includes)
    try:
        effective = semantic_tracked_paths(root, "HEAD", raw)
    except ScopeError as exc:
        raise SummaryError(str(exc)) from exc
    eol_only = sorted(set(raw) - set(effective))
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
    raise SummaryError("CRLF-aware diff checker is unavailable; rebuild/update the DevKit runtime")


def check_whitespace(root: Path, tracked: list[str], untracked: list[str]) -> list[str]:
    cmd = [*diff_checker_command(), "--repo", str(root), "--base", "HEAD"]
    for path in tracked:
        cmd.extend(["--tracked", path])
    for path in untracked:
        cmd.extend(["--untracked", path])
    result = run(cmd, check=False)
    if result.returncode not in (0, 1):
        raise SummaryError((result.stderr or result.stdout).strip() or "CRLF-aware diff checker failed")
    return [line.split("=", 1)[1] for line in result.stdout.splitlines() if re.match(r"^WHITESPACE_ERROR_\d+=", line)]


def effective_scope_sha256(root: Path, paths: list[str]) -> str:
    return shared_scope_sha256(root, paths)


def handoff_state_path(root: Path, task_id: str | None = None) -> Path:
    return handoff_path(root, task_id)


def clear_handoff_state(root: Path, task_id: str | None = None) -> None:
    clear_handoff(root, task_id)


def write_handoff_state(
    root: Path, includes: list[str], effective_paths: list[str],
    fingerprint: str, task_id: str | None = None,
) -> None:
    save_handoff(
        root, scope=includes, effective_paths=effective_paths,
        fingerprint=fingerprint, task_id=task_id,
    )


def print_summary(*, root: Path, includes: list[str], scan_mode: str, tracked: list[str], eol_only: list[str], untracked: list[str], fingerprint: str, whitespace_errors: list[str], compact: bool) -> None:
    print(f"WORKSPACE={root}")
    print(f"SCOPE={','.join(includes) if includes else 'ALL'}")
    print(f"SCAN_MODE={scan_mode}")
    print(f"TRACKED_CHANGED_COUNT={len(tracked)}")
    if not compact:
        for index, path in enumerate(tracked, start=1): print(f"TRACKED_{index}={path}")
    print(f"EOL_ONLY_COUNT={len(eol_only)}")
    if not compact:
        for index, path in enumerate(eol_only, start=1): print(f"EOL_ONLY_{index}={path}")
    print(f"UNTRACKED_COUNT={len(untracked)}")
    if not compact:
        for index, path in enumerate(untracked, start=1): print(f"UNTRACKED_{index}={path}")
    print(f"EFFECTIVE_SCOPE_SHA256={fingerprint}")
    print(f"WHITESPACE_ERROR_COUNT={len(whitespace_errors)}")
    if whitespace_errors:
        if not compact:
            for index, error in enumerate(whitespace_errors, start=1): print(f"WHITESPACE_ERROR_{index}={error.replace(chr(10), ' | ')}")
        print("HANDOFF_GATE=FAIL"); print("STATUS=invalid")
    else:
        print("HANDOFF_GATE=PASS"); print("STATUS=valid")


def main() -> int:
    args = parse_args()
    workspace = Path(args.workspace).resolve()
    if not workspace.is_dir():
        raise SummaryError(f"workspace does not exist or is not a directory: {workspace}")

    if args.version_control == "none":
        includes = normalize_includes(workspace, args.include)
        if not includes:
            raise SummaryError(
                "declared --include paths are required for a Non-Git workspace; "
                "Hermes does not infer or snapshot Non-Git changes"
            )
        print(f"WORKSPACE={workspace}")
        print("VERSION_CONTROL=none")
        print(f"SCOPE={','.join(includes)}")
        print("SCAN_MODE=unsupported-non-git")
        print("CHANGE_TRACKING=unsupported")
        print(f"DECLARED_CHANGED_COUNT={len(includes)}")
        if not args.compact:
            for index, path in enumerate(includes, start=1):
                print(f"DECLARED_CHANGED_{index}={path}")
        print("TRACKED_CHANGED_COUNT=-1")
        print("EOL_ONLY_COUNT=-1")
        print("UNTRACKED_COUNT=-1")
        print("WHITESPACE_ERROR_COUNT=-1")
        print("HANDOFF_GATE=NOT_APPLICABLE")
        print("STATUS=valid")
        return 0

    root = repo_root(workspace)
    if not args.check_only:
        clear_handoff_state(root, args.task_id)
    includes = normalize_includes(root, args.include)
    if not includes and not args.allow_full_scan:
        raise SummaryError("scoped --include paths are required for Standard Flow; use --allow-full-scan only for explicit diagnostics")

    scan_mode = "scoped" if includes else "full-diagnostic"
    tracked, eol_only = tracked_changes(root, includes)
    untracked = untracked_paths(root, includes)
    whitespace_errors = check_whitespace(root, tracked, untracked)
    effective_paths = sorted(set(tracked) | set(untracked))
    fingerprint = effective_scope_sha256(root, effective_paths)

    print("VERSION_CONTROL=git")
    print_summary(root=root, includes=includes, scan_mode=scan_mode, tracked=tracked, eol_only=eol_only, untracked=untracked, fingerprint=fingerprint, whitespace_errors=whitespace_errors, compact=args.compact)
    if whitespace_errors:
        return 1
    if args.check_only:
        print("PREFLIGHT_SCOPE_ONLY=true")
    else:
        write_handoff_state(root, includes, effective_paths, fingerprint, args.task_id)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SummaryError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
