#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from node_workspace import (
    DEFAULT_ROOT,
    WorkspaceError,
    prepare_isolated_package,
    resolve_cwd,
    resolve_package_root,
    workspace_key,
)


DEFAULT_LOCK_TIMEOUT = int(os.getenv("HERMES_NODE_WORKSPACE_LOCK_TIMEOUT_SECONDS", "600"))
PNPM_MUTATING_SUBCOMMANDS = {"i", "install", "add", "remove", "rm", "update", "dlx"}


class RuntimeErrorPolicy(RuntimeError):
    pass


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        description="Run pnpm verification in the Linux-only Hermes Node workspace."
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


def read_manifest(package_root: Path) -> dict:
    path = package_root / "package.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeErrorPolicy(f"cannot read valid package.json: {path}: {exc}") from exc
    if not isinstance(manifest, dict):
        raise RuntimeErrorPolicy(f"package.json root must be an object: {path}")
    return manifest


def resolve_project_toolchain(manifest: dict) -> tuple[str, str]:
    dev_engines = manifest.get("devEngines")
    if not isinstance(dev_engines, dict):
        raise RuntimeErrorPolicy(
            "package.json must declare devEngines.runtime and devEngines.packageManager for the DevKit pnpm toolchain"
        )

    runtime_value = dev_engines.get("runtime")
    runtime_entries = runtime_value if isinstance(runtime_value, list) else [runtime_value]
    node_entries = [
        item
        for item in runtime_entries
        if isinstance(item, dict) and str(item.get("name", "")).strip() == "node"
    ]
    if len(node_entries) != 1:
        raise RuntimeErrorPolicy(
            "package.json devEngines.runtime must declare exactly one Node runtime"
        )
    node_entry = node_entries[0]
    node_version = str(node_entry.get("version", "")).strip()
    if not node_version:
        raise RuntimeErrorPolicy("package.json devEngines.runtime Node version is missing")
    if str(node_entry.get("onFail", "")).strip() != "download":
        raise RuntimeErrorPolicy(
            "package.json devEngines.runtime Node onFail must be 'download'"
        )

    manager = dev_engines.get("packageManager")
    if not isinstance(manager, dict):
        raise RuntimeErrorPolicy(
            "package.json devEngines.packageManager must declare pnpm"
        )
    if str(manager.get("name", "")).strip() != "pnpm":
        raise RuntimeErrorPolicy(
            "package.json devEngines.packageManager.name must be 'pnpm'"
        )
    pnpm_version = str(manager.get("version", "")).strip()
    if not pnpm_version:
        raise RuntimeErrorPolicy(
            "package.json devEngines.packageManager pnpm version is missing"
        )
    if str(manager.get("onFail", "")).strip() != "download":
        raise RuntimeErrorPolicy(
            "package.json devEngines.packageManager pnpm onFail must be 'download'"
        )
    return node_version, pnpm_version


def command_basename(command: list[str]) -> str:
    return Path(command[0]).name.lower()


def validate_pnpm_command(command: list[str]) -> None:
    entry = command_basename(command)
    if entry not in {"pnpm", "pn"}:
        raise RuntimeErrorPolicy(
            f"only pnpm verification commands are supported by the DevKit Node runtime, got: {entry}"
        )

    subcommand = ""
    for token in command[1:]:
        if token.startswith("-"):
            continue
        subcommand = token.lower()
        break
    if subcommand in PNPM_MUTATING_SUBCOMMANDS:
        raise RuntimeErrorPolicy(
            f"dependency mutation 'pnpm {subcommand}' must run through dev-node-dependencies/Tirith, not node_runtime.py"
        )


def runtime_environment(paths: dict[str, Path]) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "HERMES_NODE_ROOT": str(paths["node_root"]),
            "PNPM_HOME": str(paths["pnpm_home"]),
            "PNPM_STORE_DIR": str(paths["pnpm_store"]),
            "npm_config_store_dir": str(paths["pnpm_store"]),
            "XDG_CACHE_HOME": str(paths["xdg_cache"]),
            "TMPDIR": str(paths["tmp"]),
            "NODE_REPL_HISTORY": str(paths["package_state"] / "node_repl_history"),
        }
    )
    # Managed pnpm versions live in the persistent PNPM_HOME. The image bootstrap
    # remains later on PATH as the fallback entrypoint that resolves devEngines.
    env["PATH"] = f"{paths['pnpm_home']}:{env.get('PATH', '')}"
    return env


def acquire_lock(lock_path: Path, timeout: int):
    if timeout < 1:
        raise RuntimeErrorPolicy("lock timeout must be >= 1 second")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
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
        source_cwd = resolve_cwd(workspace, args.cwd)
        source_package_root = resolve_package_root(workspace, source_cwd)
        validate_pnpm_command(command)

        root = Path(os.getenv("HERMES_NODE_ROOT", str(DEFAULT_ROOT))).expanduser().resolve()
        key = workspace_key(workspace)
        lock_path = root / "locks" / f"workspace-{key}.lock"
        lock_handle = acquire_lock(lock_path, args.lock_timeout)
        try:
            paths = prepare_isolated_package(
                workspace,
                source_package_root,
                root=root,
            )
            isolated_package_root = paths["isolated_package_root"]
            node_requirement, pnpm_requirement = resolve_project_toolchain(
                read_manifest(isolated_package_root)
            )
            env = runtime_environment(paths)

            print(f"NODE_RUNTIME_WORKSPACE={workspace}")
            print(f"NODE_RUNTIME_SOURCE_PACKAGE_ROOT={source_package_root}")
            print(f"NODE_RUNTIME_CWD={isolated_package_root}")
            print(f"NODE_RUNTIME_NODE_REQUIREMENT={node_requirement}")
            print(f"NODE_RUNTIME_PNPM_REQUIREMENT={pnpm_requirement}")
            print(f"NODE_RUNTIME_STATE_ROOT={paths['workspace_state']}")
            print(f"NODE_RUNTIME_PACKAGE_STATE={paths['package_state']}")
            print(f"NODE_RUNTIME_STORE={paths['pnpm_store']}")
            print(f"NODE_RUNTIME_LOCK={lock_path}")
            print("NODE_RUNTIME_OUTPUT_POLICY=linux-isolated-workspace;workspace-serialized")
            sys.stdout.flush()

            result = subprocess.run(
                command,
                cwd=isolated_package_root,
                env=env,
                check=False,
            )
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
            lock_handle.close()
        return result.returncode
    except (RuntimeErrorPolicy, WorkspaceError) as exc:
        print(f"NODE_RUNTIME_STATUS=BLOCKED\nNODE_RUNTIME_BLOCKER={exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"NODE_RUNTIME_STATUS=BLOCKED\nNODE_RUNTIME_BLOCKER={type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
