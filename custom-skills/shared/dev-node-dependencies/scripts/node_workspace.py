#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys


DEFAULT_ROOT = Path(os.getenv("HERMES_NODE_ROOT", "/opt/data/node"))

# Host/Windows generated state must never enter the Linux verification workspace.
# node_modules is preserved only in the isolated destination and is guarded by a
# package.json + pnpm-lock.yaml dependency fingerprint.
GENERATED_NAMES = {
    "node_modules",
    ".next",
    ".next-hermes",
    ".test-build",
    ".turbo",
    ".cache",
    "dist",
    "build",
    "coverage",
    "out",
}
SOURCE_ONLY_SKIP_NAMES = {".git", ".hermes", ".worktrees"}
PRESERVE_DEST_NAMES = {"node_modules"}
GENERATED_SUFFIXES = (".tsbuildinfo",)
DEPENDENCY_FINGERPRINT_FILE = ".hermes-dependency-fingerprint"


class WorkspaceError(RuntimeError):
    pass


def workspace_key(workspace: Path) -> str:
    digest = hashlib.sha256(str(workspace.resolve()).encode("utf-8")).hexdigest()[:16]
    name = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in workspace.name) or "workspace"
    return f"{name}-{digest}"


def package_key(workspace: Path, package_root: Path) -> str:
    relative = package_root.resolve().relative_to(workspace.resolve())
    label = package_root.name or "root"
    safe_label = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in label)
    digest = hashlib.sha256(str(relative).encode("utf-8")).hexdigest()[:12]
    return f"{safe_label}-{digest}"


def resolve_cwd(workspace: Path, raw: str) -> Path:
    candidate = Path(raw)
    path = candidate.resolve() if candidate.is_absolute() else (workspace / candidate).resolve()
    try:
        path.relative_to(workspace)
    except ValueError as exc:
        raise WorkspaceError(f"command cwd escapes workspace: {path}") from exc
    if not path.is_dir():
        raise WorkspaceError(f"command cwd does not exist: {path}")
    return path


def resolve_package_root(workspace: Path, cwd: Path) -> Path:
    current = cwd
    while True:
        if (current / "package.json").is_file():
            return current
        if current == workspace:
            break
        if workspace not in current.parents:
            break
        current = current.parent
    raise WorkspaceError(
        f"package.json was not found between command cwd and workspace root: cwd={cwd}, workspace={workspace}"
    )


def internal_paths(root: Path, workspace: Path, package_root: Path) -> dict[str, Path]:
    state = root / "workspaces" / workspace_key(workspace)
    package_state = state / "packages" / package_key(workspace, package_root)
    return {
        "node_root": root,
        "lock_root": root / "locks",
        "pnpm_home": root / "pnpm-home",
        "pnpm_store": root / "pnpm-store",
        "xdg_cache": root / "cache",
        "workspace_state": state,
        "package_state": package_state,
        "isolated_package_root": package_state / "source",
        "tmp": package_state / "tmp",
        "dependency_fingerprint": package_state / DEPENDENCY_FINGERPRINT_FILE,
    }


def _skip_source_entry(name: str) -> bool:
    return (
        name in GENERATED_NAMES
        or name in SOURCE_ONLY_SKIP_NAMES
        or name.endswith(GENERATED_SUFFIXES)
    )


def _remove(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.exists():
        shutil.rmtree(path)


def _assert_owned_by_current_user(path: Path) -> None:
    expected_uid = os.geteuid()
    actual_uid = path.stat().st_uid
    if actual_uid != expected_uid:
        raise WorkspaceError(
            "internal Node state owner mismatch: "
            f"path={path} owner_uid={actual_uid} expected_uid={expected_uid}"
        )


def _sync_tree(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    source_names: set[str] = set()

    for source_entry in source.iterdir():
        name = source_entry.name
        if _skip_source_entry(name):
            continue
        source_names.add(name)
        destination_entry = destination / name

        if source_entry.is_symlink():
            target = os.readlink(source_entry)
            if not destination_entry.is_symlink() or os.readlink(destination_entry) != target:
                _remove(destination_entry)
                destination_entry.symlink_to(target, target_is_directory=source_entry.is_dir())
            continue

        if source_entry.is_dir():
            if destination_entry.exists() and not destination_entry.is_dir():
                _remove(destination_entry)
            _sync_tree(source_entry, destination_entry)
            continue

        if destination_entry.exists() and not destination_entry.is_file():
            _remove(destination_entry)
        shutil.copy2(source_entry, destination_entry)

    # Delete stale source-controlled entries and previous framework/compiler output.
    # Linux node_modules is retained only until the dependency fingerprint check below.
    for destination_entry in destination.iterdir():
        name = destination_entry.name
        if name in PRESERVE_DEST_NAMES:
            continue
        if name not in source_names:
            _remove(destination_entry)


def dependency_fingerprint(package_root: Path) -> str:
    manifest = package_root / "package.json"
    lockfile = package_root / "pnpm-lock.yaml"
    if not manifest.is_file():
        raise WorkspaceError(f"package.json is missing from isolated package root: {package_root}")
    digest = hashlib.sha256()
    for path in (manifest, lockfile):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        if path.is_file():
            digest.update(path.read_bytes())
        else:
            digest.update(b"<missing>")
        digest.update(b"\0")
    return digest.hexdigest()


def _manifest_requires_node_modules(package_root: Path) -> bool:
    manifest = package_root / "package.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkspaceError(f"cannot inspect package.json dependency sections: {exc}") from exc
    dependency_sections = (
        "dependencies",
        "devDependencies",
        "optionalDependencies",
        "peerDependencies",
    )
    return any(
        isinstance(data.get(section), dict) and bool(data.get(section))
        for section in dependency_sections
    )


def dependency_state(paths: dict[str, Path]) -> tuple[str, bool]:
    isolated = paths["isolated_package_root"]
    current = dependency_fingerprint(isolated)
    marker = paths["dependency_fingerprint"]
    stored = marker.read_text(encoding="utf-8").strip() if marker.is_file() else ""
    modules = isolated / "node_modules"
    modules_ready = modules.is_dir() or not _manifest_requires_node_modules(isolated)
    ready = bool(stored and stored == current and modules_ready)
    if modules.exists() and not ready:
        _remove(modules)
    return current, ready


def prepare_isolated_package(
    workspace: Path,
    package_root: Path,
    *,
    root: Path | None = None,
) -> dict[str, Path | str | bool]:
    workspace = workspace.resolve()
    package_root = package_root.resolve()
    try:
        package_root.relative_to(workspace)
    except ValueError as exc:
        raise WorkspaceError(f"package root escapes workspace: {package_root}") from exc

    node_root = (root or DEFAULT_ROOT).expanduser().resolve()
    paths = internal_paths(node_root, workspace, package_root)
    for key, path in paths.items():
        if key in {"isolated_package_root", "dependency_fingerprint"}:
            continue
        path.mkdir(parents=True, exist_ok=True)
        _assert_owned_by_current_user(path)
        if not os.access(path, os.W_OK):
            raise WorkspaceError(f"internal Node state is not writable: {path}")

    isolated = paths["isolated_package_root"]
    isolated.mkdir(parents=True, exist_ok=True)
    _assert_owned_by_current_user(isolated)
    _sync_tree(package_root, isolated)
    if not (isolated / "package.json").is_file():
        raise WorkspaceError(f"isolated package sync is missing package.json: {isolated}")

    fingerprint, dependencies_ready = dependency_state(paths)
    return {
        **paths,
        "current_dependency_fingerprint": fingerprint,
        "dependencies_ready": dependencies_ready,
    }


def mark_dependencies_restored(
    workspace: Path,
    package_root: Path,
    *,
    root: Path,
) -> dict[str, Path | str | bool]:
    paths = internal_paths(root, workspace, package_root)
    isolated = paths["isolated_package_root"]
    if not isolated.is_dir():
        raise WorkspaceError(
            f"isolated package root does not exist; prepare/restore it first: {isolated}"
        )
    _assert_owned_by_current_user(isolated)
    _assert_owned_by_current_user(paths["package_state"])

    source_fingerprint = dependency_fingerprint(package_root)
    isolated_fingerprint = dependency_fingerprint(isolated)
    if source_fingerprint != isolated_fingerprint:
        raise WorkspaceError(
            "source package.json/pnpm-lock.yaml changed after isolated restore; rerun preflight/restore before marking"
        )

    requires_modules = _manifest_requires_node_modules(package_root)
    modules = isolated / "node_modules"
    if requires_modules and not modules.is_dir():
        raise WorkspaceError(
            f"cannot mark dependencies restored before node_modules exists: {modules}"
        )

    marker = paths["dependency_fingerprint"]
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(source_fingerprint + "\n", encoding="utf-8")
    return {
        **paths,
        "current_dependency_fingerprint": source_fingerprint,
        "dependencies_ready": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mirror a Node package into the Linux-only Hermes verification workspace."
    )
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--cwd", default=".")
    parser.add_argument(
        "--mark-restored",
        action="store_true",
        help="Record the current package.json/pnpm-lock.yaml fingerprint after a successful isolated pnpm restore.",
    )
    args = parser.parse_args()

    try:
        workspace = Path(args.workspace).expanduser().resolve()
        if not workspace.is_dir():
            raise WorkspaceError(f"workspace does not exist: {workspace}")
        cwd = resolve_cwd(workspace, args.cwd)
        package_root = resolve_package_root(workspace, cwd)
        root = Path(os.getenv("HERMES_NODE_ROOT", str(DEFAULT_ROOT))).expanduser().resolve()
        if args.mark_restored:
            paths = mark_dependencies_restored(
                workspace,
                package_root,
                root=root,
            )
        else:
            paths = prepare_isolated_package(workspace, package_root, root=root)

        print(f"NODE_WORKSPACE={workspace}")
        print(f"NODE_SOURCE_PACKAGE_ROOT={package_root}")
        print(f"NODE_ISOLATED_PACKAGE_ROOT={paths['isolated_package_root']}")
        print(f"NODE_WORKSPACE_STATE_ROOT={paths['workspace_state']}")
        print(f"NODE_PNPM_STORE={paths['pnpm_store']}")
        print(f"NODE_DEPENDENCY_FINGERPRINT={paths['current_dependency_fingerprint']}")
        print(
            "NODE_DEPENDENCIES_READY="
            + ("true" if paths["dependencies_ready"] else "false")
        )
        print("NODE_WORKSPACE_SYNC=ready")
        return 0
    except (WorkspaceError, OSError) as exc:
        print(f"NODE_WORKSPACE_STATUS=BLOCKED\nNODE_WORKSPACE_BLOCKER={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
