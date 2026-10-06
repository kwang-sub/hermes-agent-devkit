#!/usr/bin/env python3
"""Reuse a Maven PASS only when the approved request and executable scope are unchanged.

The bounded execution remains in maven_verification.py. This wrapper adds the
same fingerprint/evidence reuse layer used by Gradle without persisting raw
Maven arguments that may contain credentials.
"""
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

DEFAULT_EVIDENCE_ROOT = Path(
    os.getenv("HERMES_MAVEN_CACHED_EVIDENCE_ROOT", "/opt/data/maven/verification-evidence")
)
AUTO_SCOPE_PATHS = (
    ".hermes/toolchain.env",
    "mvnw",
    ".mvn/wrapper/maven-wrapper.properties",
    ".mvn/maven.config",
    ".mvn/jvm.config",
    "pom.xml",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--wrapper", default="./mvnw")
    parser.add_argument(
        "--mode",
        required=True,
        choices=("COMPILE", "TARGETED_TEST", "PACKAGE", "VERIFY"),
    )
    parser.add_argument(
        "--scope-path",
        action="append",
        default=[],
        required=True,
        help="Executable production/test/build path covered by this verification; repeatable.",
    )
    parser.add_argument("--timeout-seconds", type=int)
    parser.add_argument(
        "--engine",
        default=str(Path(__file__).resolve().with_name("maven_verification.py")),
    )
    parser.add_argument("--evidence-root", default=str(DEFAULT_EVIDENCE_ROOT))
    parser.add_argument("args", nargs=argparse.REMAINDER)
    return parser.parse_args()


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


def args_sha256(arguments: list[str]) -> str:
    encoded = json.dumps(arguments, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def request_sha256(
    *,
    workspace: Path,
    mode: str,
    wrapper: str,
    arguments_sha: str,
    scope_paths: list[str],
    engine_sha: str,
    helper_sha: str,
) -> str:
    payload = {
        "task_id": (os.getenv("HERMES_KANBAN_TASK") or "no-task").strip() or "no-task",
        "workspace": str(workspace),
        "mode": mode,
        "wrapper": wrapper,
        "arguments_sha256": arguments_sha,
        "scope_paths": scope_paths,
        "engine_sha256": engine_sha,
        "cached_helper_sha256": helper_sha,
    }
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
    temp.chmod(0o600)
    temp.replace(path)
    path.chmod(0o600)


def parse_field(output: str, name: str) -> str | None:
    matches = re.findall(rf"(?m)^{re.escape(name)}=(.*)$", output)
    return matches[-1].strip() if matches else None


def run_engine_streaming(cmd: list[str]) -> tuple[int, str, float]:
    started = time.monotonic()
    process = subprocess.Popen(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )
    captured: list[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        captured.append(line)
        sys.stdout.write(line)
        sys.stdout.flush()
    returncode = process.wait()
    return returncode, "".join(captured), time.monotonic() - started


def main() -> int:
    total_started = time.monotonic()
    options = parse_args()
    arguments = options.args[1:] if options.args[:1] == ["--"] else options.args
    if not arguments:
        print("ERROR: provide the approved Maven command after --", file=sys.stderr)
        return 2

    workspace = Path(options.workspace).resolve()
    engine = Path(options.engine).resolve()
    helper = Path(__file__).resolve()
    evidence_root = Path(options.evidence_root)

    if not workspace.is_dir():
        print(f"ERROR: workspace does not exist: {workspace}", file=sys.stderr)
        return 2
    if not engine.is_file():
        print(f"ERROR: Maven verification engine is missing: {engine}", file=sys.stderr)
        return 2
    if not evidence_root.is_absolute():
        print("ERROR: evidence root must be absolute", file=sys.stderr)
        return 2
    if options.timeout_seconds is not None and options.timeout_seconds <= 0:
        print("ERROR: timeout must be a positive integer", file=sys.stderr)
        return 2

    try:
        scope = resolved_scope_paths(workspace, options.scope_path)
        before_sha = scope_sha256(scope)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    arguments_sha = args_sha256(arguments)
    request_sha = request_sha256(
        workspace=workspace,
        mode=options.mode,
        wrapper=options.wrapper,
        arguments_sha=arguments_sha,
        scope_paths=[relative for relative, _ in scope],
        engine_sha=sha256_file(engine),
        helper_sha=sha256_file(helper),
    )
    evidence = evidence_path(evidence_root, workspace, request_sha)

    print(f"VERIFICATION_REQUEST_SHA256={request_sha}")
    print(f"VERIFICATION_SCOPE_SHA256={before_sha}")
    print("VERIFICATION_SCOPE_PATHS=" + ",".join(relative for relative, _ in scope))
    print(f"MAVEN_ARGUMENTS_SHA256={arguments_sha}")

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
        print("MAVEN_STATUS=PASS")
        print("MAVEN_BLOCKER=NONE")
        print(f"MAVEN_EVIDENCE={evidence}")
        if cached.get("primary_log"):
            print(f"MAVEN_LOG={cached['primary_log']}")
        if cached.get("primary_elapsed_seconds") is not None:
            print(f"PRIMARY_ORIGINAL_DURATION_SECONDS={cached['primary_elapsed_seconds']}")
        print(f"VERIFICATION_TOTAL_DURATION_SECONDS={time.monotonic() - total_started:.1f}")
        return 0

    remove_evidence(evidence)

    cmd = [
        sys.executable,
        str(engine),
        "--workspace",
        str(workspace),
        "--wrapper",
        options.wrapper,
        "--mode",
        options.mode,
    ]
    if options.timeout_seconds is not None:
        cmd.extend(["--timeout-seconds", str(options.timeout_seconds)])
    cmd.append("--")
    cmd.extend(arguments)

    print(f"VERIFICATION_PHASE_START={options.mode}", flush=True)
    returncode, output, duration = run_engine_streaming(cmd)
    status = parse_field(output, "MAVEN_STATUS") or ("PASS" if returncode == 0 else "BLOCKED")
    blocker = parse_field(output, "MAVEN_BLOCKER") or ("NONE" if status == "PASS" else "MAVEN_BUILD_OR_TEST_FAILED")
    print(f"VERIFICATION_PHASE_END={options.mode}")
    print(f"VERIFICATION_PHASE_RESULT={status}")
    print(f"VERIFICATION_PHASE_DURATION_SECONDS={duration:.1f}")

    try:
        after_sha = scope_sha256(scope)
    except OSError as exc:
        print(f"ERROR: failed to fingerprint verification scope after run: {exc}", file=sys.stderr)
        return 2

    if after_sha != before_sha:
        remove_evidence(evidence)
        print("VERIFICATION_EVIDENCE=INVALIDATED")
        print("VERIFICATION_SCOPE_CHANGED_DURING_RUN=true")
        print(f"VERIFICATION_SCOPE_SHA256_AFTER={after_sha}")
        print("MAVEN_STATUS=BLOCKED")
        print("MAVEN_BLOCKER=SOURCE_CHANGED_DURING_VERIFICATION")
        print("FRESH_VERIFICATION_REQUIRED=true")
        print("PRIMARY_REUSED=false")
        print(f"VERIFICATION_TOTAL_DURATION_SECONDS={time.monotonic() - total_started:.1f}")
        return 2

    if returncode == 0 and status == "PASS" and blocker == "NONE":
        primary_evidence = parse_field(output, "MAVEN_EVIDENCE")
        primary_log = parse_field(output, "MAVEN_LOG")
        primary_elapsed = parse_field(output, "MAVEN_ELAPSED_SECONDS")
        write_evidence(
            evidence,
            {
                "status": "PASS",
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "request_sha256": request_sha,
                "scope_sha256": before_sha,
                "scope_paths": [relative for relative, _ in scope],
                "mode": options.mode,
                "wrapper": options.wrapper,
                "arguments_sha256": arguments_sha,
                "engine_sha256": sha256_file(engine),
                "primary_evidence": primary_evidence,
                "primary_log": primary_log,
                "primary_elapsed_seconds": primary_elapsed,
            },
        )
        print("VERIFICATION_EVIDENCE=EXECUTED")
        print("PRIMARY_REUSED=false")
        print("FRESH_VERIFICATION_REQUIRED=false")
        print(f"MAVEN_CACHED_EVIDENCE={evidence}")
        print(f"MAVEN_EVIDENCE={evidence}")
        print(f"VERIFICATION_TOTAL_DURATION_SECONDS={time.monotonic() - total_started:.1f}")
        return 0

    remove_evidence(evidence)
    print("VERIFICATION_EVIDENCE=NOT_REUSABLE")
    print("PRIMARY_REUSED=false")
    print("FRESH_VERIFICATION_REQUIRED=true")
    print(f"VERIFICATION_TOTAL_DURATION_SECONDS={time.monotonic() - total_started:.1f}")
    return returncode or 2


if __name__ == "__main__":
    raise SystemExit(main())
