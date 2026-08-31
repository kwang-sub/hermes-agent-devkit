#!/usr/bin/env python3
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys


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
    parser.add_argument("--include", action="append", default=[])
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Print only handoff-critical summary fields without changing the process exit code.",
    )
    return parser.parse_args()


def repo_root(workspace: Path) -> Path:
    top = run(["git", "-C", str(workspace), "rev-parse", "--show-toplevel"]).stdout.strip()
    root = Path(top).resolve()
    if root != workspace.resolve():
        raise SummaryError(f"workspace must be repository root: workspace={workspace.resolve()}, root={root}")
    return root


def normalize_includes(root: Path, values: list[str]) -> list[str]:
    if not values:
        return []
    normalized: list[str] = []
    for raw in values:
        candidate = (root / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
        try:
            relative = candidate.relative_to(root)
        except ValueError as exc:
            raise SummaryError(
                f"included path is outside workspace: {raw}; summarize each Git workspace separately"
            ) from exc
        normalized.append(relative.as_posix())
    return sorted(dict.fromkeys(normalized))


def git_paths(root: Path, base: list[str], includes: list[str]) -> list[str]:
    cmd = ["git", "-C", str(root), *base]
    if includes:
        cmd.extend(["--", *includes])
    return [line.strip() for line in run(cmd).stdout.splitlines() if line.strip()]


def tracked_changes(root: Path, includes: list[str]) -> tuple[list[str], list[str]]:
    raw = git_paths(root, ["diff", "--name-only", "HEAD"], includes)
    effective: list[str] = []
    eol_only: list[str] = []
    for path in raw:
        result = run(
            ["git", "-C", str(root), "diff", "--quiet", "--ignore-cr-at-eol", "HEAD", "--", path],
            check=False,
        )
        if result.returncode == 0:
            eol_only.append(path)
        elif result.returncode == 1:
            effective.append(path)
        else:
            raise SummaryError(
                (result.stderr or result.stdout).strip()
                or f"cannot classify tracked change for {path}: rc={result.returncode}"
            )
    return effective, eol_only


def untracked_paths(root: Path, includes: list[str]) -> list[str]:
    all_untracked = git_paths(root, ["ls-files", "--others", "--exclude-standard"], [])
    if not includes:
        return all_untracked
    return [
        path for path in all_untracked
        if any(path == inc or path.startswith(f"{inc.rstrip('/')}/") for inc in includes)
    ]


def check_tracked_whitespace(root: Path, paths: list[str]) -> list[str]:
    if not paths:
        return []
    cmd = ["git", "-C", str(root), "diff", "--check", "--ignore-cr-at-eol", "HEAD", "--", *paths]
    result = run(cmd, check=False)
    output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
    if result.returncode not in (0, 1) or output:
        return [output or f"git diff --check failed with rc={result.returncode}"]
    return []


def check_untracked_whitespace(root: Path, paths: list[str]) -> list[str]:
    errors: list[str] = []
    for path in paths:
        result = run(
            ["git", "-C", str(root), "diff", "--no-index", "--check", "--", "/dev/null", path],
            check=False,
        )
        output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
        if result.returncode not in (0, 1):
            errors.append(output or f"untracked diff check failed for {path}: rc={result.returncode}")
        elif output:
            errors.append(output)
    return errors


def effective_scope_sha256(root: Path, paths: list[str]) -> str:
    digest = sha256()
    for path in sorted(dict.fromkeys(paths)):
        file_path = root / path
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        if file_path.is_file():
            content = file_path.read_bytes().replace(b"\r\n", b"\n")
            digest.update(b"F\0")
            digest.update(content)
        else:
            digest.update(b"MISSING\0")
        digest.update(b"\0")
    return digest.hexdigest()


def handoff_state_path(root: Path) -> Path:
    raw = run(["git", "-C", str(root), "rev-parse", "--git-path", "hermes/review-handoff.json"]).stdout.strip()
    path = Path(raw)
    return path if path.is_absolute() else (root / path).resolve()


def clear_handoff_state(root: Path) -> None:
    path = handoff_state_path(root)
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def write_handoff_state(
    root: Path,
    includes: list[str],
    effective_paths: list[str],
    fingerprint: str,
) -> None:
    path = handoff_state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "workspace": str(root),
        "scope": includes,
        "effective_paths": effective_paths,
        "effective_scope_sha256": fingerprint,
        "status": "valid",
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def print_summary(
    *,
    root: Path,
    includes: list[str],
    tracked: list[str],
    eol_only: list[str],
    untracked: list[str],
    fingerprint: str,
    whitespace_errors: list[str],
    compact: bool,
) -> None:
    print(f"WORKSPACE={root}")
    print(f"SCOPE={'ALL' if not includes else ','.join(includes)}")
    print(f"TRACKED_CHANGED_COUNT={len(tracked)}")
    if not compact:
        for index, path in enumerate(tracked, start=1):
            print(f"TRACKED_{index}={path}")
    print(f"EOL_ONLY_COUNT={len(eol_only)}")
    if not compact:
        for index, path in enumerate(eol_only, start=1):
            print(f"EOL_ONLY_{index}={path}")
    print(f"UNTRACKED_COUNT={len(untracked)}")
    if not compact:
        for index, path in enumerate(untracked, start=1):
            print(f"UNTRACKED_{index}={path}")
    print(f"EFFECTIVE_SCOPE_SHA256={fingerprint}")
    print(f"WHITESPACE_ERROR_COUNT={len(whitespace_errors)}")
    if whitespace_errors:
        if not compact:
            for index, error in enumerate(whitespace_errors, start=1):
                print(f"WHITESPACE_ERROR_{index}={error.replace(chr(10), ' | ')}")
        print("HANDOFF_GATE=FAIL")
        print("STATUS=invalid")
    else:
        print("HANDOFF_GATE=PASS")
        print("STATUS=valid")


def main() -> int:
    args = parse_args()
    root = repo_root(Path(args.workspace))
    clear_handoff_state(root)

    includes = normalize_includes(root, args.include)
    tracked, eol_only = tracked_changes(root, includes)
    untracked = untracked_paths(root, includes)
    whitespace_errors = check_tracked_whitespace(root, tracked) + check_untracked_whitespace(root, untracked)
    effective_paths = sorted(set(tracked) | set(untracked))
    fingerprint = effective_scope_sha256(root, effective_paths)

    print_summary(
        root=root,
        includes=includes,
        tracked=tracked,
        eol_only=eol_only,
        untracked=untracked,
        fingerprint=fingerprint,
        whitespace_errors=whitespace_errors,
        compact=args.compact,
    )

    if whitespace_errors:
        return 1

    write_handoff_state(root, includes, effective_paths, fingerprint)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SummaryError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
