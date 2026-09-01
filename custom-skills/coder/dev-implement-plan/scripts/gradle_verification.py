#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import time
from dataclasses import dataclass

DEFAULT_CAPABILITY_TIMEOUT = int(os.getenv('HERMES_GRADLE_CAPABILITY_TIMEOUT_SECONDS', '180'))
DEFAULT_VERIFY_TIMEOUT = int(os.getenv('HERMES_GRADLE_VERIFY_TIMEOUT_SECONDS', '240'))
DEFAULT_DIAGNOSTIC_TIMEOUT = int(os.getenv('HERMES_GRADLE_DIAGNOSTIC_TIMEOUT_SECONDS', '60'))
TAIL_LINES = 30


@dataclass
class RunResult:
    args: list[str]
    returncode: int | None
    stdout: str
    stderr: str
    duration: float
    timed_out: bool = False


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='Run bounded Gradle verification with deterministic timeout diagnostics.')
    p.add_argument('--workspace', required=True)
    p.add_argument('--mode', required=True, choices=['COMPILE', 'TARGETED_TEST'])
    p.add_argument('--test', action='append', default=[], help='Gradle --tests selector; repeatable for TARGETED_TEST')
    p.add_argument('--task', default=None, help='Override Gradle task (default: compileJava or test)')
    p.add_argument('--capability-timeout', type=int, default=DEFAULT_CAPABILITY_TIMEOUT)
    p.add_argument('--verification-timeout', type=int, default=DEFAULT_VERIFY_TIMEOUT)
    p.add_argument('--diagnostic-timeout', type=int, default=DEFAULT_DIAGNOSTIC_TIMEOUT)
    p.add_argument('--launcher', default=os.getenv('HERMES_JAVA_LAUNCHER', 'hermes-java'))
    return p.parse_args()


def _terminate_group(proc: subprocess.Popen[str]) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=3)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass


def run_bounded(cmd: list[str], cwd: Path, timeout: int) -> RunResult:
    started = time.monotonic()
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return RunResult(cmd, proc.returncode, stdout, stderr, time.monotonic() - started)
    except subprocess.TimeoutExpired:
        _terminate_group(proc)
        stdout, stderr = proc.communicate()
        return RunResult(cmd, None, stdout, stderr, time.monotonic() - started, timed_out=True)


def compact_tail(result: RunResult) -> str:
    text = '\n'.join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
    if not text:
        return ''
    lines = text.splitlines()[-TAIL_LINES:]
    return ' | '.join(line.strip() for line in lines if line.strip())


def q(cmd: list[str]) -> str:
    return shlex.join(cmd)


def gradle_cmd(launcher: str, *args: str) -> list[str]:
    return [launcher, './gradlew', *args, '--no-daemon', '--console=plain']


def classify_timeout(online: RunResult, offline: RunResult) -> str:
    if online.timed_out and not offline.timed_out and offline.returncode != 0:
        return 'DEPENDENCY_RESOLUTION'
    if online.timed_out and offline.timed_out:
        return 'PROJECT_CONFIGURATION'
    if online.returncode == 0:
        return 'BUILD_TASK_TIMEOUT'
    return 'PROJECT_CONFIGURATION'


def emit_result(prefix: str, result: RunResult) -> None:
    state = 'TIMEOUT' if result.timed_out else ('PASS' if result.returncode == 0 else 'FAIL')
    print(f'{prefix}_RESULT={state}')
    print(f'{prefix}_DURATION_SECONDS={result.duration:.1f}')
    print(f'{prefix}_COMMAND={q(result.args)}')
    detail = compact_tail(result)
    if detail:
        print(f'{prefix}_DETAIL={detail}')


def main() -> int:
    args = parse_args()
    workspace = Path(args.workspace).resolve()
    if not workspace.is_dir():
        print(f'ERROR: workspace does not exist: {workspace}', file=sys.stderr)
        return 2
    if not (workspace / 'gradlew').is_file():
        print(f'ERROR: gradlew is missing: {workspace / "gradlew"}', file=sys.stderr)
        return 2
    if args.mode == 'TARGETED_TEST' and not args.test:
        print('ERROR: TARGETED_TEST requires at least one --test selector', file=sys.stderr)
        return 2

    capability = run_bounded(
        gradle_cmd(args.launcher, '--version'), workspace, args.capability_timeout
    )
    emit_result('CAPABILITY', capability)
    if capability.timed_out or capability.returncode != 0:
        print('GRADLE_STATUS=BLOCKED')
        print('GRADLE_BLOCKER=CAPABILITY')
        return 2

    task = args.task or ('compileJava' if args.mode == 'COMPILE' else 'test')
    primary_args = [task]
    if args.mode == 'TARGETED_TEST':
        for selector in args.test:
            primary_args.extend(['--tests', selector])
    primary = run_bounded(
        gradle_cmd(args.launcher, *primary_args), workspace, args.verification_timeout
    )
    emit_result('PRIMARY', primary)

    if not primary.timed_out:
        if primary.returncode == 0:
            print('GRADLE_STATUS=PASS')
            print('GRADLE_BLOCKER=NONE')
            return 0
        print('GRADLE_STATUS=FAIL')
        print('GRADLE_BLOCKER=BUILD_FAILURE')
        return 1

    online = run_bounded(
        gradle_cmd(args.launcher, 'help', '--info'), workspace, args.diagnostic_timeout
    )
    emit_result('DIAGNOSTIC_ONLINE', online)

    offline = run_bounded(
        gradle_cmd(args.launcher, 'help', '--offline', '--info'), workspace, args.diagnostic_timeout
    )
    emit_result('DIAGNOSTIC_OFFLINE', offline)

    blocker = classify_timeout(online, offline)
    print('GRADLE_STATUS=BLOCKED')
    print(f'GRADLE_BLOCKER={blocker}')
    print('PRIMARY_RETRY_ALLOWED=false')
    print('DIAGNOSTIC_POLICY=single-online-help;single-offline-help;no-primary-retry')
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
