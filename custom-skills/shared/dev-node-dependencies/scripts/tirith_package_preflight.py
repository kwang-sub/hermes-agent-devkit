#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


class TirithError(RuntimeError):
    pass


def candidate_bins(explicit: str | None) -> list[str]:
    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)
    if os.getenv("TIRITH_BIN"):
        candidates.append(os.environ["TIRITH_BIN"])
    which = shutil.which("tirith")
    if which:
        candidates.append(which)
    hermes_home = os.getenv("HERMES_HOME")
    if hermes_home:
        candidates.append(str(Path(hermes_home).expanduser() / "bin" / "tirith"))
    candidates.extend((
        str(Path.home() / ".hermes" / "bin" / "tirith"),
        "/opt/data/bin/tirith",
    ))
    seen: set[str] = set()
    result: list[str] = []
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        path = Path(candidate).expanduser()
        if path.is_file() and os.access(path, os.X_OK):
            result.append(str(path.resolve()))
    return result


def run(args: list[str], *, timeout: float = 8.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        timeout=timeout,
        check=False,
    )


def parse_json_output(proc: subprocess.CompletedProcess[str]) -> dict:
    text = (proc.stdout or "").strip()
    if not text:
        raise TirithError(f"tirith returned no JSON output (exit={proc.returncode})")
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TirithError(f"tirith returned invalid JSON (exit={proc.returncode})") from exc
    if not isinstance(value, dict):
        raise TirithError("tirith JSON result is not an object")
    return value


def check_command(binary: str, command: str) -> dict:
    proc = run([
        binary,
        "check",
        "--json",
        "--non-interactive",
        "--shell",
        "posix",
        "--",
        command,
    ])
    result = parse_json_output(proc)
    action = str(result.get("action", "")).lower()
    if action not in {"allow", "warn", "block"}:
        if proc.returncode == 0:
            action = "allow"
        elif proc.returncode == 1:
            action = "block"
        elif proc.returncode == 2:
            action = "warn"
        else:
            raise TirithError(f"unknown tirith verdict: exit={proc.returncode}, action={action or 'NONE'}")
    result["action"] = action
    return result


def findings(result: dict) -> list[dict]:
    raw = result.get("findings", [])
    return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


def only_analysis_incomplete(result: dict) -> bool:
    items = findings(result)
    return bool(items) and all(str(item.get("rule_id", "")) == "analysis_incomplete" for item in items)


def finding_ids(result: dict) -> str:
    ids = [str(item.get("rule_id", "unknown")) for item in findings(result)]
    return ",".join(ids) if ids else "NONE"


def daemon_running(binary: str) -> bool:
    try:
        return run([binary, "daemon", "status"], timeout=4.0).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def lock_path(binary: str) -> Path:
    digest = hashlib.sha256(binary.encode("utf-8")).hexdigest()[:16]
    return Path(tempfile.gettempdir()) / f"hermes-tirith-daemon-{os.getuid()}-{digest}.lock"


def ensure_daemon(binary: str) -> tuple[bool, str]:
    if daemon_running(binary):
        return True, "already-running"
    path = lock_path(binary)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        if daemon_running(binary):
            return True, "started-by-peer"
        try:
            proc = run([binary, "daemon", "start", "--detach"], timeout=10.0)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return False, f"start-failed:{type(exc).__name__}"
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout).strip().replace("\n", " ")[:240]
            return False, f"start-exit-{proc.returncode}:{detail}"
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            if daemon_running(binary):
                return True, "started"
            time.sleep(0.15)
        return False, "start-not-ready"


def emit_result(*, state: str, binary: str | None, first: dict | None, second: dict | None,
                daemon: str, retry: str, detail: str = "") -> None:
    print(f"TIRITH_PREFLIGHT={state}")
    print(f"TIRITH_BINARY={binary or 'NONE'}")
    print(f"TIRITH_FIRST_ACTION={str(first.get('action', 'NONE')) if first else 'NONE'}")
    print(f"TIRITH_FIRST_FINDINGS={finding_ids(first) if first else 'NONE'}")
    print(f"TIRITH_DAEMON={daemon}")
    print(f"TIRITH_RETRY={retry}")
    print(f"TIRITH_SECOND_ACTION={str(second.get('action', 'NONE')) if second else 'NONE'}")
    print(f"TIRITH_SECOND_FINDINGS={finding_ids(second) if second else 'NONE'}")
    if detail:
        print(f"TIRITH_DETAIL={detail}")
    print("STATUS=pass" if state in {"allow", "unavailable"} else "STATUS=blocked")


def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-scan a Node package mutation command with Tirith")
    parser.add_argument("--command", required=True)
    parser.add_argument("--tirith-bin")
    args = parser.parse_args()

    binaries = candidate_bins(args.tirith_bin)
    if not binaries:
        emit_result(state="unavailable", binary=None, first=None, second=None, daemon="not-checked", retry="none",
                    detail="tirith binary not found; Hermes terminal guard remains authoritative")
        return 0
    binary = binaries[0]

    try:
        first = check_command(binary, args.command)
    except (TirithError, OSError, subprocess.TimeoutExpired) as exc:
        emit_result(state="unavailable", binary=binary, first=None, second=None, daemon="not-checked", retry="none",
                    detail=f"preflight operational failure: {type(exc).__name__}")
        return 0

    if first["action"] == "allow":
        emit_result(state="allow", binary=binary, first=first, second=None, daemon="not-needed", retry="none")
        return 0

    if not only_analysis_incomplete(first):
        emit_result(state="approval_required", binary=binary, first=first, second=None, daemon="not-started", retry="none",
                    detail="positive warn/block finding requires normal approval; headless worker must not bypass")
        return 2

    ready, daemon_state = ensure_daemon(binary)
    if not ready:
        emit_result(state="approval_required", binary=binary, first=first, second=None, daemon=daemon_state,
                    retry="daemon-recheck-fail", detail="analysis_incomplete could not be resolved by daemon preparation")
        return 2

    try:
        second = check_command(binary, args.command)
    except (TirithError, OSError, subprocess.TimeoutExpired) as exc:
        emit_result(state="approval_required", binary=binary, first=first, second=None, daemon=daemon_state,
                    retry="daemon-recheck-fail", detail=f"daemon recheck operational failure: {type(exc).__name__}")
        return 2

    if second["action"] == "allow":
        emit_result(state="allow", binary=binary, first=first, second=second, daemon=daemon_state,
                    retry="daemon-recheck-pass")
        return 0

    emit_result(state="approval_required", binary=binary, first=first, second=second, daemon=daemon_state,
                retry="daemon-recheck-fail", detail="daemon recheck still produced warn/block; do not execute install")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
