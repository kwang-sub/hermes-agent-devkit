#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys


LOCKFILES = {
    "package-lock.json": "npm",
    "npm-shrinkwrap.json": "npm",
    "pnpm-lock.yaml": "pnpm",
    "yarn.lock": "yarn",
    "bun.lock": "bun",
    "bun.lockb": "bun",
}
DEFAULT_LOCKFILE = {
    "npm": "package-lock.json",
    "pnpm": "pnpm-lock.yaml",
    "yarn": "yarn.lock",
    "bun": "bun.lock",
}
PREFERRED_LOCKFILES = {
    "npm": ("npm-shrinkwrap.json", "package-lock.json"),
    "pnpm": ("pnpm-lock.yaml",),
    "yarn": ("yarn.lock",),
    "bun": ("bun.lock", "bun.lockb"),
}
SKIP_DIRS = {".git", ".hermes", ".worktrees", "node_modules", ".next", "dist", "build", "coverage", "target"}
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


def run_version(command: list[str]) -> str:
    try:
        result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    text = (result.stdout or result.stderr).strip().splitlines()
    return text[0].strip() if text else ""


def normalize_version(value: str) -> str:
    value = value.strip()
    if value.startswith("v"):
        value = value[1:]
    return value.split("+", 1)[0]


def major_of(value: str) -> int | None:
    match = re.search(r"(?:^|[^0-9])(\d+)(?:\.|$)", value.strip())
    return int(match.group(1)) if match else None


def simple_required_major(requirement: str) -> int | None:
    text = requirement.strip()
    if not text or "||" in text:
        return None
    patterns = (
        r"^v?(\d+)(?:\.\d+){0,2}(?:\.x)?$",
        r"^[~^]v?(\d+)(?:\.\d+){0,2}$",
        r"^>=?\s*v?(\d+)(?:\.\d+){0,2}\s+<\s*v?(\d+)(?:\.\d+){0,2}$",
    )
    for pattern in patterns:
        match = re.match(pattern, text)
        if not match:
            continue
        if len(match.groups()) == 2:
            low, high = int(match.group(1)), int(match.group(2))
            if high == low + 1:
                return low
            return None
        return int(match.group(1))
    return None


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


def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PreflightError(f"cannot read package manifest: {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise PreflightError(f"invalid package.json: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise PreflightError(f"package.json root must be an object: {path}")
    return data


def package_name(spec: str) -> str:
    spec = spec.strip()
    if not spec:
        raise PreflightError("empty package spec")
    if spec.startswith("@"):
        slash = spec.find("/")
        if slash <= 1:
            raise PreflightError(f"invalid scoped package spec: {spec}")
        version_at = spec.find("@", slash + 1)
        return spec if version_at < 0 else spec[:version_at]
    if any(spec.startswith(prefix) for prefix in ("file:", "git+", "http://", "https://", "github:")):
        raise PreflightError(f"non-registry package spec requires explicit project handling: {spec}")
    return spec.split("@", 1)[0]


def manifest_state(manifest: dict, name: str) -> str:
    for section, state in MANIFEST_SECTIONS:
        values = manifest.get(section)
        if isinstance(values, dict) and name in values:
            return state
    return "ABSENT"


def installed_package_path(package_root: Path, name: str) -> Path:
    if name.startswith("@"):
        scope, package = name.split("/", 1)
        return package_root / "node_modules" / scope / package / "package.json"
    return package_root / "node_modules" / name / "package.json"


def node_modules_state(package_root: Path, name: str, state: str) -> str:
    present = installed_package_path(package_root, name).is_file()
    if present and state == "ABSENT":
        return "EXTRANEOUS_PRESENT"
    if present:
        return "PRESENT_DECLARED"
    return "ABSENT"


def parse_package_manager_field(manifest: dict) -> tuple[str, str]:
    value = manifest.get("packageManager")
    if not isinstance(value, str) or not value.strip():
        return "", ""
    match = re.match(r"^(npm|pnpm|yarn|bun)@(.+)$", value.strip())
    if not match:
        raise PreflightError(f"unsupported packageManager value: {value}")
    return match.group(1), normalize_version(match.group(2))


def lockfiles_at(root: Path) -> dict[str, list[Path]]:
    result: dict[str, list[Path]] = {}
    for filename, manager in LOCKFILES.items():
        path = root / filename
        if path.is_file():
            result.setdefault(manager, []).append(path)
    return result


def resolve_manager_boundary(package_root: Path, workspace: Path) -> tuple[str, str, str, Path, bool, Path]:
    current = package_root
    while True:
        manifest_path = current / "package.json"
        manifest = read_json(manifest_path) if manifest_path.is_file() else {}
        field_manager, field_version = parse_package_manager_field(manifest)
        locks = lockfiles_at(current)
        if len(locks) > 1:
            detail = ", ".join(path.name for paths in locks.values() for path in paths)
            raise PreflightError(f"conflicting package manager lockfiles: {detail}")
        lock_manager = next(iter(locks), "")
        if field_manager or lock_manager:
            if field_manager and lock_manager and field_manager != lock_manager:
                raise PreflightError(
                    f"packageManager/lockfile mismatch: packageManager={field_manager}, lockfile_manager={lock_manager}"
                )
            manager = field_manager or lock_manager
            source = "packageManager" if field_manager else "lockfile"
            present_lockfile: Path | None = None
            if lock_manager:
                available = set(locks[lock_manager])
                for filename in PREFERRED_LOCKFILES[manager]:
                    candidate = current / filename
                    if candidate in available:
                        present_lockfile = candidate
                        break
            lock_path = present_lockfile or (current / DEFAULT_LOCKFILE[manager])
            return manager, source, field_version, lock_path, present_lockfile is not None, current
        if current == workspace:
            break
        if workspace not in current.parents:
            break
        current = current.parent
    raise PreflightError("package manager cannot be determined: add packageManager or canonical lockfile evidence")


def build_install_command(manager: str, dependency_type: str, packages: list[str]) -> str:
    quoted = " ".join(shlex.quote(value) for value in packages)
    if manager == "npm":
        prefix = "npm install --save-dev" if dependency_type == "dev" else "npm install"
    elif manager == "pnpm":
        prefix = "pnpm add -D" if dependency_type == "dev" else "pnpm add"
    elif manager == "yarn":
        prefix = "yarn add -D" if dependency_type == "dev" else "yarn add"
    elif manager == "bun":
        prefix = "bun add -d" if dependency_type == "dev" else "bun add"
    else:
        raise PreflightError(f"unsupported manager: {manager}")
    return f"{prefix} {quoted}".strip()


def nearest_version_file(package_root: Path, workspace: Path) -> tuple[str, str]:
    current = package_root
    while True:
        for filename in (".nvmrc", ".node-version"):
            path = current / filename
            if path.is_file():
                try:
                    return filename, path.read_text(encoding="utf-8").strip()
                except OSError:
                    return filename, ""
        if current == workspace:
            break
        if workspace not in current.parents:
            break
        current = current.parent
    return "", ""


def inherited_node_requirement(package_manifest: dict, manager_root: Path, package_root: Path) -> tuple[str, str]:
    engines = package_manifest.get("engines") if isinstance(package_manifest.get("engines"), dict) else {}
    engine_node = str(engines.get("node", "")).strip() if engines else ""
    volta = package_manifest.get("volta") if isinstance(package_manifest.get("volta"), dict) else {}
    volta_node = str(volta.get("node", "")).strip() if volta else ""
    if volta_node:
        return "volta.node", volta_node
    if engine_node:
        return "engines.node", engine_node
    if manager_root != package_root and (manager_root / "package.json").is_file():
        root_manifest = read_json(manager_root / "package.json")
        root_engines = root_manifest.get("engines") if isinstance(root_manifest.get("engines"), dict) else {}
        root_engine_node = str(root_engines.get("node", "")).strip() if root_engines else ""
        root_volta = root_manifest.get("volta") if isinstance(root_manifest.get("volta"), dict) else {}
        root_volta_node = str(root_volta.get("node", "")).strip() if root_volta else ""
        if root_volta_node:
            return "manager-root volta.node", root_volta_node
        if root_engine_node:
            return "manager-root engines.node", root_engine_node
    return "NONE", ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve Node dependency mutation compatibility before install")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--package-root")
    parser.add_argument("--dependency-type", choices=("prod", "dev"), default="prod")
    parser.add_argument("--package", action="append", dest="packages", required=True)
    args = parser.parse_args()

    try:
        workspace = Path(args.workspace).expanduser().resolve()
        if not workspace.is_dir():
            raise PreflightError(f"workspace not found: {workspace}")
        if args.package_root:
            candidate = Path(args.package_root).expanduser()
            if not candidate.is_absolute():
                candidate = workspace / candidate
            package_root = safe_resolve_under(workspace, candidate)
            if not (package_root / "package.json").is_file():
                raise PreflightError(f"package.json not found at approved package root: {package_root}")
        else:
            roots = discover_package_roots(workspace)
            if len(roots) != 1:
                rendered = ",".join(str(path.relative_to(workspace)) for path in roots) or "NONE"
                raise PreflightError(
                    f"package root is ambiguous; pass --package-root explicitly: candidates={rendered}"
                )
            package_root = roots[0]

        manifest = read_json(package_root / "package.json")
        manager, manager_source, required_manager_version, lock_path, lock_present, manager_root = resolve_manager_boundary(
            package_root, workspace
        )

        node_version_raw = run_version(["node", "--version"])
        if not node_version_raw:
            raise PreflightError("node executable is unavailable")
        node_version = normalize_version(node_version_raw)
        node_major = major_of(node_version)

        manager_binary = shutil.which(manager)
        if not manager_binary:
            raise PreflightError(f"package manager executable is unavailable: {manager}")
        manager_version = normalize_version(run_version([manager_binary, "--version"]))
        if not manager_version:
            raise PreflightError(f"cannot determine package manager version: {manager}")
        if required_manager_version and manager_version != required_manager_version:
            raise PreflightError(
                f"package manager version mismatch: required={required_manager_version}, actual={manager_version}"
            )

        version_file_name, version_file_value = nearest_version_file(package_root, workspace)
        manifest_requirement_source, manifest_requirement = inherited_node_requirement(manifest, manager_root, package_root)
        node_requirement = version_file_value or manifest_requirement
        node_requirement_source = version_file_name or manifest_requirement_source
        required_node_major = simple_required_major(node_requirement) if node_requirement else None
        node_check = "not_required"
        if node_requirement:
            node_check = "manual"
            if required_node_major is not None and node_major is not None:
                if required_node_major != node_major:
                    raise PreflightError(
                        f"node version mismatch: requirement={node_requirement}, actual={node_version}"
                    )
                node_check = "pass"

        dependency_rows: list[tuple[str, str, str, str]] = []
        for spec in args.packages:
            name = package_name(spec)
            state = manifest_state(manifest, name)
            modules_state = node_modules_state(package_root, name, state)
            dependency_rows.append((spec, name, state, modules_state))

        install_required = any(row[2] == "ABSENT" for row in dependency_rows)
        restore_required = any(row[2] != "ABSENT" and row[3] == "ABSENT" for row in dependency_rows)
        install_command = build_install_command(manager, args.dependency_type, args.packages) if install_required else "NOT_REQUIRED"

        print(f"WORKSPACE={workspace}")
        print(f"PACKAGE_ROOT={package_root}")
        print(f"PACKAGE_MANAGER_ROOT={manager_root}")
        print(f"PACKAGE_MANAGER={manager}")
        print(f"PACKAGE_MANAGER_SOURCE={manager_source}")
        print(f"PACKAGE_MANAGER_VERSION={manager_version}")
        print(f"PACKAGE_MANAGER_REQUIRED_VERSION={required_manager_version or 'NONE'}")
        print(f"CANONICAL_LOCKFILE={lock_path}")
        print(f"LOCKFILE_PRESENT={'true' if lock_present else 'false'}")
        print(f"NODE_VERSION={node_version}")
        print(f"NODE_REQUIREMENT={node_requirement or 'NONE'}")
        print(f"NODE_REQUIREMENT_SOURCE={node_requirement_source}")
        print(f"NODE_REQUIREMENT_CHECK={node_check}")
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
