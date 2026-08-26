#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys


HERMES_CLI_CANDIDATES = (
    Path("/usr/local/bin/hermes"),
    Path("/opt/hermes/.venv/bin/hermes"),
    Path("/opt/hermes/bin/hermes"),
    Path("/opt/hermes-agent/.venv/bin/hermes"),
    Path("/opt/data/hermes-agent/.venv/bin/hermes"),
    Path("/root/.local/bin/hermes"),
    Path("/home/hermes/.local/bin/hermes"),
)


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


def resolve_hermes_cli() -> Path:
    explicit = os.getenv("HERMES_CLI", "").strip()
    if explicit:
        candidate = Path(explicit)
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
        raise BootstrapLauncherError(
            f"HERMES_CLI is set but is not executable: {candidate}"
        )

    discovered = shutil.which("hermes")
    if discovered:
        return Path(discovered)

    for candidate in HERMES_CLI_CANDIDATES:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate

    raise BootstrapLauncherError(
        "Hermes CLI was not found on PATH or at any known DevKit location: "
        + ", ".join(str(path) for path in HERMES_CLI_CANDIDATES)
    )


def child_env(hermes_cli: Path) -> dict[str, str]:
    env = os.environ.copy()
    cli_dir = str(hermes_cli.parent)
    path_parts = [part for part in env.get("PATH", "").split(os.pathsep) if part]
    if cli_dir not in path_parts:
        env["PATH"] = os.pathsep.join([cli_dir, *path_parts])
    env["HERMES_CLI"] = str(hermes_cli)
    return env


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    result = subprocess.run(cmd, env=env)
    if result.returncode != 0:
        raise BootstrapLauncherError(
            f"bootstrap stage failed ({result.returncode}): {' '.join(cmd)}"
        )


def main() -> int:
    scripts = Path(__file__).resolve().parent
    repo = repo_arg(sys.argv[1:])
    hermes_cli = resolve_hermes_cli()
    env = child_env(hermes_cli)

    print(f"[OK] Hermes CLI: {hermes_cli}")

    run([
        sys.executable,
        str(scripts / "dev_environment_preflight.py"),
        "--repo",
        repo,
    ], env=env)
    run([
        sys.executable,
        str(scripts / "bootstrap_project.py"),
        *sys.argv[1:],
    ], env=env)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BootstrapLauncherError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
