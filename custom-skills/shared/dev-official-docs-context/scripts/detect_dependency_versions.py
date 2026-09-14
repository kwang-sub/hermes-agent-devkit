#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

SKIP_DIRS = {
    ".git", ".hermes", ".worktrees", "node_modules", ".next",
    "dist", "build", "coverage", "target", ".test-build",
}
LOCKFILES = ("package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml", "yarn.lock", "bun.lock", "bun.lockb")


def _within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def discover_package_roots(workspace: Path, max_depth: int = 3) -> list[Path]:
    workspace = workspace.resolve()
    roots: list[Path] = []
    for current, dirs, files in os.walk(workspace):
        here = Path(current)
        try:
            depth = len(here.relative_to(workspace).parts)
        except ValueError:
            continue
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and depth < max_depth]
        if "package.json" in files:
            roots.append(here)
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    return sorted(set(roots))


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def select_package_root(workspace: Path, explicit: str | None) -> Path:
    workspace = workspace.resolve()
    if explicit:
        candidate = (workspace / explicit).resolve() if not Path(explicit).is_absolute() else Path(explicit).resolve()
        if not _within(candidate, workspace):
            raise ValueError("package root must stay inside workspace")
        if not (candidate / "package.json").is_file():
            raise ValueError(f"package.json not found at explicit package root: {candidate}")
        return candidate
    roots = discover_package_roots(workspace)
    if not roots:
        raise ValueError("no package.json found within bounded workspace scan")
    if len(roots) != 1:
        rel = ",".join(str(p.relative_to(workspace)) or "." for p in roots)
        raise ValueError(f"multiple package roots found; pass --package-root: {rel}")
    return roots[0]


def parse_package_manager(package: dict, root: Path) -> tuple[str, str]:
    raw = str(package.get("packageManager", "")).strip()
    if raw:
        match = re.match(r"^([A-Za-z0-9._-]+)@(.+)$", raw)
        if match:
            return match.group(1), match.group(2)
        return raw, "UNKNOWN"
    present = [name for name in LOCKFILES if (root / name).is_file()]
    managers = []
    for name in present:
        managers.append(
            "npm" if name in {"package-lock.json", "npm-shrinkwrap.json"}
            else "pnpm" if name == "pnpm-lock.yaml"
            else "yarn" if name == "yarn.lock"
            else "bun"
        )
    unique = list(dict.fromkeys(managers))
    if len(unique) == 1:
        return unique[0], "UNKNOWN"
    if len(unique) > 1:
        raise ValueError(f"conflicting package-manager lockfiles: {present}")
    return "UNKNOWN", "UNKNOWN"


def manifest_state(package: dict, name: str) -> tuple[str, str]:
    sections = (
        ("dependencies", "prod"),
        ("devDependencies", "dev"),
        ("peerDependencies", "peer"),
        ("optionalDependencies", "optional"),
    )
    for section, label in sections:
        values = package.get(section)
        if isinstance(values, dict) and name in values:
            return str(values[name]), label
    return "ABSENT", "absent"


def npm_lock_version(lock: dict, name: str) -> str | None:
    packages = lock.get("packages")
    if isinstance(packages, dict):
        entry = packages.get(f"node_modules/{name}")
        if isinstance(entry, dict) and entry.get("version"):
            return str(entry["version"])
    dependencies = lock.get("dependencies")
    if isinstance(dependencies, dict):
        entry = dependencies.get(name)
        if isinstance(entry, dict) and entry.get("version"):
            return str(entry["version"])
    return None


def installed_version(root: Path, name: str) -> str | None:
    path = root / "node_modules" / Path(*name.split("/")) / "package.json"
    if not path.is_file():
        return None
    try:
        data = load_json(path)
    except ValueError:
        return None
    value = data.get("version")
    return str(value) if value else None


def exact_manifest_version(spec: str) -> str | None:
    value = spec.strip()
    if re.fullmatch(r"v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", value):
        return value.removeprefix("v")
    return None


def resolve_dependency_version(root: Path, manager: str, name: str, declared: str) -> tuple[str, str]:
    if manager == "npm":
        for filename in ("package-lock.json", "npm-shrinkwrap.json"):
            path = root / filename
            if not path.is_file():
                continue
            try:
                version = npm_lock_version(load_json(path), name)
            except ValueError:
                version = None
            if version:
                return version, filename
    installed = installed_version(root, name)
    if installed:
        return installed, "node_modules/package.json"
    exact = exact_manifest_version(declared) if declared != "ABSENT" else None
    if exact:
        return exact, "package.json-exact"
    return "UNKNOWN", "UNKNOWN"


def node_version() -> str:
    try:
        proc = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=3, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return "UNKNOWN"
    return proc.stdout.strip().removeprefix("v") if proc.returncode == 0 else "UNKNOWN"


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect bounded project dependency version evidence for official-doc lookup")
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--package-root")
    parser.add_argument("--package", action="append", default=[])
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    try:
        root = select_package_root(workspace, args.package_root)
        package = load_json(root / "package.json")
        manager, manager_version = parse_package_manager(package, root)
    except ValueError as exc:
        print(f"BLOCK_REASON={exc}")
        print("STATUS=blocked")
        return 2

    packages = list(dict.fromkeys(args.package))
    if not packages:
        for section in ("dependencies", "devDependencies"):
            values = package.get(section)
            if isinstance(values, dict):
                packages.extend(str(name) for name in values)
        packages = list(dict.fromkeys(packages))

    print(f"WORKSPACE={workspace}")
    print(f"PACKAGE_ROOT={root}")
    print(f"PACKAGE_MANAGER={manager}")
    print(f"PACKAGE_MANAGER_VERSION={manager_version}")
    engines = package.get("engines") if isinstance(package.get("engines"), dict) else {}
    print(f"NODE_REQUIREMENT={engines.get('node', 'NONE')}")
    print(f"NODE_VERSION={node_version()}")

    for index, name in enumerate(packages, 1):
        declared, section = manifest_state(package, name)
        resolved, source = resolve_dependency_version(root, manager, name, declared)
        print(f"DEPENDENCY_{index}_NAME={name}")
        print(f"DEPENDENCY_{index}_SECTION={section}")
        print(f"DEPENDENCY_{index}_DECLARED_SPEC={declared}")
        print(f"DEPENDENCY_{index}_RESOLVED_VERSION={resolved}")
        print(f"DEPENDENCY_{index}_VERSION_SOURCE={source}")

    print("STATUS=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
