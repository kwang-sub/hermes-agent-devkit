#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

DEFAULT_VERIFY_TIMEOUT = int(os.getenv("HERMES_GRADLE_VERIFY_TIMEOUT_SECONDS", "600"))
MAX_VERIFY_TIMEOUT = 600
DEFAULT_COMPILE_PREFLIGHT_TIMEOUT = int(
    os.getenv("HERMES_GRADLE_COMPILE_PREFLIGHT_TIMEOUT_SECONDS", "180")
)
MAX_COMPILE_PREFLIGHT_TIMEOUT = 300
DEFAULT_PREFLIGHT_CAPABILITY_TIMEOUT = int(
    os.getenv("HERMES_GRADLE_PREFLIGHT_CAPABILITY_TIMEOUT_SECONDS", "30")
)
DEFAULT_PREFLIGHT_DIAGNOSTIC_TIMEOUT = int(
    os.getenv("HERMES_GRADLE_PREFLIGHT_DIAGNOSTIC_TIMEOUT_SECONDS", "15")
)
DEFAULT_PREFLIGHT_DRY_RUN_TIMEOUT = int(
    os.getenv("HERMES_GRADLE_PREFLIGHT_DRY_RUN_TIMEOUT_SECONDS", "10")
)
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
            "Run canonical Gradle verification once per unchanged executable scope, "
            "fail fast on Java compile errors before expensive targeted tests, and "
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
    p.add_argument(
        "--compile-preflight-timeout",
        type=int,
        default=DEFAULT_COMPILE_PREFLIGHT_TIMEOUT,
        help=(
            "Bounded Java compile preflight for fresh TARGETED_TEST requests. "
            "Only runs when Java production/test files are in scope."
        ),
    )
    p.add_argument("--skip-compile-preflight", action="store_true")
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


def build_engine_command(
    *,
    engine: Path,
    workspace: Path,
    mode: str,
    verification_timeout: int,
    launcher: str,
    task: str | None = None,
    tests: list[str] | None = None,
    capability_timeout: int | None = None,
    diagnostic_timeout: int | None = None,
    dry_run_timeout: int | None = None,
) -> list[str]:
    cmd = [
        sys.executable,
        str(engine),
        "--workspace",
        str(workspace),
        "--mode",
        mode,
        "--verification-timeout",
        str(verification_timeout),
        "--launcher",
        launcher,
    ]
    if task:
        cmd.extend(["--task", task])
    for selector in tests or []:
        cmd.extend(["--test", selector])
    for option, value in (
        ("--capability-timeout", capability_timeout),
        ("--diagnostic-timeout", diagnostic_timeout),
        ("--dry-run-timeout", dry_run_timeout),
    ):
        if value is not None:
            cmd.extend([option, str(value)])
    return cmd


def run_engine_streaming(cmd: list[str]) -> tuple[int, str, float]:
    """Stream engine output immediately while retaining it for evidence parsing."""
    started = time.monotonic()
    proc = subprocess.Popen(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )
    captured: list[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        captured.append(line)
        sys.stdout.write(line)
        sys.stdout.flush()
    returncode = proc.wait()
    return returncode, "".join(captured), time.monotonic() - started


def result_status(output: str, returncode: int) -> str:
    matches = re.findall(r"(?m)^GRADLE_STATUS=(PASS|FAIL|BLOCKED)\s*$", output)
    if matches:
        return matches[-1]
    return "PASS" if returncode == 0 else "FAIL"


def last_gradle_task(output: str) -> str:
    explicit = re.findall(r"(?m)^PRIMARY_LAST_TASK=([^\s]+)\s*$", output)
    if explicit:
        return explicit[-1]
    matches = re.findall(r"> Task\s+(:[^\s|]+)", output)
    return matches[-1] if matches else "UNKNOWN"


def classify_failure_phase(last_task: str, fallback: str) -> str:
    task_name = last_task.rsplit(":", 1)[-1] if last_task != "UNKNOWN" else ""
    if task_name == "compileJava":
        return "COMPILE_PRODUCTION"
    if task_name == "compileTestJava":
        return "COMPILE_TEST"
    if task_name in {"compileKotlin", "kaptKotlin", "kaptGenerateStubsKotlin"}:
        return "COMPILE_KOTLIN"
    if task_name in {"compileTestKotlin", "kaptTestKotlin", "kaptGenerateStubsTestKotlin"}:
        return "COMPILE_TEST_KOTLIN"
    if task_name.startswith("processResources") or task_name.startswith("processTestResources"):
        return "RESOURCE_PROCESSING"
    if task_name.startswith("test"):
        return "TEST_EXECUTION"
    return fallback


def java_compile_preflight(scope: list[tuple[str, Path]]) -> tuple[str, str] | None:
    java_paths = [relative for relative, _ in scope if relative.endswith(".java")]
    if not java_paths:
        return None
    if any(relative.startswith("src/test/") for relative in java_paths):
        return "COMPILE_TEST", "compileTestJava"
    if any(relative.startswith("src/main/") for relative in java_paths):
        return "COMPILE_PRODUCTION", "compileJava"
    return None


def emit_phase_start(name: str, *, task: str, timeout: int) -> None:
    print(f"VERIFICATION_PHASE_START={name}", flush=True)
    print(f"VERIFICATION_PHASE_TASK={task}", flush=True)
    print(f"VERIFICATION_PHASE_TIMEOUT_SECONDS={timeout}", flush=True)


def emit_phase_end(name: str, *, output: str, returncode: int, duration: float) -> str:
    status = result_status(output, returncode)
    print(f"VERIFICATION_PHASE_END={name}")
    print(f"VERIFICATION_PHASE_RESULT={status}")
    print(f"VERIFICATION_PHASE_DURATION_SECONDS={duration:.1f}")
    return status


def main() -> int:
    total_started = time.monotonic()
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
    if (
        args.compile_preflight_timeout < 1
        or args.compile_preflight_timeout > MAX_COMPILE_PREFLIGHT_TIMEOUT
    ):
        print(
            "ERROR: compile preflight timeout must be between 1 and "
            f"{MAX_COMPILE_PREFLIGHT_TIMEOUT} seconds",
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
        print("VERIFICATION_PHASE_START=CACHE_REUSE")
        print("VERIFICATION_PHASE_END=CACHE_REUSE")
        print("VERIFICATION_PHASE_RESULT=PASS")
        print("VERIFICATION_PHASE_DURATION_SECONDS=0.0")
        print("VERIFICATION_EVIDENCE=REUSED")
        print("PRIMARY_REUSED=true")
        if cached.get("primary_command"):
            print(f"PRIMARY_COMMAND={cached['primary_command']}")
        if cached.get("primary_duration_seconds") is not None:
            print(f"PRIMARY_ORIGINAL_DURATION_SECONDS={cached['primary_duration_seconds']}")
        print("GRADLE_STATUS=PASS")
        print("GRADLE_BLOCKER=NONE")
        print(f"VERIFICATION_TOTAL_DURATION_SECONDS={time.monotonic() - total_started:.1f}")
        return 0

    # A scope mismatch or previous non-reusable artifact invalidates the old PASS
    # before any fresh execution. A failed/blocked fresh run must never fall back
    # to an older PASS if source later changes again.
    remove_evidence(evidence)

    preflight = None
    if args.mode == "TARGETED_TEST" and not args.skip_compile_preflight:
        preflight = java_compile_preflight(scope)

    if preflight is not None:
        phase_name, preflight_task = preflight
        preflight_timeout = min(args.compile_preflight_timeout, args.verification_timeout)
        emit_phase_start(phase_name, task=preflight_task, timeout=preflight_timeout)
        preflight_cmd = build_engine_command(
            engine=engine,
            workspace=workspace,
            mode="COMPILE",
            task=preflight_task,
            verification_timeout=preflight_timeout,
            launcher=args.launcher,
            capability_timeout=(
                args.capability_timeout
                if args.capability_timeout is not None
                else DEFAULT_PREFLIGHT_CAPABILITY_TIMEOUT
            ),
            diagnostic_timeout=(
                args.diagnostic_timeout
                if args.diagnostic_timeout is not None
                else DEFAULT_PREFLIGHT_DIAGNOSTIC_TIMEOUT
            ),
            dry_run_timeout=(
                args.dry_run_timeout
                if args.dry_run_timeout is not None
                else DEFAULT_PREFLIGHT_DRY_RUN_TIMEOUT
            ),
        )
        preflight_rc, preflight_output, preflight_duration = run_engine_streaming(preflight_cmd)
        preflight_status = emit_phase_end(
            phase_name,
            output=preflight_output,
            returncode=preflight_rc,
            duration=preflight_duration,
        )
        if preflight_rc != 0 or preflight_status != "PASS":
            last_task = last_gradle_task(preflight_output)
            print(f"GRADLE_FAILURE_PHASE={classify_failure_phase(last_task, phase_name)}")
            print(f"GRADLE_FAILURE_LAST_TASK={last_task}")
            print("FAIL_FAST_STOP=true")
            print("TARGETED_TEST_SKIPPED=true")
            print("VERIFICATION_EVIDENCE=NOT_REUSABLE")
            print("PRIMARY_REUSED=false")
            print(f"VERIFICATION_TOTAL_DURATION_SECONDS={time.monotonic() - total_started:.1f}")
            return preflight_rc or 1

        try:
            after_preflight_sha = scope_sha256(scope)
        except OSError as exc:
            print(f"ERROR: failed to fingerprint verification scope after preflight: {exc}", file=sys.stderr)
            return 2
        if after_preflight_sha != before_sha:
            print("VERIFICATION_EVIDENCE=INVALIDATED")
            print("VERIFICATION_SCOPE_CHANGED_DURING_RUN=true")
            print(f"VERIFICATION_SCOPE_SHA256_AFTER={after_preflight_sha}")
            print("GRADLE_STATUS=BLOCKED")
            print("GRADLE_BLOCKER=SOURCE_CHANGED_DURING_VERIFICATION")
            print("FRESH_VERIFICATION_REQUIRED=true")
            print("TARGETED_TEST_SKIPPED=true")
            print(f"VERIFICATION_TOTAL_DURATION_SECONDS={time.monotonic() - total_started:.1f}")
            return 2

    primary_phase = "TARGETED_TEST" if args.mode == "TARGETED_TEST" else "COMPILE"
    emit_phase_start(primary_phase, task=task, timeout=args.verification_timeout)
    cmd = build_engine_command(
        engine=engine,
        workspace=workspace,
        mode=args.mode,
        task=args.task,
        tests=args.test,
        verification_timeout=args.verification_timeout,
        launcher=args.launcher,
        capability_timeout=args.capability_timeout,
        diagnostic_timeout=args.diagnostic_timeout,
        dry_run_timeout=args.dry_run_timeout,
    )
    result_returncode, result_stdout, result_duration = run_engine_streaming(cmd)
    primary_status = emit_phase_end(
        primary_phase,
        output=result_stdout,
        returncode=result_returncode,
        duration=result_duration,
    )

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
        print(f"VERIFICATION_TOTAL_DURATION_SECONDS={time.monotonic() - total_started:.1f}")
        return 2

    if result_returncode == 0 and primary_status == "PASS":
        primary_command = ""
        primary_duration = None
        for line in result_stdout.splitlines():
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
        print(f"VERIFICATION_TOTAL_DURATION_SECONDS={time.monotonic() - total_started:.1f}")
        return 0

    last_task = last_gradle_task(result_stdout)
    print(f"GRADLE_FAILURE_PHASE={classify_failure_phase(last_task, primary_phase)}")
    print(f"GRADLE_FAILURE_LAST_TASK={last_task}")
    print("VERIFICATION_EVIDENCE=NOT_REUSABLE")
    print("PRIMARY_REUSED=false")
    print(f"VERIFICATION_TOTAL_DURATION_SECONDS={time.monotonic() - total_started:.1f}")
    return result_returncode


if __name__ == "__main__":
    raise SystemExit(main())
