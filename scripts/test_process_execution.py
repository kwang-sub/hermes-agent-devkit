#!/usr/bin/env python3
from __future__ import annotations

import io
from pathlib import Path
import subprocess
import sys
import tempfile
import time


REPO_ROOT = Path(__file__).resolve().parents[1]
LIB_ROOT = REPO_ROOT / "custom-skills" / "_lib"
if str(LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(LIB_ROOT))

from process_execution import run_capture, run_inherit, run_to_stream


def test_capture_success() -> None:
    result, stdout, stderr = run_capture(
        [
            sys.executable,
            "-c",
            "import sys; print('OUT'); print('ERR', file=sys.stderr)",
        ],
        cwd=REPO_ROOT,
        timeout_seconds=5,
    )
    assert result.returncode == 0
    assert not result.timed_out
    assert stdout.strip() == "OUT"
    assert stderr.strip() == "ERR"


def test_capture_timeout() -> None:
    result, _stdout, _stderr = run_capture(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        cwd=REPO_ROOT,
        timeout_seconds=1,
    )
    assert result.timed_out
    assert result.duration < 10


def test_timeout_kills_child_when_process_leader_exits_first() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        pid_file = Path(tmp) / "child.pid"
        parent_code = (
            "import pathlib, subprocess, sys, time; "
            "child=\"import os, pathlib, signal, sys, time; "
            "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
            "pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(60)\"; "
            "subprocess.Popen([sys.executable, '-c', child, sys.argv[1]]); "
            "p=pathlib.Path(sys.argv[1]); "
            "deadline=time.monotonic()+2; "
            "\nwhile not p.exists() and time.monotonic() < deadline: time.sleep(0.01)\n"
            "time.sleep(60)"
        )
        result, _stdout, _stderr = run_capture(
            [sys.executable, "-c", parent_code, str(pid_file)],
            cwd=REPO_ROOT,
            timeout_seconds=1,
        )
        assert result.timed_out
        assert pid_file.is_file()
        child_pid = int(pid_file.read_text(encoding="utf-8"))
        child_proc = Path("/proc") / str(child_pid)
        deadline = time.monotonic() + 2
        while child_proc.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not child_proc.exists(), f"timed-out child process survived cleanup: pid={child_pid}"


def test_stream_redirection() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "execution.log"
        with path.open("wb") as stream:
            result = run_to_stream(
                [
                    sys.executable,
                    "-c",
                    "import sys; print('STDOUT'); print('STDERR', file=sys.stderr)",
                ],
                cwd=REPO_ROOT,
                stream=stream,
                timeout_seconds=5,
            )
        assert result.returncode == 0
        assert not result.timed_out
        text = path.read_text(encoding="utf-8")
        assert "STDOUT" in text
        assert "STDERR" in text


def test_inherited_exit_code() -> None:
    result = run_inherit(
        [sys.executable, "-c", "raise SystemExit(3)"],
        cwd=REPO_ROOT,
        timeout_seconds=5,
    )
    assert result.returncode == 3
    assert not result.timed_out


def test_adapters_use_shared_execution() -> None:
    contracts = {
        REPO_ROOT
        / "custom-skills/coder/dev-implement-plan/scripts/gradle_verification.py": (
            "from process_execution import run_capture as run_process_capture",
            "run_process_capture(",
        ),
        REPO_ROOT
        / "custom-skills/coder/dev-implement-plan/scripts/maven_verification.py": (
            "from process_execution import run_to_stream",
            "run_to_stream(",
        ),
        REPO_ROOT
        / "custom-skills/shared/dev-node-dependencies/scripts/node_runtime.py": (
            "from process_execution import run_inherit",
            "run_inherit(",
            "HERMES_NODE_COMMAND_TIMEOUT_SECONDS",
        ),
    }
    for path, required in contracts.items():
        source = path.read_text(encoding="utf-8")
        missing = [value for value in required if value not in source]
        assert not missing, f"{path} missing shared execution contract: {missing}"


def main() -> int:
    tests = (
        test_capture_success,
        test_capture_timeout,
        test_timeout_kills_child_when_process_leader_exits_first,
        test_stream_redirection,
        test_inherited_exit_code,
        test_adapters_use_shared_execution,
    )
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
