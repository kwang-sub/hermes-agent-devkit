#!/usr/bin/env python3
"""Run an approved Maven command once with bounded time and durable evidence.

Workspace/ownership/approval validation remains in the existing worker gates.
This helper never updates Kanban, installs a system Maven, or switches providers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
import uuid


MAX_TAIL_BYTES = 128 * 1024


def positive_seconds(value: str) -> int:
    try:
        seconds = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("timeout must be a positive integer") from exc
    if seconds <= 0:
        raise argparse.ArgumentTypeError("timeout must be a positive integer")
    return seconds


def stop_group(process: subprocess.Popen[bytes]) -> None:
    """Reap Maven and its children before returning a timeout result."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
    finally:
        # A child may survive after the original launcher has already exited.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def tail(path: Path) -> str:
    with path.open("rb") as stream:
        stream.seek(0, os.SEEK_END)
        stream.seek(max(0, stream.tell() - MAX_TAIL_BYTES))
        return stream.read(MAX_TAIL_BYTES).decode("utf-8", errors="replace")


def classify(log: str) -> str:
    explicit = re.findall(r"^MAVEN_BLOCKER=([A-Z0-9_]+)\s*$", log, re.MULTILINE)
    if explicit:
        return explicit[-1]
    lower = log.casefold()
    if "offline" in lower and any(value in lower for value in ("could not resolve", "cannot access", "not been downloaded")):
        return "MAVEN_OFFLINE_DEPENDENCY_MISSING"
    if any(value in lower for value in ("could not resolve dependencies", "could not resolve plugin", "non-resolvable parent pom", "could not transfer artifact")):
        return "MAVEN_DEPENDENCY_RESOLUTION_FAILED"
    return "MAVEN_BUILD_OR_TEST_FAILED"


def verify(workspace: Path, wrapper: str, args: list[str], launcher: Path,
           evidence_root: Path, timeout_seconds: int) -> dict[str, object]:
    """Execute only the supplied argv; project configuration stays authoritative."""
    workspace = workspace.resolve(strict=True)
    if not workspace.is_dir():
        raise ValueError("workspace must be an existing directory")
    if not launcher.is_file() or not os.access(launcher, os.X_OK):
        return {"status": "BLOCKED", "blocker": "MAVEN_LAUNCHER_MISSING", "executed": False}
    if not evidence_root.is_absolute():
        raise ValueError("evidence root must be an absolute path")
    key = hashlib.sha256(str(workspace).encode()).hexdigest()[:16]
    directory = evidence_root / key / uuid.uuid4().hex
    directory.mkdir(parents=True, mode=0o700)
    log_path = directory / "maven.log"
    command = [str(launcher), wrapper, *args]
    started = time.monotonic()
    code: int | None = None
    blocker = "NONE"
    executed = False
    with log_path.open("wb") as stream:
        log_path.chmod(0o600)
        try:
            process = subprocess.Popen(command, cwd=workspace, stdout=stream,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            executed = True
            try:
                code = process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                stop_group(process)
                code = process.returncode
                blocker = "MAVEN_COMMAND_TIMEOUT"
            except BaseException:
                stop_group(process)
                raise
        except OSError:
            blocker = "MAVEN_LAUNCHER_EXEC_FAILED"
    if blocker == "NONE" and code != 0:
        blocker = classify(tail(log_path))
    result: dict[str, object] = {
        "status": "PASS" if code == 0 and blocker == "NONE" else "BLOCKED",
        "blocker": blocker, "executed": executed, "exit_code": code,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "timeout_seconds": timeout_seconds, "workspace": str(workspace),
        "launcher": str(launcher), "log": str(log_path),
        # Do not serialize argv: approved settings/arguments may contain secrets.
        "command_sha256": hashlib.sha256(json.dumps(command).encode()).hexdigest(),
    }
    receipt = directory / "result.json"
    result["evidence"] = str(receipt)
    receipt.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    receipt.chmod(0o600)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--wrapper", default="./mvnw")
    parser.add_argument("--mode", required=True, choices=("COMPILE", "TARGETED_TEST", "PACKAGE", "VERIFY"))
    parser.add_argument("--timeout-seconds", type=positive_seconds)
    parser.add_argument("args", nargs=argparse.REMAINDER, help="approved Maven arguments after --")
    options = parser.parse_args()
    arguments = options.args[1:] if options.args[:1] == ["--"] else options.args
    if not arguments:
        parser.error("provide the approved Maven command after --")
    # --version/--help are diagnostics, not compile/test evidence.
    if any(value in {"-v", "--version", "-h", "--help"} for value in arguments):
        parser.error("diagnostic-only flags cannot produce verification evidence")
    default = "300" if options.mode == "COMPILE" else "600"
    env_name = "HERMES_MAVEN_COMPILE_TIMEOUT_SECONDS" if options.mode == "COMPILE" else "HERMES_MAVEN_VERIFY_TIMEOUT_SECONDS"
    try:
        seconds = options.timeout_seconds or positive_seconds(os.environ.get(env_name, default))
        root = Path(os.environ.get("HERMES_MAVEN_ROOT", "/opt/data/maven"))
        result = verify(options.workspace, options.wrapper, arguments,
                        Path("/usr/local/bin/hermes-maven"), root / "verification", seconds)
    except (ValueError, OSError, argparse.ArgumentTypeError) as exc:
        print("MAVEN_STATUS=BLOCKED\nMAVEN_BLOCKER=MAVEN_VERIFICATION_CONTEXT_INVALID")
        print(f"MAVEN_ERROR_TYPE={type(exc).__name__}")
        return 2
    print(f"MAVEN_STATUS={result['status']}\nMAVEN_BLOCKER={result['blocker']}")
    print(f"MAVEN_MODE={options.mode}\nMAVEN_EXECUTED={str(result['executed']).lower()}")
    for field in ("exit_code", "timeout_seconds", "elapsed_seconds", "log", "evidence"):
        if field in result:
            print(f"MAVEN_{field.upper()}={result[field]}")
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
