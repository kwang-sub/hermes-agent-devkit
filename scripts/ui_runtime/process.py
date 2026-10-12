"""Reuse canonical process termination and verify owned live descendants."""
from __future__ import annotations
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import time


def _canonical_terminator():
    installed = Path(__file__).resolve().parent.parent / 'devkit_process_execution.py'
    source = Path(__file__).resolve().parents[2] / 'custom-skills/_lib/process_execution.py'
    candidate = installed if installed.is_file() else source
    spec = importlib.util.spec_from_file_location('devkit_shared_process_execution', candidate)
    if spec is None or spec.loader is None:
        raise RuntimeError('canonical process execution library is unavailable')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.terminate_process_group


def live_group(pgid: int) -> bool:
    """On Linux exclude zombies; they cannot write files or retain server sockets."""
    proc = Path('/proc')
    if proc.is_dir():
        for path in proc.glob('[0-9]*/stat'):
            try:
                tail = path.read_text().rsplit(')', 1)[1].split()
                if int(tail[2]) == pgid and tail[0] not in ('Z', 'X'):
                    return True
            except (OSError, ValueError, IndexError):
                continue
        return False
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False


def stop_owned(process: subprocess.Popen | None) -> list[str]:
    if process is None:
        return []
    try:
        if os.name != 'posix':
            # DevKit is Linux. Do not claim that terminate() manages Windows trees.
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=3)
            return ['PROCESS_TREE_VERIFICATION_UNSUPPORTED']
        _canonical_terminator()(process, terminate_timeout=1.0, kill_timeout=2.0)
        deadline = time.monotonic() + 2.0
        while live_group(process.pid) and time.monotonic() < deadline:
            time.sleep(.02)
        return ['OWNED_PROCESS_GROUP_STILL_RUNNING'] if live_group(process.pid) else []
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        return ['PROCESS_CLEANUP_' + type(exc).__name__]
