#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


MANAGED_MARKER = "# managed-by: dev-project-bootstrap"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh technology stack cache for bootstrap-managed repositories under a root"
    )
    parser.add_argument("--root", required=True, help="Directory containing managed Git repositories")
    parser.add_argument("--max-depth", type=int, default=5)
    return parser.parse_args()


def managed_repo(metadata: Path) -> bool:
    try:
        lines = metadata.read_text(encoding="utf-8").splitlines()[:5]
    except OSError:
        return False
    return MANAGED_MARKER in lines and (metadata.parent.parent / ".git").exists()


def discover(root: Path, max_depth: int) -> list[Path]:
    root = root.resolve()
    repos: list[Path] = []
    for metadata in root.glob("**/.hermes/project.yaml"):
        try:
            relative = metadata.relative_to(root)
        except ValueError:
            continue
        repo_depth = max(0, len(relative.parts) - 2)
        if repo_depth > max_depth:
            continue
        if managed_repo(metadata):
            repos.append(metadata.parent.parent.resolve())
    return sorted(set(repos), key=lambda path: path.as_posix())


def main() -> int:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(f"ERROR=root not found: {root}", file=sys.stderr)
        return 2
    if args.max_depth < 0 or args.max_depth > 12:
        print("ERROR=--max-depth must be 0..12", file=sys.stderr)
        return 2

    bootstrap = Path(__file__).resolve().parent / "bootstrap.py"
    repos = discover(root, args.max_depth)
    failed = 0

    for repo in repos:
        print(f"[REFRESH] {repo}")
        result = subprocess.run(
            [sys.executable, "-u", str(bootstrap), "--repo", str(repo), "--refresh-stack"],
            text=True,
        )
        if result.returncode != 0:
            failed += 1
            print(f"[FAIL] {repo}")
        else:
            print(f"[PASS] {repo}")

    print(f"REFRESH_STACK_REPOSITORIES={len(repos)}")
    print(f"REFRESH_STACK_FAILED={failed}")
    print("STATUS=pass" if failed == 0 else "STATUS=failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
