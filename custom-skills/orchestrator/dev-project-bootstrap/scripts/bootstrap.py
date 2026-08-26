#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess
import sys


class BootstrapLauncherError(RuntimeError):
    pass


def repo_arg(argv: list[str]) -> str:
    for index, value in enumerate(argv):
        if value == "--repo":
            try:
                return argv[index + 1]
            except IndexError as exc:
                raise BootstrapLauncherError("--repo requires a value") from exc
        if value.startswith("--repo="):
            return value.split("=", 1)[1]
    raise BootstrapLauncherError("--repo is required")


def run(cmd: list[str]) -> None:
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise BootstrapLauncherError(
            f"bootstrap stage failed ({result.returncode}): {' '.join(cmd)}"
        )


def main() -> int:
    scripts = Path(__file__).resolve().parent
    repo = repo_arg(sys.argv[1:])

    run([
        sys.executable,
        str(scripts / "dev_environment_preflight.py"),
        "--repo",
        repo,
    ])
    run([
        sys.executable,
        str(scripts / "bootstrap_project.py"),
        *sys.argv[1:],
    ])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BootstrapLauncherError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
