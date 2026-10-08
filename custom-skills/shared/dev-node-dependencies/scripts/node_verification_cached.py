#!/usr/bin/env python3
"""Cached pnpm verification routed only through canonical Linux Node isolation.

Only PASS evidence for an identical command, toolchain and covered source scope
may be reused. Project scripts/CI conventions and dependency approvals remain
authoritative; this wrapper never installs packages or mutates source.
"""
from __future__ import annotations

import argparse
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from node_environment_gate import EnvironmentGateError, validate_project_environment
from node_runtime import validate_pnpm_command, RuntimeErrorPolicy
from node_workspace import resolve_cwd, resolve_package_root, WorkspaceError

DEFAULT_EVIDENCE_ROOT = Path(
    os.getenv("HERMES_NODE_VERIFICATION_EVIDENCE_ROOT", "/opt/data/node/verification-evidence")
)
RUNTIME_SCRIPT = Path(__file__).with_name("node_runtime.py")
AUTO_CONFIG_FILES = (
    "package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml",
    "tsconfig.json", "tsconfig.app.json", "tsconfig.node.json",
    "vitest.config.ts", "vite.config.ts", "jest.config.js",
    "next.config.js", "next.config.mjs", "next.config.ts",
)


class VerificationError(RuntimeError):
    pass


def parse_args(argv: list[str] | None = None) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--mode", choices=["STATIC_COMPILE", "TARGETED_TEST", "PACKAGE_BUILD"], required=True)
    parser.add_argument("--scope-path", action="append", default=[])
    parser.add_argument("--evidence-root", default=str(DEFAULT_EVIDENCE_ROOT))
    args, command = parser.parse_known_args(argv)
    if command and command[0] == "--":
        command = command[1:]
    if not command or not args.scope_path:
        parser.error("a canonical pnpm command and explicit --scope-path are required")
    return args, command


def covered_files(workspace: Path, package_root: Path, requested: list[str]) -> list[tuple[str, Path]]:
    paths: dict[str, Path] = {}
    candidates = [*requested, *[str((package_root / name).relative_to(workspace))
                                for name in AUTO_CONFIG_FILES]]
    for raw in candidates:
        candidate = (workspace / raw).resolve()
        try:
            relative = candidate.relative_to(workspace)
        except ValueError as exc:
            raise VerificationError(f"covered path escapes approved workspace: {raw}") from exc
        if raw in requested and not candidate.is_file():
            raise VerificationError(f"explicit verification scope is missing: {raw}")
        if candidate.is_file():
            paths[relative.as_posix()] = candidate
    return sorted(paths.items())


def fingerprint(files: list[tuple[str, Path]]) -> str:
    digest = sha256()
    for name, path in files:
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def request_digest(
    *, workspace: Path, cwd: Path, mode: str, command: list[str],
    files: list[tuple[str, Path]],
) -> str:
    payload = {
        "schema": 1,
        "workspace": str(workspace),
        "cwd": str(cwd),
        "mode": mode,
        "command": command,
        "scope_paths": [name for name, _ in files],
        "runner_sha256": file_sha256(RUNTIME_SCRIPT),
        "cache_helper_sha256": file_sha256(Path(__file__)),
    }
    return sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def atomic_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".receipt-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(payload, out, sort_keys=True)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def load_pass(path: Path, request_hash: str, scope_hash: str) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return (
        isinstance(data, dict) and data.get("status") == "PASS"
        and data.get("request_sha256") == request_hash
        and data.get("scope_sha256") == scope_hash
    )


def execute_runtime(workspace: Path, cwd: Path, command: list[str]) -> int:
    relative_cwd = str(cwd.relative_to(workspace))
    argv = [
        sys.executable, str(RUNTIME_SCRIPT), "--workspace", str(workspace),
        "--cwd", relative_cwd, "--", *command,
    ]
    return subprocess.call(argv, cwd=workspace)


def run(
    *, workspace: Path, cwd: Path, mode: str, command: list[str],
    scope_paths: list[str], evidence_root: Path,
) -> int:
    validate_pnpm_command(command)
    package_root = resolve_package_root(workspace, cwd)
    # Still enforce toolchain/build-policy checks on cache hits.
    validate_project_environment(package_root)
    selected = covered_files(workspace, package_root, scope_paths)
    request_hash = request_digest(
        workspace=workspace, cwd=cwd, mode=mode, command=command, files=selected,
    )
    scope_hash = fingerprint(selected)
    workspace_hash = sha256(str(workspace).encode("utf-8")).hexdigest()[:20]
    evidence = evidence_root / workspace_hash / (request_hash + ".json")
    evidence.parent.mkdir(parents=True, exist_ok=True)
    lock_path = evidence.with_suffix(".lock")
    print(f"VERIFICATION_REQUEST_SHA256={request_hash}")
    print(f"VERIFICATION_SCOPE_SHA256={scope_hash}")
    print(f"VERIFICATION_SCOPE_PATHS={','.join(name for name, _ in selected)}")
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            if load_pass(evidence, request_hash, scope_hash):
                print("VERIFICATION_EVIDENCE=REUSED")
                print("PRIMARY_REUSED=true")
                print("NODE_VERIFICATION_STATUS=PASS")
                return 0
            # Do not resurrect stale PASS evidence when content later reverts.
            evidence.unlink(missing_ok=True)
            result = execute_runtime(workspace, cwd, command)
            final_hash = fingerprint(selected)
            if final_hash != scope_hash:
                print("VERIFICATION_SCOPE_CHANGED_DURING_RUN=true")
                print("VERIFICATION_EVIDENCE=INVALIDATED")
                print("NODE_VERIFICATION_STATUS=BLOCKED")
                return 2
            if result == 0:
                atomic_json(evidence, {
                    "status": "PASS", "request_sha256": request_hash,
                    "scope_sha256": scope_hash, "scope_paths": [name for name, _ in selected],
                    "command": command, "mode": mode,
                })
                print("VERIFICATION_EVIDENCE=EXECUTED")
                print("PRIMARY_REUSED=false")
                print("NODE_VERIFICATION_STATUS=PASS")
                return 0
            print("VERIFICATION_EVIDENCE=NOT_REUSABLE")
            print("PRIMARY_REUSED=false")
            print("NODE_VERIFICATION_STATUS=FAIL")
            return int(result)
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def main(argv: list[str] | None = None) -> int:
    args, command = parse_args(argv)
    try:
        workspace = Path(args.workspace).resolve()
        if not workspace.is_dir():
            raise VerificationError("workspace is missing")
        cwd = resolve_cwd(workspace, args.cwd)
        evidence_root = Path(args.evidence_root).resolve()
        if not evidence_root.is_absolute():
            raise VerificationError("evidence root must be absolute")
        return run(
            workspace=workspace, cwd=cwd, mode=args.mode, command=command,
            scope_paths=args.scope_path, evidence_root=evidence_root,
        )
    except (VerificationError, EnvironmentGateError, RuntimeErrorPolicy,
            WorkspaceError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"NODE_VERIFICATION_STATUS=BLOCKED\nNODE_VERIFICATION_BLOCKER={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
