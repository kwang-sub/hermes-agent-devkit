#!/usr/bin/env python3
"""Isolated browser verification process adapter.

Starts an approved localhost fixture server, waits for readiness, invokes an
approved browser probe with argv (never a shell), classifies its event JSON,
and always stops only its own server process group. This does NOT secretly
switch browser providers or make unverified ACs PASS.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error

from browser_dialog_trace import analyze

def _argv(value: str, name: str) -> list[str]:
    try:
        args = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(name + " must be a JSON argv array") from exc
    if not isinstance(args, list) or not args or any(not isinstance(x, str) or not x for x in args):
        raise ValueError(name + " must contain nonempty strings")
    return args

def _port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]

def _resolve(args: list[str], variables: dict[str, str]) -> list[str]:
    for value in args:
        for variable in ("{origin}", "{port}", "{result_file}"):
            if variable in value and variable[1:-1] not in variables:
                raise ValueError("unknown variable " + variable)
    return [item.replace("{origin}", variables["origin"])
                .replace("{port}", variables["port"])
                .replace("{result_file}", variables["result_file"]) for item in args]

def _ready(origin: str, proc: subprocess.Popen, seconds: float, path: str = '/') -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(
                urllib.request.Request(origin + path, headers={"User-Agent": "Hermes-DevKit-Adapter"}),
                timeout=1.0,
            ) as response:
                if 200 <= response.status < 500:
                    return True
        except urllib.error.HTTPError as exc:
            if 400 <= exc.code < 500:
                return True  # Web server is alive; application route may reject the fixture.
        except (OSError, TimeoutError):
            pass
        time.sleep(0.15)
    return False

def _stop(proc: subprocess.Popen | None) -> list[str]:
    if proc is None:
        return []
    errors = []
    # A child browser may survive after the short-lived probe launcher exits;
    # the process group is owned by this invocation, never a shared Hermes PGID.
    if proc.poll() is not None and os.name != "posix":
        return errors
    try:
        if os.name == "posix":
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                return errors
        else:
            proc.terminate()
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            if os.name == "posix":
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
            proc.wait(timeout=3)
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append(type(exc).__name__)
    except OSError as exc:
        errors.append(type(exc).__name__)
    return errors

def run(server_command: list[str], probe_command: list[str], artifact_dir: Path,
        task_id: str, provider: str, startup_timeout: float = 25,
        probe_timeout: float = 45, cwd: Path | None = None,
        ready_path: str = '/') -> dict:
    if not task_id or not provider:
        raise ValueError("task_id and provider required")
    if startup_timeout <= 0 or probe_timeout <= 0:
        raise ValueError("timeouts must be positive")
    if not ready_path.startswith("/") or ready_path.startswith("//") or "://" in ready_path:
        raise ValueError("ready_path must be a local absolute route")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    port = _port()
    origin = f"http://127.0.0.1:{port}"
    raw_path = artifact_dir / "browser-dialog-raw.json"
    report_path = artifact_dir / "browser-runtime-report.json"
    # Never accept stale PASS evidence.
    if raw_path.exists():
        raw_path.unlink()
    report = {
        "schema": "browser_runtime_adapter_v1", "task_id": task_id,
        "provider": provider, "started_at": datetime.now(timezone.utc).isoformat(),
        "origin": origin, "execution_status": "BLOCKED_ENV",
        "classification": "NOT_EXECUTED", "cleanup": {"status": "NOT_RUN"},
    }
    variables = {"origin": origin, "port": str(port), "result_file": str(raw_path)}
    proc = None
    server_log = None
    probe_log = None
    try:
        # Commands are explicitly supplied for the approved fixture / provider.
        # User-controlled shell strings are never evaluated.
        with (artifact_dir / "browser-server.log").open("w", encoding="utf-8") as server_log:
            env = os.environ.copy()
            env["BROWSER_TEST_ORIGIN"] = origin
            env["BROWSER_TEST_PORT"] = str(port)
            proc = subprocess.Popen(_resolve(server_command, variables),
                                    cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                    stdout=server_log, stderr=subprocess.STDOUT,
                                    start_new_session=(os.name == "posix"))
            if not _ready(origin, proc, startup_timeout, ready_path):
                report["classification"] = "SERVER_NOT_READY"
            else:
                report["server_ready"] = True
                try:
                    with (artifact_dir / "browser-probe.log").open("w", encoding="utf-8") as probe_log:
                        probe_proc = subprocess.Popen(
                            _resolve(probe_command, variables), cwd=cwd,
                            env=env, stdin=subprocess.DEVNULL,
                            stdout=probe_log, stderr=subprocess.STDOUT,
                            start_new_session=(os.name == "posix"))
                        try:
                            report["probe_exit_code"] = probe_proc.wait(timeout=probe_timeout)
                        except subprocess.TimeoutExpired:
                            report["classification"] = "PROBE_TIMEOUT"
                        finally:
                            _stop(probe_proc)
                    if report["classification"] != "PROBE_TIMEOUT":
                        if not raw_path.is_file():
                            report["classification"] = "PROBE_EVIDENCE_MISSING"
                        else:
                            try:
                                raw = json.loads(raw_path.read_text(encoding="utf-8"))
                                if not isinstance(raw, dict) or raw.get("provider") != provider:
                                    raise ValueError("provider mismatch / invalid trace")
                                diagnosed = analyze(raw)
                                report.update({key: diagnosed[key] for key in (
                                    "execution_status", "classification", "recovery_fingerprint", "next_action")})
                                if report.get("probe_exit_code") != 0 and report["execution_status"] == "PASS":
                                    report["execution_status"] = "INCONCLUSIVE"
                                    report["classification"] = "PROBE_EXIT_NONZERO"
                            except (ValueError, OSError, UnicodeError) as exc:
                                report["classification"] = "PROBE_EVIDENCE_INVALID"
                                report["error"] = type(exc).__name__
                except (OSError, ValueError) as exc:
                    report["classification"] = "PROBE_LAUNCH_FAILED"
                    report["error"] = type(exc).__name__
        # Closing owned file handles occurs before process termination, but the
        # process group is still alive and is stopped in finally below.
    except (OSError, ValueError) as exc:
        report["classification"] = "RUNTIME_LAUNCH_FAILED"
        report["error"] = type(exc).__name__
    finally:
        errors = _stop(proc)
        report["cleanup"] = {"status": "PASS" if not errors else "WARNING", "errors": errors}
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-command", required=True, help="JSON argv; {port} may be substituted")
    parser.add_argument("--probe-command", required=True, help="JSON argv; {origin}, {result_file} may be substituted")
    parser.add_argument("--artifact-dir", required=True, type=Path)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--cwd", type=Path)
    parser.add_argument("--startup-timeout", type=float, default=25)
    parser.add_argument("--probe-timeout", type=float, default=45)
    parser.add_argument("--ready-path", default="/")
    args = parser.parse_args()
    try:
        result = run(_argv(args.server_command, "server-command"), _argv(args.probe_command, "probe-command"),
                     args.artifact_dir, args.task_id, args.provider,
                     args.startup_timeout, args.probe_timeout, args.cwd, args.ready_path)
    except (ValueError, OSError) as exc:
        print("BROWSER_RUNTIME_ADAPTER=INVALID: " + type(exc).__name__)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["execution_status"] == "PASS" else 2

if __name__ == "__main__":
    raise SystemExit(main())
