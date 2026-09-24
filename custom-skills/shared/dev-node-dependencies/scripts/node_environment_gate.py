#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

from pnpm_build_policy import BuildPolicyError, inspect_build_policy
from node_workspace import WorkspaceError, resolve_cwd, resolve_package_root


PNPM_LOCKFILE = "pnpm-lock.yaml"
LEGACY_LOCKFILES = (
    "package-lock.json",
    "npm-shrinkwrap.json",
    "yarn.lock",
    "bun.lock",
    "bun.lockb",
)


class EnvironmentGateError(RuntimeError):
    def __init__(self, message: str, blocker_class: str = "PROJECT_TOOLCHAIN_MIGRATION_REQUIRED"):
        super().__init__(message)
        self.blocker_class = blocker_class


def read_manifest(package_root: Path) -> dict:
    path = package_root / "package.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise EnvironmentGateError(f"cannot read package.json: {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise EnvironmentGateError(f"invalid package.json: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise EnvironmentGateError(f"package.json root must be an object: {path}")
    return data


def resolve_dev_engines(manifest: dict) -> tuple[str, str]:
    dev_engines = manifest.get("devEngines")
    if not isinstance(dev_engines, dict):
        raise EnvironmentGateError(
            "package.json must declare devEngines.runtime and devEngines.packageManager before Hermes frontend verification"
        )

    runtime_value = dev_engines.get("runtime")
    runtime_entries = runtime_value if isinstance(runtime_value, list) else [runtime_value]
    node_entries = [
        item
        for item in runtime_entries
        if isinstance(item, dict) and str(item.get("name", "")).strip() == "node"
    ]
    if len(node_entries) != 1:
        raise EnvironmentGateError(
            "devEngines.runtime must declare exactly one Node runtime"
        )
    node_entry = node_entries[0]
    node_requirement = str(node_entry.get("version", "")).strip()
    if not node_requirement:
        raise EnvironmentGateError("devEngines.runtime Node version is missing")
    if str(node_entry.get("onFail", "")).strip() != "download":
        raise EnvironmentGateError(
            "devEngines.runtime.onFail must be 'download'"
        )

    manager = dev_engines.get("packageManager")
    if not isinstance(manager, dict):
        raise EnvironmentGateError(
            "devEngines.packageManager must declare pnpm"
        )
    if str(manager.get("name", "")).strip() != "pnpm":
        raise EnvironmentGateError(
            "devEngines.packageManager.name must be 'pnpm'"
        )
    pnpm_requirement = str(manager.get("version", "")).strip()
    if not pnpm_requirement:
        raise EnvironmentGateError(
            "devEngines.packageManager pnpm version is missing"
        )
    if str(manager.get("onFail", "")).strip() != "download":
        raise EnvironmentGateError(
            "devEngines.packageManager.onFail must be 'download'"
        )
    return node_requirement, pnpm_requirement


def validate_package_manager_declaration(manifest: dict) -> str:
    declared = manifest.get("packageManager")
    if declared is None:
        return "NOT_DECLARED"
    if not isinstance(declared, str) or not declared.strip():
        raise EnvironmentGateError(
            "package.json packageManager must be a pnpm declaration when present"
        )
    value = declared.strip()
    name = value.split("@", 1)[0]
    if name != "pnpm":
        raise EnvironmentGateError(
            f"package.json packageManager conflicts with DevKit pnpm-only contract: {value}"
        )
    return value


def validate_project_environment(package_root: Path) -> dict[str, object]:
    manifest = read_manifest(package_root)
    node_requirement, pnpm_requirement = resolve_dev_engines(manifest)
    package_manager_declaration = validate_package_manager_declaration(manifest)

    legacy = [name for name in LEGACY_LOCKFILES if (package_root / name).is_file()]
    if legacy:
        raise EnvironmentGateError(
            "legacy package-manager lockfile detected; pnpm migration must be handled as a separate approved scope before frontend verification: "
            + ", ".join(legacy)
        )

    lockfile = package_root / PNPM_LOCKFILE
    if not lockfile.is_file():
        raise EnvironmentGateError(
            "pnpm-lock.yaml is required by the DevKit frontend verification contract; migrate the project toolchain before continuing"
        )

    pnpm_binary = shutil.which("pnpm")
    if not pnpm_binary:
        raise EnvironmentGateError(
            "pnpm standalone executable is unavailable in the DevKit runtime",
            blocker_class="DEVKIT_RUNTIME_CAPABILITY_MISSING",
        )
    try:
        build_policy = inspect_build_policy(package_root, pnpm_binary)
    except BuildPolicyError as exc:
        raise EnvironmentGateError(
            str(exc),
            blocker_class=exc.blocker_class,
        ) from exc

    return {
        "node_requirement": node_requirement,
        "pnpm_requirement": pnpm_requirement,
        "package_manager_declaration": package_manager_declaration,
        "lockfile": str(lockfile),
        "build_policy_file": build_policy["policy_file"],
        "approved_builds": build_policy["approved"],
        "denied_builds": build_policy["denied"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Block non-canonical Node projects before Hermes frontend commands can run."
    )
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--cwd", default=".", help="Package cwd relative to workspace")
    args = parser.parse_args()

    package_root: Path | None = None
    try:
        workspace = Path(args.workspace).expanduser().resolve()
        if not workspace.is_dir():
            raise EnvironmentGateError(f"workspace does not exist: {workspace}")
        cwd = resolve_cwd(workspace, args.cwd)
        package_root = resolve_package_root(workspace, cwd)
        evidence = validate_project_environment(package_root)

        print("FRONTEND_ENVIRONMENT_GATE=PASS")
        print("BLOCKER_CLASS=NONE")
        print(f"WORKSPACE={workspace}")
        print(f"PACKAGE_ROOT={package_root}")
        print("PACKAGE_MANAGER=pnpm")
        print(
            "PACKAGE_MANAGER_SOURCE=package.json devEngines.packageManager"
        )
        print(
            f"PACKAGE_MANAGER_DECLARATION={evidence['package_manager_declaration']}"
        )
        print(f"PNPM_REQUIREMENT={evidence['pnpm_requirement']}")
        print(f"NODE_REQUIREMENT={evidence['node_requirement']}")
        print(f"CANONICAL_LOCKFILE={evidence['lockfile']}")
        print("CANONICAL_LOCKFILE_PRESENT=true")
        print("LEGACY_LOCKFILES=NONE")
        print(f"PNPM_BUILD_POLICY_FILE={evidence['build_policy_file']}")
        print("PNPM_BUILD_POLICY_SOURCE=pnpm-workspace.yaml")
        print("PNPM_STRICT_DEP_BUILDS=true")
        print("PNPM_DANGEROUSLY_ALLOW_ALL_BUILDS=false")
        print(
            "PNPM_APPROVED_BUILDS="
            + (",".join(evidence["approved_builds"]) if evidence["approved_builds"] else "NONE")
        )
        print(
            "PNPM_DENIED_BUILDS="
            + (",".join(evidence["denied_builds"]) if evidence["denied_builds"] else "NONE")
        )
        print("SOURCE_VERIFICATION_POLICY=FORBIDDEN")
        print("VERIFICATION_RUNTIME=node_runtime.py")
        print("DEPENDENCY_MUTATION_POLICY=dev-node-dependencies")
        return 0
    except EnvironmentGateError as exc:
        print("FRONTEND_ENVIRONMENT_GATE=BLOCKED", file=sys.stderr)
        print(f"BLOCKER_CLASS={exc.blocker_class}", file=sys.stderr)
        if package_root is not None:
            print(f"PACKAGE_ROOT={package_root}", file=sys.stderr)
        print("SOURCE_VERIFICATION_POLICY=FORBIDDEN", file=sys.stderr)
        print(f"BLOCKER={exc}", file=sys.stderr)
        return 2
    except WorkspaceError as exc:
        print("FRONTEND_ENVIRONMENT_GATE=BLOCKED", file=sys.stderr)
        print("BLOCKER_CLASS=PROJECT_STRUCTURE_INVALID", file=sys.stderr)
        print("SOURCE_VERIFICATION_POLICY=FORBIDDEN", file=sys.stderr)
        print(f"BLOCKER={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
