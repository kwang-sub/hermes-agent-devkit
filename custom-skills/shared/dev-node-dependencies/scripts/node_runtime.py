#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

DEFAULT_ROOT = Path(os.getenv("HERMES_NODE_ROOT", "/opt/data/node"))
DEFAULT_LOCK_TIMEOUT = int(os.getenv("HERMES_NODE_WORKSPACE_LOCK_TIMEOUT_SECONDS", "600"))
KNOWN_OUTPUTS = (".next", ".next-hermes", "dist", "build", "coverage", "node_modules/.cache")


class RuntimeErrorPolicy(RuntimeError):
    pass


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        description="Run pnpm/Node project commands with DevKit-isolated state and a workspace lock."
    )
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--cwd", default=".", help="Command cwd relative to workspace")
    parser.add_argument("--lock-timeout", type=int, default=DEFAULT_LOCK_TIMEOUT)
    args, command = parser.parse_known_args()
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("a command is required after --")
    return args, command


def resolve_cwd(workspace: Path, raw: str) -> Path:
    candidate = Path(raw)
    path = candidate.resolve() if candidate.is_absolute() else (workspace / candidate).resolve()
    try:
        path.relative_to(workspace)
    except ValueError as exc:
        raise RuntimeErrorPolicy(f"command cwd escapes workspace: {path}") from exc
    if not path.is_dir():
        raise RuntimeErrorPolicy(f"command cwd does not exist: {path}")
    return path


def workspace_key(workspace: Path) -> str:
    digest = hashlib.sha256(str(workspace).encode("utf-8")).hexdigest()[:16]
    name = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in workspace.name) or "workspace"
    return f"{name}-{digest}"


def read_manifest(cwd: Path) -> dict:
    path = cwd / "package.json"
    if not path.is_file():
        raise RuntimeErrorPolicy(f"package.json is required at Node package root: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeErrorPolicy(f"cannot read package.json: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeErrorPolicy(f"package.json root must be an object: {path}")
    return data


def require_pnpm_contract(manifest: dict) -> None:
    dev_engines = manifest.get("devEngines")
    if not isinstance(dev_engines, dict):
        raise RuntimeErrorPolicy("package.json devEngines is required by the DevKit pnpm contract")

    runtime = dev_engines.get("runtime")
    if not isinstance(runtime, dict):
        raise RuntimeErrorPolicy("package.json devEngines.runtime must declare the project Node runtime")
    if runtime.get("name") != "node" or not str(runtime.get("version", "")).strip():
        raise RuntimeErrorPolicy("devEngines.runtime must declare name=node and a non-empty version")
    if runtime.get("onFail") != "download":
        raise RuntimeErrorPolicy("devEngines.runtime.onFail must be 'download'")

    manager = dev_engines.get("packageManager")
    if not isinstance(manager, dict):
        raise RuntimeErrorPolicy("package.json devEngines.packageManager is required")
    if manager.get("name") != "pnpm" or not str(manager.get("version", "")).strip():
        raise RuntimeErrorPolicy("devEngines.packageManager must declare pnpm and a version range")
    if manager.get("onFail") != "download":
        raise RuntimeErrorPolicy("devEngines.packageManager.onFail must be 'download'")


def reject_dependency_mutation(command: list[str]) -> None:
    entry = Path(command[0]).name.lower()
    if entry not in {"pnpm", "pn"}:
        return
    subcommand = ""
    for token in command[1:]:
        if token.startswith("-"):
            continue
        subcommand = token.lower()
        break
    if subcommand in {"i", "install", "add", "remove", "rm", "update", "dlx"}:
        raise RuntimeErrorPolicy(
            f"dependency mutation '{entry} {subcommand}' must run through dev-node-dependencies/Tirith"
        )


def internal_environment(root: Path, key: str) -> tuple[dict[str, str], dict[str, Path]]:
    workspace_state = root / "workspaces" / key
    paths = {
        "node_root": root,
        "lock_root": root / "locks",
        "workspace_state": workspace_state,
        "pnpm_store": root / "pnpm-store",
        "pnpm_home": root / "pnpm-home",
        "xdg_cache": root / "xdg-cache",
        "tmp": workspace_state / "tmp",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
        if not os.access(path, os.W_OK):
            raise RuntimeErrorPolicy(f"internal Node state is not writable: {path}")

    env = os.environ.copy()
    env.update(
        {
            "HERMES_NODE_ROOT": str(root),
            "PNPM_HOME": str(paths["pnpm_home"]),
            "PNPM_STORE_DIR": str(paths["pnpm_store"]),
            "npm_config_store_dir": str(paths["pnpm_store"]),
            "XDG_CACHE_HOME": str(paths["xdg_cache"]),
            "TMPDIR": str(paths["tmp"]),
            "NODE_REPL_HISTORY": str(workspace_state / "node_repl_history"),
            "NEXT_DIST_DIR": ".next-hermes",
            "HERMES_NEXT_DIST_DIR": ".next-hermes",
        }
    )
    bootstrap_home = os.getenv("PNPM_HOME", "/opt/pnpm")
    env["PATH"] = os.pathsep.join(
        [str(paths["pnpm_home"]), bootstrap_home, env.get("PATH", "")]
    )
    return env, paths


def check_workspace_outputs(cwd: Path) -> None:
    for relative in KNOWN_OUTPUTS:
        path = cwd / relative
        if path.exists() and not os.access(path, os.W_OK):
            raise RuntimeErrorPolicy(f"workspace output is not writable: {path}")


def acquire_lock(lock_path: Path, timeout: int):
    if timeout < 1:
        raise RuntimeErrorPolicy("lock timeout must be >= 1 second")
    handle = lock_path.open("a+")
    deadline = time.monotonic() + timeout
    while True:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return handle
        except BlockingIOError:
            if time.monotonic() >= deadline:
                handle.close()
                raise RuntimeErrorPolicy(f"timed out waiting for Node workspace lock: {lock_path}")
            time.sleep(0.1)


def main() -> int:
    args, command = parse_args()
    try:
        workspace = Path(args.workspace).expanduser().resolve()
        if not workspace.is_dir():
            raise RuntimeErrorPolicy(f"workspace does not exist: {workspace}")
        cwd = resolve_cwd(workspace, args.cwd)
        require_pnpm_contract(read_manifest(cwd))
        reject_dependency_mutation(command)

        key = workspace_key(workspace)
        root = Path(os.getenv("HERMES_NODE_ROOT", str(DEFAULT_ROOT))).expanduser().resolve()
        env, paths = internal_environment(root, key)
        check_workspace_outputs(cwd)
        lock_path = paths["lock_root"] / f"workspace-{key}.lock"

        print(f"NODE_RUNTIME_WORKSPACE={workspace}")
        print(f"NODE_RUNTIME_CWD={cwd}")
        print(f"NODE_RUNTIME_STATE_ROOT={paths['workspace_state']}")
        print(f"NODE_RUNTIME_STORE={paths['pnpm_store']}")
        print(f"NODE_RUNTIME_LOCK={lock_path}")
        print("NODE_RUNTIME_PACKAGE_MANAGER=pnpm")
        print("NODE_RUNTIME_NEXT_DIST_DIR=.next-hermes")
        sys.stdout.flush()

        lock_handle = acquire_lock(lock_path, args.lock_timeout)
        try:
            result = subprocess.run(command, cwd=cwd, env=env, check=False)
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
            lock_handle.close()
        return result.returncode
    except RuntimeErrorPolicy as exc:
        print(f"NODE_RUNTIME_STATUS=BLOCKED\nNODE_RUNTIME_BLOCKER={exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"NODE_RUNTIME_STATUS=BLOCKED\nNODE_RUNTIME_BLOCKER={type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
