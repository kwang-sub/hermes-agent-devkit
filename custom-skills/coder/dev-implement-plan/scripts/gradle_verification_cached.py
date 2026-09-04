#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

DEFAULT_VERIFY_TIMEOUT = int(os.getenv("HERMES_GRADLE_VERIFY_TIMEOUT_SECONDS", "600"))
MAX_VERIFY_TIMEOUT = 600
DEFAULT_EVIDENCE_ROOT = Path(
    os.getenv("HERMES_GRADLE_EVIDENCE_ROOT", "/opt/data/gradle/verification-evidence")
)
AUTO_SCOPE_PATHS = (
    ".hermes/toolchain.env",
    "gradlew",
    "gradle/wrapper/gradle-wrapper.properties",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "settings.gradle.kts",
    "gradle.properties",
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Run canonical Gradle verification once per unchanged executable scope and "
            "reuse a persisted PASS result across Coder/Reviewer sessions."
        )
    )
    p.add_argument("--workspace", required=True)
    p.add_argument("--mode", required=True, choices=["COMPILE", "TARGETED_TEST"])
    p.add_argument("--test", action="append", default=[])
    p.add_argument("--task", default=None)
    p.add_argument(
        "--scope-path",
        action="append",
        default=[],
        required=True,
        help="Executable production/test path covered by this verification; repeatable.",
    )
    p.add_argument("--verification-timeout", type=int, default=DEFAULT_VERIFY_TIMEOUT)
    p.add_argument("--capability-timeout", type=int, default=None)
    p.add_argument("--diagnostic-timeout", type=int, default=None)
    p.add_argument("--dry-run-timeout", type=int, default=None)
    p.add_argument("--launcher", default=os.getenv("HERMES_JAVA_LAUNCHER", "hermes-java"))
    p.add_argument(
        "--engine",
        default=str(Path(__file__).resolve().with_name("gradle_verification.py")),
        help="Underlying bounded Gradle verification engine.",
    )
    p.add_argument("--evidence-root", default=str(DEFAULT_EVIDENCE_ROOT))
    return p.parse_args()


def safe_id(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)


def ensure_within_workspace(workspace: Path, raw: str) -> tuple[str, Path]:
    candidate = Path(raw)
    path = candidate.resolve() if candidate.is_absolute() else (workspace / candidate).resolve()
    try:
        relative = path.relative_to(workspace).as_posix()
    except ValueError as exc:
        raise ValueError(f"scope path escapes workspace: {raw}") from exc
    return relative, path


def resolved_scope_paths(workspace: Path, requested: list[str]) -> list[tuple[str, Path]]:
    items: dict[str, Path] = {}
    for raw in requested:
        relative, path = ensure_within_workspace(workspace, raw)
        if not path.is_file():
            raise ValueError(f"scope path is not a file: {raw}")
        items[relative] = path
    for raw in AUTO_SCOPE_PATHS:
        relative, path = ensure_within_workspace(workspace, raw)
        if path.is_file():
            items.setdefault(relative, path)
    return sorted(items.items())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scope_sha256(scope: list[tuple[str, Path]]) -> str:
    digest = hashlib.sha256()
    for relative, path in scope:
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def request_payload(
    *,
    workspace: Path,
    mode: str,
    task: str,
    tests: list[str],
    scope: list[tuple[str, Path]],
    engine_sha256: str,
) -> dict[str, object]:
    return {
        "task_id": (os.getenv("HERMES_KANBAN_TASK") or "no-task").strip() or "no-task",
        "workspace": str(workspace),
        "mode": mode,
        "task": task,
        "tests": sorted(set(tests)),
        "scope_paths": [relative for relative, _ in scope],
        "engine_sha256": engine_sha256,
    }


def request_sha256(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def evidence_path(root: Path, workspace: Path, request_sha: str) -> Path:
    return root / safe_id(workspace.name or "workspace") / f"{request_sha}.json"


def load_evidence(path: Path) -> dict[str, object] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def remove_evidence(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def write_evidence(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temp.write_text(
        json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


def emit_identity(
    *, request_sha: str, scope_sha: str, scope: list[tuple[str, Path]], timeout: int
) -> None:
    print(f"VERIFICATION_REQUEST_SHA256={request_sha}")
    print(f"VERIFICATION_SCOPE_SHA256={scope_sha}")
    print("VERIFICATION_SCOPE_PATHS=" + ",".join(relative for relative, _ in scope))
    print(f"VERIFICATION_TIMEOUT_SECONDS={timeout}")


def main() -> int:
    args = parse_args()
    workspace = Path(args.workspace).resolve()
    if not workspace.is_dir():
        print(f"ERROR: workspace does not exist: {workspace}", file=sys.stderr)
        return 2
    if args.mode == "TARGETED_TEST" and not args.test:
        print("ERROR: TARGETED_TEST requires at least one --test selector", file=sys.stderr)
        return 2
    if args.verification_timeout < 1 or args.verification_timeout > MAX_VERIFY_TIMEOUT:
        print(
            f"ERROR: verification timeout must be between 1 and {MAX_VERIFY_TIMEOUT} seconds",
            file=sys.stderr,
        )
        return 2

    engine = Path(args.engine).resolve()
    if not engine.is_file():
        print(f"ERROR: Gradle verification engine is missing: {engine}", file=sys.stderr)
        return 2

    try:
        scope = resolved_scope_paths(workspace, args.scope_path)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    task = args.task or ("compileJava" if args.mode == "COMPILE" else "test")
    engine_sha = sha256_file(engine)
    payload = request_payload(
        workspace=workspace,
        mode=args.mode,
        task=task,
        tests=args.test,
        scope=scope,
        engine_sha256=engine_sha,
    )
    request_sha = request_sha256(payload)
    before_sha = scope_sha256(scope)
    evidence = evidence_path(Path(args.evidence_root), workspace, request_sha)
    emit_identity(
        request_sha=request_sha,
        scope_sha=before_sha,
        scope=scope,
        timeout=args.verification_timeout,
    )

    cached = load_evidence(evidence)
    if (
        cached
        and cached.get("status") == "PASS"
        and cached.get("request_sha256") == request_sha
        and cached.get("scope_sha256") == before_sha
    ):
        print("VERIFICATION_EVIDENCE=REUSED")
        print("PRIMARY_REUSED=true")
        if cached.get("primary_command"):
            print(f"PRIMARY_COMMAND={cached['primary_command']}")
        if cached.get("primary_duration_seconds") is not None:
            print(f"PRIMARY_ORIGINAL_DURATION_SECONDS={cached['primary_duration_seconds']}")
        print("GRADLE_STATUS=PASS")
        print("GRADLE_BLOCKER=NONE")
        return 0

    # A scope mismatch or previous non-reusable artifact invalidates the old PASS
    # before any fresh execution. A failed/blocked fresh run must never fall back
    # to an older PASS if source later changes again.
    remove_evidence(evidence)

    cmd = [
        sys.executable,
        str(engine),
        "--workspace",
        str(workspace),
        "--mode",
        args.mode,
        "--verification-timeout",
        str(args.verification_timeout),
        "--launcher",
        args.launcher,
    ]
    if args.task:
        cmd.extend(["--task", args.task])
    for selector in args.test:
        cmd.extend(["--test", selector])
    for option, value in (
        ("--capability-timeout", args.capability_timeout),
        ("--diagnostic-timeout", args.diagnostic_timeout),
        ("--dry-run-timeout", args.dry_run_timeout),
    ):
        if value is not None:
            cmd.extend([option, str(value)])

    result = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if result.stdout:
        sys.stdout.write(result.stdout)
        if not result.stdout.endswith("\n"):
            sys.stdout.write("\n")
    if result.stderr:
        sys.stderr.write(result.stderr)
        if not result.stderr.endswith("\n"):
            sys.stderr.write("\n")

    try:
        after_sha = scope_sha256(scope)
    except OSError as exc:
        print(f"ERROR: failed to fingerprint verification scope after run: {exc}", file=sys.stderr)
        return 2

    if after_sha != before_sha:
        print("VERIFICATION_EVIDENCE=INVALIDATED")
        print("VERIFICATION_SCOPE_CHANGED_DURING_RUN=true")
        print(f"VERIFICATION_SCOPE_SHA256_AFTER={after_sha}")
        print("GRADLE_STATUS=BLOCKED")
        print("GRADLE_BLOCKER=SOURCE_CHANGED_DURING_VERIFICATION")
        print("FRESH_VERIFICATION_REQUIRED=true")
        return 2

    if result.returncode == 0 and "GRADLE_STATUS=PASS" in result.stdout:
        primary_command = ""
        primary_duration = None
        for line in result.stdout.splitlines():
            if line.startswith("PRIMARY_COMMAND="):
                primary_command = line.split("=", 1)[1]
            elif line.startswith("PRIMARY_DURATION_SECONDS="):
                primary_duration = line.split("=", 1)[1]
        write_evidence(
            evidence,
            {
                "status": "PASS",
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "request_sha256": request_sha,
                "scope_sha256": before_sha,
                "request": payload,
                "primary_command": primary_command,
                "primary_duration_seconds": primary_duration,
            },
        )
        print("VERIFICATION_EVIDENCE=EXECUTED")
        print("PRIMARY_REUSED=false")
        print("FRESH_VERIFICATION_REQUIRED=false")
        return 0

    print("VERIFICATION_EVIDENCE=NOT_REUSABLE")
    print("PRIMARY_REUSED=false")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
