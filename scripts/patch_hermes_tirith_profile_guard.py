#!/usr/bin/env python3
"""Patch Hermes Tirith guard for routed-profile subprocess parity and bounded daemon recovery."""

from __future__ import annotations

import argparse
import contextvars
import importlib.util
import json
import py_compile
import subprocess
import sys
import tempfile
import threading
import types
from pathlib import Path

MARKER = "DEVKIT_TIRITH_PROFILE_GUARD_V1"

HELPERS = r'''
# DEVKIT_TIRITH_PROFILE_GUARD_V1: keep Tirith child state aligned with the routed Hermes profile.
def _devkit_tirith_subprocess_env() -> dict[str, str]:
    from hermes_constants import apply_subprocess_home_env, get_hermes_home_override

    env = os.environ.copy()
    if override := get_hermes_home_override():
        env["HERMES_HOME"] = override
    apply_subprocess_home_env(env)
    return env


def _devkit_tirith_run_check(tirith_path: str, command: str, timeout: float,
                              *, env: dict[str, str] | None = None):
    return subprocess.run(
        [tirith_path, "check", "--json", "--non-interactive", "--shell", "posix", "--", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        stdin=subprocess.DEVNULL,
        env=env if env is not None else _devkit_tirith_subprocess_env(),
    )


def _devkit_tirith_run_control(tirith_path: str, args: list[str], timeout: float,
                                env: dict[str, str]):
    return subprocess.run(
        [tirith_path, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        stdin=subprocess.DEVNULL,
        env=env,
    )


def _devkit_only_analysis_incomplete(findings: list) -> bool:
    return bool(findings) and all(
        isinstance(item, dict) and item.get("rule_id") == "analysis_incomplete"
        for item in findings
    )


def _devkit_parse_tirith_result(result):
    action = {0: "allow", 1: "block", 2: "warn"}.get(result.returncode)
    if action is None:
        return None
    findings, summary = [], ""
    try:
        data = json.loads(result.stdout) if result.stdout.strip() else {}
        raw_findings = data.get("findings", []) if isinstance(data, dict) else []
        findings = raw_findings[:_MAX_FINDINGS] if isinstance(raw_findings, list) else []
        summary = (data.get("summary", "") or "")[:_MAX_SUMMARY_LEN] if isinstance(data, dict) else ""
    except (json.JSONDecodeError, AttributeError):
        summary = {
            "block": "security issue detected (details unavailable)",
            "warn": "security warning detected (details unavailable)",
        }.get(action, "")
    return action, findings, summary


def _devkit_tirith_daemon_recheck(tirith_path: str, command: str, timeout: float):
    """One bounded daemon recovery for analysis_incomplete; None preserves the first verdict."""
    env = _devkit_tirith_subprocess_env()
    control_timeout = max(1.0, min(float(timeout), 4.0))
    try:
        status = _devkit_tirith_run_control(tirith_path, ["daemon", "status"], control_timeout, env)
        if status.returncode != 0:
            started = _devkit_tirith_run_control(
                tirith_path, ["daemon", "start", "--detach"], max(control_timeout, 3.0), env)
            if started.returncode != 0:
                # Another process may have won the start race; status is authoritative.
                status = _devkit_tirith_run_control(tirith_path, ["daemon", "status"], control_timeout, env)
                if status.returncode != 0:
                    return None
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                status = _devkit_tirith_run_control(tirith_path, ["daemon", "status"], control_timeout, env)
                if status.returncode == 0:
                    break
                time.sleep(0.1)
            else:
                return None
        return _devkit_tirith_run_check(tirith_path, command, timeout, env=env)
    except (OSError, subprocess.TimeoutExpired):
        return None
'''.lstrip("\n")

RETRY_BLOCK = r'''
    # DEVKIT_TIRITH_PROFILE_GUARD_V1: recover only a pure runtime threat-intelligence incomplete verdict.
    # Positive findings are never retried/bypassed; operational daemon failures preserve the first verdict.
    if action in {"warn", "block"} and _devkit_only_analysis_incomplete(findings):
        retry_result = _devkit_tirith_daemon_recheck(tirith_path, command, timeout)
        if retry_result is not None:
            retry_verdict = _devkit_parse_tirith_result(retry_result)
            if retry_verdict is not None:
                action, findings, summary = retry_verdict
                if action == "allow":
                    _crash_count = 0
                logger.debug("tirith analysis_incomplete daemon recheck action=%s", action)
'''.rstrip("\n") + "\n\n"


def _find_suppression_anchor(text: str, start: int) -> int:
    candidates = (
        "    # .app is a legitimate gTLD:",
        "    # Suppress warn verdicts",
    )
    positions = [text.find(anchor, start) for anchor in candidates]
    positions = [pos for pos in positions if pos >= 0]
    if not positions:
        raise RuntimeError("tirith guard: .app suppression anchor not found")
    return min(positions)


def patch_text(text: str) -> str:
    if MARKER in text:
        return text
    func_anchor = "def check_command_security(command: str) -> dict:"
    func_pos = text.find(func_anchor)
    if func_pos < 0:
        raise RuntimeError("tirith guard: check_command_security anchor not found")
    if "import time" not in text:
        raise RuntimeError("tirith guard: upstream time import is required")

    text = text[:func_pos] + HELPERS + "\n\n" + text[func_pos:]
    func_pos = text.find(func_anchor)

    run_start = text.find("        result = subprocess.run(", func_pos)
    if run_start < 0:
        raise RuntimeError("tirith guard: check subprocess anchor not found")
    except_pos = text.find("    except OSError as exc:", run_start)
    if except_pos < 0:
        raise RuntimeError("tirith guard: subprocess except anchor not found")
    run_block = text[run_start:except_pos]
    if '[tirith_path, "check"' not in run_block or "stdin=subprocess.DEVNULL" not in run_block:
        raise RuntimeError("tirith guard: unexpected check subprocess shape")
    text = text[:run_start] + "        result = _devkit_tirith_run_check(tirith_path, command, timeout)\n" + text[except_pos:]

    func_pos = text.find(func_anchor)
    suppression_pos = _find_suppression_anchor(text, func_pos)
    text = text[:suppression_pos] + RETRY_BLOCK + text[suppression_pos:]
    return text


def patch_file(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return "already-patched"
    patched = patch_text(text)
    if patched.count(MARKER) < 2:
        raise RuntimeError("tirith guard: marker contract incomplete after patch")
    path.write_text(patched, encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="tirith-profile-guard-compile-") as tmp:
        py_compile.compile(str(path), cfile=str(Path(tmp) / "tirith_security.pyc"), doraise=True)
    return "patched"


def _fixture_source(*, latest_style: bool) -> str:
    suppress = (
        '''    # .app is a legitimate gTLD: fixture\n    if action == "warn" and findings and all(_is_app_tld_finding(f) for f in findings):\n        return _verdict("allow")\n    return _verdict(action, summary, findings)\n'''
        if latest_style
        else
        '''    # Suppress warn verdicts fixture\n    if action == "warn" and findings:\n        non_suppressible = [f for f in findings if not _is_app_tld_finding(f)]\n        if not non_suppressible:\n            action, findings, summary = "allow", [], ""\n    return {"action": action, "findings": findings, "summary": summary}\n'''
    )
    return '''import json\nimport logging\nimport os\nimport subprocess\nimport time\nlogger=logging.getLogger(__name__)\n_MAX_FINDINGS=50\n_MAX_SUMMARY_LEN=500\n_crash_count=0\n_circuit_open=False\ndef _load_security_config(): return {"tirith_enabled": True, "tirith_path": "/tirith", "tirith_timeout": 5, "tirith_fail_open": False}\ndef is_platform_supported(): return True\ndef _resolve_tirith_path(_): return "/tirith"\ndef _warn_once(*a, **k): pass\ndef _record_tirith_crash(): pass\ndef _verdict(action, summary="", findings=None): return {"action": action, "findings": [] if findings is None else findings, "summary": summary}\ndef _fail(fail_open, open_summary, closed_summary): return _verdict("allow", open_summary) if fail_open else _verdict("block", closed_summary)\ndef _crash(fail_open, open_summary, closed_summary): return _fail(fail_open, open_summary, closed_summary)\ndef _is_app_tld_finding(_): return False\n\ndef check_command_security(command: str) -> dict:\n    global _crash_count\n    cfg=_load_security_config()\n    if not cfg["tirith_enabled"]: return _verdict("allow")\n    if _circuit_open: return _verdict("allow", "tirith disabled (circuit breaker)")\n    if not is_platform_supported(): return _verdict("allow")\n    tirith_path=_resolve_tirith_path(cfg["tirith_path"])\n    timeout, fail_open=cfg["tirith_timeout"], cfg["tirith_fail_open"]\n    if tirith_path is None: return _fail(fail_open, "unavailable", "blocked")\n    try:\n        result = subprocess.run(\n            [tirith_path, "check", "--json", "--non-interactive", "--shell", "posix", "--", command],\n            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout,\n            stdin=subprocess.DEVNULL)\n    except OSError as exc:\n        return _crash(fail_open, str(exc), str(exc))\n    except subprocess.TimeoutExpired:\n        return _crash(fail_open, "timeout", "timeout")\n    action={0:"allow",1:"block",2:"warn"}.get(result.returncode)\n    if action is None: return _crash(fail_open, "exit", "exit")\n    if action == "allow": _crash_count=0\n    findings=[]; summary=""\n    try:\n        data=json.loads(result.stdout) if result.stdout.strip() else {}\n        findings=data.get("findings", [])[:_MAX_FINDINGS]\n        summary=(data.get("summary", "") or "")[:_MAX_SUMMARY_LEN]\n    except (json.JSONDecodeError, AttributeError):\n        summary="details unavailable"\n''' + suppress


def _completed(argv, code: int, payload: dict | None = None):
    stdout = "" if payload is None else json.dumps(payload)
    return subprocess.CompletedProcess(argv, code, stdout=stdout, stderr="")


def _load_fixture(path: Path, home_var: contextvars.ContextVar):
    fake = types.ModuleType("hermes_constants")
    fake.get_hermes_home_override = lambda: home_var.get()

    def apply_home(env):
        override = env.get("HERMES_HOME") or home_var.get()
        if override:
            env["HOME"] = f"{override}/home"

    fake.apply_subprocess_home_env = apply_home
    previous = sys.modules.get("hermes_constants")
    sys.modules["hermes_constants"] = fake
    spec = importlib.util.spec_from_file_location(f"tirith_fixture_{id(path)}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module, previous


def _assert_profile_env(module, home_var: contextvars.ContextVar) -> None:
    calls: list[tuple[list[str], dict[str, str]]] = []
    check_count = 0

    def fake_run(argv, **kwargs):
        nonlocal check_count
        env = dict(kwargs.get("env") or {})
        calls.append((list(argv), env))
        if argv[1:3] == ["daemon", "status"]:
            daemon_status_calls = sum(1 for value, _ in calls if value[1:3] == ["daemon", "status"])
            return _completed(argv, 1 if daemon_status_calls == 1 else 0)
        if argv[1:4] == ["daemon", "start", "--detach"]:
            return _completed(argv, 0)
        if argv[1] == "check":
            check_count += 1
            if check_count == 1:
                return _completed(argv, 2, {"findings": [{"rule_id": "analysis_incomplete"}], "summary": "incomplete"})
            return _completed(argv, 0, {"findings": [], "summary": ""})
        raise AssertionError(argv)

    module.subprocess.run = fake_run
    token = home_var.set("/profiles/coder")
    try:
        result = module.check_command_security("npm install @supabase/ssr")
    finally:
        home_var.reset(token)
    assert result["action"] == "allow", result
    assert check_count == 2, calls
    assert any(value[1:4] == ["daemon", "start", "--detach"] for value, _ in calls), calls
    for _, env in calls:
        assert env.get("HERMES_HOME") == "/profiles/coder", env
        assert env.get("HOME") == "/profiles/coder/home", env


def _assert_positive_finding_not_retried(module, home_var: contextvars.ContextVar) -> None:
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        return _completed(argv, 2, {"findings": [{"rule_id": "malware_package"}], "summary": "bad"})

    module.subprocess.run = fake_run
    token = home_var.set("/profiles/coder")
    try:
        result = module.check_command_security("npm install bad")
    finally:
        home_var.reset(token)
    assert result["action"] == "warn", result
    assert len(calls) == 1 and calls[0][1] == "check", calls


def _assert_incomplete_remains_blocked(module, home_var: contextvars.ContextVar) -> None:
    check_count = 0

    def fake_run(argv, **kwargs):
        nonlocal check_count
        if argv[1:3] == ["daemon", "status"]:
            return _completed(argv, 0)
        if argv[1] == "check":
            check_count += 1
            return _completed(argv, 2, {"findings": [{"rule_id": "analysis_incomplete"}], "summary": "still incomplete"})
        raise AssertionError(argv)

    module.subprocess.run = fake_run
    token = home_var.set("/profiles/coder")
    try:
        result = module.check_command_security("npm install x")
    finally:
        home_var.reset(token)
    assert result["action"] == "warn", result
    assert check_count == 2


def _assert_profile_isolation(module, home_var: contextvars.ContextVar) -> None:
    seen = []
    lock = threading.Lock()

    def fake_run(argv, **kwargs):
        if argv[1] != "check":
            raise AssertionError(argv)
        with lock:
            seen.append((threading.current_thread().name, kwargs["env"].get("HERMES_HOME"), kwargs["env"].get("HOME")))
        return _completed(argv, 0, {"findings": [], "summary": ""})

    module.subprocess.run = fake_run
    errors = []

    def worker(profile):
        token = home_var.set(f"/profiles/{profile}")
        try:
            result = module.check_command_security("echo ok")
            assert result["action"] == "allow"
        except BaseException as exc:
            errors.append(exc)
        finally:
            home_var.reset(token)

    threads = [threading.Thread(target=worker, args=(profile,), name=profile) for profile in ("coder", "reviewer")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors, errors
    assert sorted((profile, hermes_home, home) for profile, hermes_home, home in seen) == [
        ("coder", "/profiles/coder", "/profiles/coder/home"),
        ("reviewer", "/profiles/reviewer", "/profiles/reviewer/home"),
    ], seen


def self_test() -> None:
    for latest_style in (False, True):
        with tempfile.TemporaryDirectory(prefix="tirith-profile-guard-test-") as tmp:
            path = Path(tmp) / "tirith_security.py"
            path.write_text(_fixture_source(latest_style=latest_style), encoding="utf-8")
            assert patch_file(path) == "patched"
            assert patch_file(path) == "already-patched"
            text = path.read_text(encoding="utf-8")
            for term in (MARKER, "_devkit_tirith_subprocess_env", "_devkit_tirith_daemon_recheck", "env=env"):
                assert term in text, term
            home_var = contextvars.ContextVar("home", default=None)
            module, previous = _load_fixture(path, home_var)
            try:
                _assert_profile_env(module, home_var)
                _assert_positive_finding_not_retried(module, home_var)
                _assert_incomplete_remains_blocked(module, home_var)
                _assert_profile_isolation(module, home_var)
            finally:
                if previous is None:
                    sys.modules.pop("hermes_constants", None)
                else:
                    sys.modules["hermes_constants"] = previous


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test == (args.target is not None):
        parser.error("provide exactly one of --self-test or target")
    return args


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        print("Hermes Tirith profile guard patch self-test passed")
        return
    state = patch_file(args.target.resolve())
    print(f"Hermes Tirith profile guard patch {state}: {args.target}")


if __name__ == "__main__":
    main()
