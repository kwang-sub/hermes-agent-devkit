#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

SKIP_DIRS = {".git", ".hermes", ".worktrees", "node_modules", ".next", ".next-hermes", "dist", "build", "coverage", "target"}
MAX_DEPTH = 3
INSTALL_TIMEOUT_SECONDS = 600
MANIFEST_SECTIONS = (
    ("dependencies", "DECLARED_PROD"),
    ("devDependencies", "DECLARED_DEV"),
    ("peerDependencies", "DECLARED_PEER"),
    ("optionalDependencies", "DECLARED_OPTIONAL"),
)


class PreflightError(RuntimeError):
    pass


def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PreflightError(f"cannot read package manifest: {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise PreflightError(f"invalid package.json: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise PreflightError(f"package.json must contain an object: {path}")
    return data


def safe_resolve_under(root: Path, value: Path) -> Path:
    root = root.resolve()
    resolved = value.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PreflightError(f"package root is outside workspace: {resolved}") from exc
    return resolved


def discover_package_roots(workspace: Path) -> list[Path]:
    found: list[Path] = []
    for root_text, dirs, files in os.walk(workspace):
        root = Path(root_text)
        relative = root.relative_to(workspace)
        depth = len(relative.parts)
        dirs[:] = sorted(
            name for name in dirs
            if name not in SKIP_DIRS and not name.startswith(".")
        )
        if depth >= MAX_DEPTH:
            dirs[:] = []
        if "package.json" in files:
            found.append(root.resolve())
    return sorted(found)


def resolve_package_root(workspace: Path, explicit: str | None) -> Path:
    if explicit:
        candidate = Path(explicit).expanduser()
        if not candidate.is_absolute():
            candidate = workspace / candidate
        package_root = safe_resolve_under(workspace, candidate)
        if not (package_root / "package.json").is_file():
            raise PreflightError(f"package.json not found at approved package root: {package_root}")
        return package_root

    roots = discover_package_roots(workspace)
    if len(roots) != 1:
        rendered = ",".join(str(path.relative_to(workspace)) for path in roots) or "NONE"
        raise PreflightError(
            f"package root is ambiguous; pass --package-root explicitly: candidates={rendered}"
        )
    return roots[0]


def require_pnpm_toolchain(manifest: dict) -> tuple[str, str]:
    dev_engines = manifest.get("devEngines")
    if not isinstance(dev_engines, dict):
        raise PreflightError("package.json devEngines is required by the DevKit Node contract")

    runtime = dev_engines.get("runtime")
    if not isinstance(runtime, dict):
        raise PreflightError("devEngines.runtime must declare the project Node runtime")
    runtime_name = str(runtime.get("name", "")).strip()
    runtime_version = str(runtime.get("version", "")).strip()
    runtime_on_fail = str(runtime.get("onFail", "")).strip()
    if runtime_name != "node" or not runtime_version:
        raise PreflightError("devEngines.runtime must declare name=node and a version")
    if runtime_on_fail != "download":
        raise PreflightError("devEngines.runtime.onFail must be 'download'")

    manager = dev_engines.get("packageManager")
    if not isinstance(manager, dict):
        raise PreflightError("devEngines.packageManager must declare pnpm")
    manager_name = str(manager.get("name", "")).strip()
    manager_version = str(manager.get("version", "")).strip()
    manager_on_fail = str(manager.get("onFail", "")).strip()
    if manager_name != "pnpm" or not manager_version:
        raise PreflightError("devEngines.packageManager must declare pnpm and a version range")
    if manager_on_fail != "download":
        raise PreflightError("devEngines.packageManager.onFail must be 'download'")

    return runtime_version, manager_version


def run_version(command: list[str]) -> str:
    try:
        result = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    lines = (result.stdout or result.stderr).strip().splitlines()
    return lines[0].strip() if lines else ""


def package_name(spec: str) -> str:
    if spec.startswith("@"):
        if "@" in spec[1:]:
            return spec.rsplit("@", 1)[0]
        return spec
    if "@" in spec:
        return spec.rsplit("@", 1)[0]
    return spec


def manifest_state(manifest: dict, name: str) -> str:
    for section, state in MANIFEST_SECTIONS:
        values = manifest.get(section)
        if isinstance(values, dict) and name in values:
            return state
    return "ABSENT"


def node_modules_state(package_root: Path, name: str, state: str) -> str:
    target = package_root / "node_modules"
    for part in name.split("/"):
        target /= part
    if not target.exists():
        return "ABSENT"
    return "EXTRANEOUS_PRESENT" if state == "ABSENT" else "PRESENT_DECLARED"


def build_install_command(dependency_type: str, packages: list[str]) -> str:
    quoted = " ".join(shlex.quote(item) for item in packages)
    prefix = "pnpm add -D" if dependency_type == "dev" else "pnpm add"
    return f"{prefix} {quoted}".strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the DevKit pnpm/Node contract before dependency mutation"
    )
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--package-root")
    parser.add_argument("--dependency-type", choices=("prod", "dev"), default="prod")
    parser.add_argument("--package", action="append", dest="packages", required=True)
    args = parser.parse_args()

    try:
        workspace = Path(args.workspace).expanduser().resolve()
        if not workspace.is_dir():
            raise PreflightError(f"workspace not found: {workspace}")

        package_root = resolve_package_root(workspace, args.package_root)
        manifest = read_json(package_root / "package.json")
        node_requirement, pnpm_requirement = require_pnpm_toolchain(manifest)

        pnpm_binary = shutil.which("pnpm")
        if not pnpm_binary:
            raise PreflightError("standalone pnpm is unavailable in the DevKit runtime")
        bootstrap_pnpm_version = run_version([pnpm_binary, "--version"])
        if not bootstrap_pnpm_version:
            raise PreflightError("cannot determine standalone pnpm version")

        lock_path = package_root / "pnpm-lock.yaml"
        lock_present = lock_path.is_file()

        dependency_rows: list[tuple[str, str, str, str]] = []
        for spec in args.packages:
            name = package_name(spec)
            state = manifest_state(manifest, name)
            modules_state = node_modules_state(package_root, name, state)
            dependency_rows.append((spec, name, state, modules_state))

        install_required = any(row[2] == "ABSENT" for row in dependency_rows)
        restore_required = any(row[2] != "ABSENT" and row[3] == "ABSENT" for row in dependency_rows)
        install_command = (
            build_install_command(args.dependency_type, args.packages)
            if install_required else "NOT_REQUIRED"
        )

        print(f"WORKSPACE={workspace}")
        print(f"PACKAGE_ROOT={package_root}")
        print("PACKAGE_MANAGER_ROOT=" + str(package_root))
        print("PACKAGE_MANAGER=pnpm")
        print("PACKAGE_MANAGER_SOURCE=package.json devEngines.packageManager")
        print(f"PACKAGE_MANAGER_BOOTSTRAP_VERSION={bootstrap_pnpm_version}")
        print(f"PACKAGE_MANAGER_REQUIRED_VERSION={pnpm_requirement}")
        print(f"CANONICAL_LOCKFILE={lock_path}")
        print(f"LOCKFILE_PRESENT={'true' if lock_present else 'false'}")
        print("NODE_VERSION=managed-by-pnpm")
        print(f"NODE_REQUIREMENT={node_requirement}")
        print("NODE_REQUIREMENT_SOURCE=package.json devEngines.runtime")
        print("NODE_REQUIREMENT_CHECK=pnpm-managed")
        for index, (spec, name, state, modules_state) in enumerate(dependency_rows, start=1):
            print(f"DEPENDENCY_{index}_SPEC={spec}")
            print(f"DEPENDENCY_{index}_NAME={name}")
            print(f"DEPENDENCY_{index}_MANIFEST_STATE={state}")
            print(f"DEPENDENCY_{index}_NODE_MODULES_STATE={modules_state}")
        print(f"INSTALL_REQUIRED={'true' if install_required else 'false'}")
        print(f"RESTORE_REQUIRED={'true' if restore_required else 'false'}")
        print(f"INSTALL_COMMAND={install_command}")
        print(f"INSTALL_TIMEOUT_SECONDS={INSTALL_TIMEOUT_SECONDS}")
        print("STATUS=pass")
        return 0
    except PreflightError as exc:
        print(f"ERROR={exc}", file=sys.stderr)
        print("STATUS=blocked", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
