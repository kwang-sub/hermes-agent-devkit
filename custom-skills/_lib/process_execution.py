from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import time
from dataclasses import dataclass
from typing import BinaryIO, Callable, Mapping, TextIO


@dataclass
class ProcessExecutionResult:
    returncode: int | None
    duration: float
    timed_out: bool = False


TimeoutProbe = Callable[[subprocess.Popen], None]


def _process_group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def terminate_process_group(
    process: subprocess.Popen,
    *,
    terminate_timeout: float = 3.0,
    kill_timeout: float = 3.0,
) -> None:
    """Terminate the whole managed process session, even if its leader exits first."""
    pgid = process.pid
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        if process.poll() is None:
            try:
                process.wait(timeout=kill_timeout)
            except subprocess.TimeoutExpired:
                pass
        return

    deadline = time.monotonic() + terminate_timeout
    while _process_group_exists(pgid) and time.monotonic() < deadline:
        remaining = max(0.0, deadline - time.monotonic())
        if process.poll() is None:
            try:
                process.wait(timeout=min(0.1, remaining))
            except subprocess.TimeoutExpired:
                pass
        else:
            time.sleep(min(0.05, remaining))

    if _process_group_exists(pgid):
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    if process.poll() is None:
        try:
            process.wait(timeout=kill_timeout)
        except subprocess.TimeoutExpired:
            pass


def _handle_timeout(
    process: subprocess.Popen,
    timeout_probe: TimeoutProbe | None,
) -> None:
    if timeout_probe is not None:
        try:
            timeout_probe(process)
        except Exception:
            # Diagnostics must never prevent process cleanup.
            pass
    terminate_process_group(process)


def run_capture(
    command: list[str],
    *,
    cwd: Path,
    timeout_seconds: int | None,
    env: Mapping[str, str] | None = None,
    timeout_probe: TimeoutProbe | None = None,
) -> tuple[ProcessExecutionResult, str, str]:
    """Run a command in an isolated process session and capture text output."""
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        env=None if env is None else dict(env),
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
        return (
            ProcessExecutionResult(
                returncode=process.returncode,
                duration=time.monotonic() - started,
            ),
            stdout,
            stderr,
        )
    except subprocess.TimeoutExpired:
        _handle_timeout(process, timeout_probe)
        stdout, stderr = process.communicate()
        return (
            ProcessExecutionResult(
                returncode=process.returncode,
                duration=time.monotonic() - started,
                timed_out=True,
            ),
            stdout,
            stderr,
        )
    except BaseException:
        terminate_process_group(process)
        raise


def run_to_stream(
    command: list[str],
    *,
    cwd: Path,
    stream: BinaryIO | TextIO,
    timeout_seconds: int | None,
    env: Mapping[str, str] | None = None,
    stderr_to_stdout: bool = True,
    timeout_probe: TimeoutProbe | None = None,
) -> ProcessExecutionResult:
    """Run a command with durable output redirected to the provided stream."""
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=stream,
        stderr=subprocess.STDOUT if stderr_to_stdout else None,
        start_new_session=True,
        env=None if env is None else dict(env),
    )
    try:
        process.wait(timeout=timeout_seconds)
        return ProcessExecutionResult(
            returncode=process.returncode,
            duration=time.monotonic() - started,
        )
    except subprocess.TimeoutExpired:
        _handle_timeout(process, timeout_probe)
        return ProcessExecutionResult(
            returncode=process.returncode,
            duration=time.monotonic() - started,
            timed_out=True,
        )
    except BaseException:
        terminate_process_group(process)
        raise


def run_inherit(
    command: list[str],
    *,
    cwd: Path,
    timeout_seconds: int | None,
    env: Mapping[str, str] | None = None,
    timeout_probe: TimeoutProbe | None = None,
) -> ProcessExecutionResult:
    """Run a command using inherited stdio with the same process-session policy."""
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=cwd,
        start_new_session=True,
        env=None if env is None else dict(env),
    )
    try:
        process.wait(timeout=timeout_seconds)
        return ProcessExecutionResult(
            returncode=process.returncode,
            duration=time.monotonic() - started,
        )
    except subprocess.TimeoutExpired:
        _handle_timeout(process, timeout_probe)
        return ProcessExecutionResult(
            returncode=process.returncode,
            duration=time.monotonic() - started,
            timed_out=True,
        )
    except BaseException:
        terminate_process_group(process)
        raise
