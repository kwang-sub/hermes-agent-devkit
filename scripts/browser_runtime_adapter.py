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
import hashlib
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error

from ui_runtime.artifacts import atomic_json, attempt_directory
from ui_runtime.process import stop_owned
from ui_runtime.result import positive_seconds, replace_outcome
from ui_runtime.suite import aggregate, validate_report

from browser_dialog_trace import analyze
from managed_dialog_evidence import summarize as summarize_managed_dialog

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
    class LocalReadiness(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None  # Only inspect the owned server; never follow an auth redirect.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), LocalReadiness())
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return False
        try:
            with opener.open(
                urllib.request.Request(origin + path, headers={"User-Agent": "Hermes-DevKit-Adapter"}),
                timeout=min(1.0, max(.01, deadline-time.monotonic())),
            ) as response:
                if 200 <= response.status < 500:
                    return True
        except urllib.error.HTTPError as exc:
            if 300 <= exc.code < 500:
                return True  # Web server is alive; application route may reject the fixture.
        except (OSError, TimeoutError):
            pass
        time.sleep(0.15)
    return False

def _stop(proc: subprocess.Popen | None) -> list[str]:
    return stop_owned(proc)


def _diagnose(raw: dict) -> dict:
    if raw.get("schema") == "managed_dialog_probe_v1":
        return summarize_managed_dialog(raw)
    if raw.get("schema") == "ui_verification_v1":
        # The UI runner records the approved plan, not inferred checks from PASS rows.
        validate_report(raw)
        return aggregate(raw["checks"], raw["required"], raw["cleanup"])
    return analyze(raw)


def _await_probe(probe: subprocess.Popen, server: subprocess.Popen,
                 seconds: float) -> dict:
    """Stop waiting when the owned fixture server disappears, not at the long probe timeout."""
    deadline = time.monotonic() + seconds
    while True:
        exit_code = probe.poll()
        if exit_code is not None:
            return {'probe_exit_code': exit_code}
        if server.poll() is not None:
            return {'classification': 'SERVER_LOST'}
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {'classification': 'PROBE_TIMEOUT'}
        time.sleep(min(0.1, remaining))


def run(server_command: list[str], probe_command: list[str], artifact_dir: Path,
        task_id: str, provider: str, startup_timeout: float = 25,
        probe_timeout: float = 45, cwd: Path | None = None,
        ready_path: str = '/') -> dict:
    if not task_id or not provider:
        raise ValueError("task_id and provider required")
    positive_seconds(startup_timeout, "startup_timeout")
    positive_seconds(probe_timeout, "probe_timeout")
    if not ready_path.startswith("/") or ready_path.startswith("//") or "://" in ready_path:
        raise ValueError("ready_path must be a local absolute route")
    artifact_dir = artifact_dir.resolve()
    attempt_dir = attempt_directory(artifact_dir)
    port = _port()
    origin = f"http://127.0.0.1:{port}"
    raw_path = attempt_dir / "browser-dialog-raw.json"
    report_path = attempt_dir / "browser-runtime-report.json"
    # Preserve pre-upgrade evidence, but never feed it into a new attempt.
    stale = artifact_dir / "browser-dialog-raw.json"
    if stale.exists():
        try:
            stale.replace(attempt_dir / "previous-browser-dialog-raw.json")
        except FileNotFoundError:
            pass  # Another new attempt already archived the legacy artifact.
    report = {
        "schema": "browser_runtime_adapter_v1", "task_id": task_id,
        "provider": provider, "started_at": datetime.now(timezone.utc).isoformat(),
        "origin": origin, "execution_status": "BLOCKED_ENV",
        "classification": "NOT_EXECUTED", "cleanup": {"status": "NOT_RUN"},
        "attempt_dir": str(attempt_dir),
    }
    variables = {"origin": origin, "port": str(port), "result_file": str(raw_path)}
    proc = None
    cleanup_errors = []
    server_log = None
    probe_log = None
    try:
        # Commands are explicitly supplied for the approved fixture / provider.
        # User-controlled shell strings are never evaluated.
        with (attempt_dir / "browser-server.log").open("w", encoding="utf-8") as server_log:
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
                    with (attempt_dir / "browser-probe.log").open("w", encoding="utf-8") as probe_log:
                        probe_proc = subprocess.Popen(
                            _resolve(probe_command, variables), cwd=cwd,
                            env=env, stdin=subprocess.DEVNULL,
                            stdout=probe_log, stderr=subprocess.STDOUT,
                            start_new_session=(os.name == "posix"))
                        try:
                            report.update(_await_probe(probe_proc, proc, probe_timeout))
                        finally:
                            cleanup_errors.extend(_stop(probe_proc))
                    if report["classification"] not in ("PROBE_TIMEOUT", "SERVER_LOST"):
                        if not raw_path.is_file():
                            report["classification"] = "PROBE_EVIDENCE_MISSING"
                        else:
                            try:
                                raw = json.loads(raw_path.read_text(encoding="utf-8-sig"))
                                if not isinstance(raw, dict) or raw.get("provider") != provider:
                                    raise ValueError("provider mismatch / invalid trace")
                                report['capability_provenance'] = (
                                    'MANAGED_OFFICIAL' if raw.get('schema') == 'managed_dialog_probe_v1' else
                                    'DECLARED_UI_CHECKS' if raw.get('schema') == 'ui_verification_v1' else
                                    'LEGACY_DIALOG_OBSERVATION')
                                report['capability'] = ('managed-native-dialog-v1' if raw.get('schema') == 'managed_dialog_probe_v1' else
                                                        'ui-verification' if raw.get('schema') == 'ui_verification_v1' else 'beforeunload-dismiss')
                                environment = raw.get('environment', {})
                                report['environment_fingerprint'] = hashlib.sha256(json.dumps(
                                    {'environment': environment, 'adapter_source': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
                                    sort_keys=True, separators=(',', ':')).encode()).hexdigest()
                                if isinstance(raw.get('scope'), str): report['verification_scope'] = raw['scope']
                                diagnosed = _diagnose(raw)
                                report.update({key: diagnosed[key] for key in (
                                    "execution_status", "classification", "recovery_fingerprint", "next_action")})
                                for key in ("failed_phase", "failed_case"):
                                    if key in diagnosed:
                                        report[key] = diagnosed[key]
                                if report.get("probe_exit_code") != 0 and report["execution_status"] == "PASS":
                                    replace_outcome(report, "INCONCLUSIVE", "PROBE_EXIT_NONZERO")
                            except (ValueError, OSError, UnicodeError, KeyError, TypeError) as exc:
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
    except BaseException:
        replace_outcome(report, "INCONCLUSIVE", "RUNTIME_INTERRUPTED")
        raise
    finally:
        errors = cleanup_errors + _stop(proc)
        report["cleanup"] = {"status": "PASS" if not errors else "WARNING", "errors": errors}
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        if errors and report["execution_status"] == "PASS":
            replace_outcome(report, "INCONCLUSIVE", "CLEANUP_UNCONFIRMED")
        else:
            replace_outcome(report, report["execution_status"], report["classification"])
        if report.get('capability_provenance') == 'LEGACY_DIALOG_OBSERVATION' and report['execution_status'] == 'PASS':
            report['next_action'] = 'REVIEW_EVIDENCE'
        atomic_json(report_path, report)
        atomic_json(artifact_dir / "browser-runtime-report.json", report)
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
    def interrupt(signum, frame):
        raise KeyboardInterrupt("runtime cancellation")
    if os.name == "posix":
        signal.signal(signal.SIGTERM, interrupt)
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
