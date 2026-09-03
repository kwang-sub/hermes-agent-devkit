#!/usr/bin/env python3
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Iterator


HERMES_CLI_CANDIDATES = (
    Path("/usr/local/bin/hermes"),
    Path("/opt/hermes/.venv/bin/hermes"),
    Path("/opt/hermes/bin/hermes"),
    Path("/opt/hermes-agent/.venv/bin/hermes"),
    Path("/opt/data/hermes-agent/.venv/bin/hermes"),
    Path("/root/.local/bin/hermes"),
    Path("/home/hermes/.local/bin/hermes"),
)
FULL_PREFLIGHT_FLAG = "--full-preflight"


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


def project_args(argv: list[str]) -> list[str]:
    return [value for value in argv if value != FULL_PREFLIGHT_FLAG]


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
    env["PYTHONUNBUFFERED"] = "1"
    return env


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    result = subprocess.run(cmd, env=env)
    if result.returncode != 0:
        raise BootstrapLauncherError(
            f"bootstrap stage failed ({result.returncode}): {' '.join(cmd)}"
        )


def python_stage(script: Path, *args: str) -> list[str]:
    return [sys.executable, "-u", str(script), *args]


def lock_path(repo: str) -> Path:
    resolved = str(Path(repo).resolve())
    digest = hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:16]
    return Path("/tmp") / f"hermes-bootstrap-{digest}.lock"


@contextmanager
def bootstrap_lock(repo: str) -> Iterator[None]:
    path = lock_path(repo)
    handle = path.open("a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise BootstrapLauncherError(
                "bootstrap is already running for this repository; "
                "poll the existing process instead of starting another one: "
                f"{Path(repo).resolve()}"
            ) from exc
        handle.seek(0)
        handle.truncate()
        handle.write(f"pid={os.getpid()}\nrepo={Path(repo).resolve()}\n")
        handle.flush()
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def main() -> int:
    scripts = Path(__file__).resolve().parent
    launcher_args = sys.argv[1:]
    repo = repo_arg(launcher_args)
    full_preflight = FULL_PREFLIGHT_FLAG in launcher_args
    forwarded_args = project_args(launcher_args)
    hermes_cli = resolve_hermes_cli()
    env = child_env(hermes_cli)

    print(f"[OK] Hermes CLI: {hermes_cli}", flush=True)
    print(
        f"[INFO] Bootstrap preflight: {'full' if full_preflight else 'fast'}",
        flush=True,
    )

    with bootstrap_lock(repo):
        preflight_args = ["--repo", repo]
        if full_preflight:
            preflight_args.append("--full")
        run(
            python_stage(scripts / "bootstrap_preflight.py", *preflight_args),
            env=env,
        )
        run(
            python_stage(scripts / "ensure_gitignore.py", "--repo", repo),
            env=env,
        )
        run(
            python_stage(scripts / "bootstrap_project.py", *forwarded_args),
            env=env,
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BootstrapLauncherError as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1)
