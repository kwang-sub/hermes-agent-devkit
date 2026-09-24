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

from pnpm_build_policy import BuildPolicyError, inspect_build_policy
from node_workspace import DEFAULT_ROOT, WorkspaceError, prepare_isolated_package


PNPM_LOCKFILE = "pnpm-lock.yaml"
LEGACY_LOCKFILES = (
    "package-lock.json",
    "npm-shrinkwrap.json",
    "yarn.lock",
    "bun.lock",
    "bun.lockb",
)
SKIP_DIRS = {
    ".git",
    ".hermes",
    ".worktrees",
    "node_modules",
    ".next",
    ".next-hermes",
    "dist",
    "build",
    "coverage",
    "target",
}
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


def run_version(command: list[str], *, cwd: Path | None = None) -> str:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
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
    text = (result.stdout or result.stderr).strip().splitlines()
    return text[0].strip() if text else ""


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
    if any(
        spec.startswith(prefix)
        for prefix in ("file:", "git+", "http://", "https://", "github:")
    ):
        raise PreflightError(
            f"non-registry package spec requires explicit project handling: {spec}"
        )
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


def resolve_dev_engines(manifest: dict) -> tuple[str, str]:
    dev_engines = manifest.get("devEngines")
    if not isinstance(dev_engines, dict):
        raise PreflightError(
            "package.json must declare devEngines.runtime and devEngines.packageManager"
        )

    runtime_value = dev_engines.get("runtime")
    runtime_entries = runtime_value if isinstance(runtime_value, list) else [runtime_value]
    node_entries = [
        item
        for item in runtime_entries
        if isinstance(item, dict) and str(item.get("name", "")).strip() == "node"
    ]
    if len(node_entries) != 1:
        raise PreflightError("devEngines.runtime must declare exactly one Node runtime")
    node = node_entries[0]
    node_version = str(node.get("version", "")).strip()
    if not node_version:
        raise PreflightError("devEngines.runtime Node version is missing")
    if str(node.get("onFail", "")).strip() != "download":
        raise PreflightError("devEngines.runtime Node onFail must be 'download'")

    manager = dev_engines.get("packageManager")
    if not isinstance(manager, dict):
        raise PreflightError("devEngines.packageManager must declare pnpm")
    if str(manager.get("name", "")).strip() != "pnpm":
        raise PreflightError("devEngines.packageManager.name must be 'pnpm'")
    pnpm_version = str(manager.get("version", "")).strip()
    if not pnpm_version:
        raise PreflightError("devEngines.packageManager pnpm version is missing")
    if str(manager.get("onFail", "")).strip() != "download":
        raise PreflightError("devEngines.packageManager pnpm onFail must be 'download'")
    return node_version, pnpm_version


def assert_pnpm_only(package_root: Path) -> None:
    legacy = [name for name in LEGACY_LOCKFILES if (package_root / name).is_file()]
    if legacy:
        raise PreflightError(
            "legacy package-manager lockfile detected; migrate the project to pnpm first: "
            + ", ".join(legacy)
        )


def build_install_command(dependency_type: str, packages: list[str]) -> str:
    quoted = " ".join(shlex.quote(value) for value in packages)
    prefix = (
        "pnpm add --lockfile-only -D"
        if dependency_type == "dev"
        else "pnpm add --lockfile-only"
    )
    return f"{prefix} {quoted}".strip()


def build_mark_command(workspace: Path, package_root: Path) -> str:
    relative = package_root.relative_to(workspace)
    cwd = "." if not relative.parts else relative.as_posix()
    script = (
        "/opt/custom-skills/shared/dev-node-dependencies/scripts/node_workspace.py"
    )
    return (
        f"python3 {shlex.quote(script)} --workspace {shlex.quote(str(workspace))} "
        f"--cwd {shlex.quote(cwd)} --mark-restored"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve the canonical pnpm dependency mutation/restore contract"
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
        if args.package_root:
            candidate = Path(args.package_root).expanduser()
            if not candidate.is_absolute():
                candidate = workspace / candidate
            package_root = safe_resolve_under(workspace, candidate)
            if not (package_root / "package.json").is_file():
                raise PreflightError(
                    f"package.json not found at approved package root: {package_root}"
                )
        else:
            roots = discover_package_roots(workspace)
            if len(roots) != 1:
                rendered = (
                    ",".join(str(path.relative_to(workspace)) for path in roots)
                    or "NONE"
                )
                raise PreflightError(
                    f"package root is ambiguous; pass --package-root explicitly: candidates={rendered}"
                )
            package_root = roots[0]

        manifest = read_json(package_root / "package.json")
        node_requirement, pnpm_requirement = resolve_dev_engines(manifest)
        assert_pnpm_only(package_root)

        pnpm_binary = shutil.which("pnpm")
        if not pnpm_binary:
            raise PreflightError(
                "pnpm standalone executable is unavailable in the DevKit image"
            )
        pnpm_version = run_version([pnpm_binary, "--version"], cwd=package_root)
        if not pnpm_version:
            raise PreflightError("cannot resolve the project pnpm version")
        try:
            build_policy = inspect_build_policy(package_root, pnpm_binary)
        except BuildPolicyError as exc:
            raise PreflightError(
                f"{exc.blocker_class}: {exc}"
            ) from exc

        lock_path = package_root / PNPM_LOCKFILE
        lock_present = lock_path.is_file()

        root = Path(
            os.getenv("HERMES_NODE_ROOT", str(DEFAULT_ROOT))
        ).expanduser().resolve()
        isolated_paths = prepare_isolated_package(
            workspace, package_root, root=root
        )
        isolated_package_root = Path(isolated_paths["isolated_package_root"])

        dependency_rows: list[tuple[str, str, str, str]] = []
        for spec in args.packages:
            name = package_name(spec)
            state = manifest_state(manifest, name)
            modules_state = node_modules_state(
                isolated_package_root, name, state
            )
            dependency_rows.append((spec, name, state, modules_state))

        install_required = any(row[2] == "ABSENT" for row in dependency_rows)
        install_command = (
            build_install_command(args.dependency_type, args.packages)
            if install_required
            else "NOT_REQUIRED"
        )
        install_workdir = str(package_root) if install_required else "NOT_REQUIRED"

        # A manifest/lockfile mutation must complete first, then preflight is rerun
        # against the new fingerprint before restoring the isolated dependency tree.
        restore_required = (
            not install_required and not bool(isolated_paths["dependencies_ready"])
        )
        if restore_required and not lock_present:
            raise PreflightError(
                "pnpm-lock.yaml is required before restoring the Linux verification workspace"
            )
        restore_command = (
            "pnpm install --frozen-lockfile"
            if restore_required
            else "NOT_REQUIRED"
        )
        restore_workdir = (
            str(isolated_package_root)
            if restore_required
            else "NOT_REQUIRED"
        )
        restore_mark_command = (
            build_mark_command(workspace, package_root)
            if restore_required
            else "NOT_REQUIRED"
        )

        print(f"WORKSPACE={workspace}")
        print(f"PACKAGE_ROOT={package_root}")
        print(f"PACKAGE_MANAGER_ROOT={package_root}")
        print(f"VERIFICATION_PACKAGE_ROOT={isolated_package_root}")
        print("PACKAGE_MANAGER=pnpm")
        print("PACKAGE_MANAGER_SOURCE=package.json devEngines.packageManager")
        print(f"PACKAGE_MANAGER_VERSION={pnpm_version}")
        print(f"PACKAGE_MANAGER_REQUIRED_VERSION={pnpm_requirement}")
        print(f"PNPM_BUILD_POLICY_FILE={build_policy['policy_file']}")
        print("PNPM_BUILD_POLICY_SOURCE=pnpm-workspace.yaml")
        print("PNPM_STRICT_DEP_BUILDS=true")
        print("PNPM_DANGEROUSLY_ALLOW_ALL_BUILDS=false")
        print(
            "PNPM_APPROVED_BUILDS="
            + (",".join(build_policy["approved"]) if build_policy["approved"] else "NONE")
        )
        print(
            "PNPM_DENIED_BUILDS="
            + (",".join(build_policy["denied"]) if build_policy["denied"] else "NONE")
        )
        print(f"CANONICAL_LOCKFILE={lock_path}")
        print(f"LOCKFILE_PRESENT={'true' if lock_present else 'false'}")
        print("NODE_VERSION=managed-by-pnpm")
        print(f"NODE_REQUIREMENT={node_requirement}")
        print("NODE_REQUIREMENT_SOURCE=package.json devEngines.runtime")
        print("NODE_REQUIREMENT_CHECK=pnpm-managed")
        print(
            f"DEPENDENCY_FINGERPRINT={isolated_paths['current_dependency_fingerprint']}"
        )
        print(
            "DEPENDENCIES_READY="
            + ("true" if isolated_paths["dependencies_ready"] else "false")
        )
        for index, (spec, name, state, modules_state) in enumerate(
            dependency_rows, start=1
        ):
            print(f"DEPENDENCY_{index}_SPEC={spec}")
            print(f"DEPENDENCY_{index}_NAME={name}")
            print(f"DEPENDENCY_{index}_MANIFEST_STATE={state}")
            print(f"DEPENDENCY_{index}_NODE_MODULES_STATE={modules_state}")
        print(f"INSTALL_REQUIRED={'true' if install_required else 'false'}")
        print(f"INSTALL_COMMAND={install_command}")
        print(f"INSTALL_WORKDIR={install_workdir}")
        print(f"RESTORE_REQUIRED={'true' if restore_required else 'false'}")
        print(f"RESTORE_COMMAND={restore_command}")
        print(f"RESTORE_WORKDIR={restore_workdir}")
        print(f"RESTORE_MARK_COMMAND={restore_mark_command}")
        print(f"INSTALL_TIMEOUT_SECONDS={INSTALL_TIMEOUT_SECONDS}")
        print("STATUS=pass")
        return 0
    except (PreflightError, WorkspaceError) as exc:
        print(f"ERROR={exc}", file=sys.stderr)
        print("STATUS=blocked", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
