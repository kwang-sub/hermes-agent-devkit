#!/usr/bin/env python3
from __future__ import annotations

import io
from pathlib import Path
import subprocess
import sys
import tempfile


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
