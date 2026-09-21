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
PNPM_MUTATING_SUBCOMMANDS = {"i", "install", "add", "remove", "rm", "update", "dlx"}
KNOWN_OUTPUTS = (".next-hermes", "dist", "build", "coverage", "node_modules/.cache")


class RuntimeErrorPolicy(RuntimeError):
    pass


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        description="Run pnpm-based Node/frontend verification with isolated DevKit state."
    )
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--cwd", default=".", help="Command cwd relative to workspace (default: workspace root)")
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


def resolve_package_root(cwd: Path, workspace: Path) -> Path:
    current = cwd
    while True:
        if (current / "package.json").is_file():
            return current
        if current == workspace:
            break
        if workspace not in current.parents:
            break
        current = current.parent
    raise RuntimeErrorPolicy(
        f"package.json was not found between command cwd and workspace root: cwd={cwd}, workspace={workspace}"
    )


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


def workspace_key(workspace: Path) -> str:
    digest = hashlib.sha256(str(workspace).encode("utf-8")).hexdigest()[:16]
    name = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in workspace.name) or "workspace"
    return f"{name}-{digest}"


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


def internal_environment(root: Path, key: str) -> tuple[dict[str, str], dict[str, Path]]:
    workspace_state = root / "workspaces" / key
    paths = {
        "node_root": root,
        "lock_root": root / "locks",
        "workspace_state": workspace_state,
        "pnpm_home": root / "pnpm-home",
        "pnpm_store": root / "pnpm-store",
        "xdg_cache": root / "cache",
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
            "HERMES_NEXT_DIST_DIR": ".next-hermes",
        }
    )
    env["PATH"] = f"{paths['pnpm_home']}:{env.get('PATH', '')}"
    return env, paths


def check_workspace_outputs(package_root: Path) -> None:
    for relative in KNOWN_OUTPUTS:
        path = package_root / relative
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
        package_root = resolve_package_root(cwd, workspace)
        node_requirement, pnpm_requirement = resolve_project_toolchain(read_manifest(package_root))
        validate_pnpm_command(command)

        key = workspace_key(workspace)
        root = Path(os.getenv("HERMES_NODE_ROOT", str(DEFAULT_ROOT))).expanduser().resolve()
        env, paths = internal_environment(root, key)
        check_workspace_outputs(package_root)
        lock_path = paths["lock_root"] / f"workspace-{key}.lock"

        print(f"NODE_RUNTIME_WORKSPACE={workspace}")
        print(f"NODE_RUNTIME_CWD={cwd}")
        print(f"NODE_RUNTIME_PACKAGE_ROOT={package_root}")
        print(f"NODE_RUNTIME_NODE_REQUIREMENT={node_requirement}")
        print(f"NODE_RUNTIME_PNPM_REQUIREMENT={pnpm_requirement}")
        print(f"NODE_RUNTIME_STATE_ROOT={paths['workspace_state']}")
        print(f"NODE_RUNTIME_STORE={paths['pnpm_store']}")
        print(f"NODE_RUNTIME_LOCK={lock_path}")
        print("NODE_RUNTIME_NEXT_DIST_DIR=.next-hermes")
        print("NODE_RUNTIME_OUTPUT_POLICY=pnpm-managed;workspace-serialized;next-dist-isolated")
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
