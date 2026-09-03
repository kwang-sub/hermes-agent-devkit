#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field

DEFAULT_CAPABILITY_TIMEOUT = int(os.getenv('HERMES_GRADLE_CAPABILITY_TIMEOUT_SECONDS', '180'))
DEFAULT_VERIFY_TIMEOUT = int(os.getenv('HERMES_GRADLE_VERIFY_TIMEOUT_SECONDS', '240'))
DEFAULT_DIAGNOSTIC_TIMEOUT = int(os.getenv('HERMES_GRADLE_DIAGNOSTIC_TIMEOUT_SECONDS', '60'))
DEFAULT_DRY_RUN_TIMEOUT = int(os.getenv('HERMES_GRADLE_DRY_RUN_TIMEOUT_SECONDS', '30'))
TAIL_LINES = 30
MAX_PROCESS_SNAPSHOTS = 8


@dataclass
class RunResult:
    args: list[str]
    returncode: int | None
    stdout: str
    stderr: str
    duration: float
    timed_out: bool = False
    timeout_processes: list[str] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='Run bounded Gradle verification with deterministic timeout diagnostics.')
    p.add_argument('--workspace', required=True)
    p.add_argument('--mode', required=True, choices=['COMPILE', 'TARGETED_TEST'])
    p.add_argument('--test', action='append', default=[], help='Gradle --tests selector; repeatable for TARGETED_TEST')
    p.add_argument('--task', default=None, help='Override Gradle task (default: compileJava or test)')
    p.add_argument('--capability-timeout', type=int, default=DEFAULT_CAPABILITY_TIMEOUT)
    p.add_argument('--verification-timeout', type=int, default=DEFAULT_VERIFY_TIMEOUT)
    p.add_argument('--diagnostic-timeout', type=int, default=DEFAULT_DIAGNOSTIC_TIMEOUT)
    p.add_argument('--dry-run-timeout', type=int, default=DEFAULT_DRY_RUN_TIMEOUT)
    p.add_argument('--launcher', default=os.getenv('HERMES_JAVA_LAUNCHER', 'hermes-java'))
    return p.parse_args()


def safe_id(value: str) -> str:
    return ''.join(ch if ch.isalnum() or ch in '._-' else '_' for ch in value)


def session_guard_path() -> Path | None:
    task_id = (os.getenv('HERMES_KANBAN_TASK') or '').strip()
    session_id = (os.getenv('HERMES_SESSION_ID') or '').strip()
    if not task_id or not session_id:
        return None
    root = Path(os.getenv('HERMES_GRADLE_SESSION_GUARD_ROOT', '/opt/data/gradle/session-blocks'))
    return root / f'{safe_id(task_id)}--{safe_id(session_id)}.blocked'


def clear_session_guard() -> None:
    path = session_guard_path()
    if path is None:
        return
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def write_session_guard(blocker: str) -> None:
    path = session_guard_path()
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'GRADLE_STATUS=BLOCKED\nGRADLE_BLOCKER={blocker}\n', encoding='utf-8')


def observation_log_path(workspace: Path) -> Path:
    root = Path(os.getenv('HERMES_GRADLE_DIAGNOSTIC_LOG_ROOT', '/opt/data/gradle/diagnostics'))
    task_id = safe_id((os.getenv('HERMES_KANBAN_TASK') or 'no-task').strip() or 'no-task')
    session_id = safe_id((os.getenv('HERMES_SESSION_ID') or 'no-session').strip() or 'no-session')
    workspace_name = safe_id(workspace.name or 'workspace')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    return root / workspace_name / f'{stamp}--{task_id}--{session_id}.log'


def write_observation_log(
    *,
    workspace: Path,
    mode: str,
    primary: RunResult,
    last_task: str,
    filesystem: str,
    online: RunResult,
    offline: RunResult,
    dry_run: RunResult | None,
    blocker: str,
    timeout_detail: str,
    candidates: str,
) -> Path | None:
    path = observation_log_path(workspace)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f'OBSERVED_AT_UTC={datetime.now(timezone.utc).isoformat()}',
            f'WORKSPACE={workspace}',
            f'MODE={mode}',
            f'HERMES_KANBAN_TASK={(os.getenv("HERMES_KANBAN_TASK") or "UNKNOWN")}',
            f'HERMES_SESSION_ID={(os.getenv("HERMES_SESSION_ID") or "UNKNOWN")}',
            'HOST_ACTIVITY=UNKNOWN',
            'HOST_ACTIVITY_POLICY=OBSERVE_ONLY',
            f'WORKSPACE_FILESYSTEM={filesystem}',
            f'PRIMARY_RESULT={"TIMEOUT" if primary.timed_out else primary.returncode}',
            f'PRIMARY_DURATION_SECONDS={primary.duration:.1f}',
            f'PRIMARY_COMMAND={q(primary.args)}',
            f'PRIMARY_LAST_TASK={last_task}',
            f'GRADLE_BLOCKER={blocker}',
            f'GRADLE_TIMEOUT_DETAIL={timeout_detail}',
            f'GRADLE_ROOT_CAUSE_CANDIDATES={candidates}',
            f'DIAGNOSTIC_ONLINE_RESULT={"TIMEOUT" if online.timed_out else online.returncode}',
            f'DIAGNOSTIC_OFFLINE_RESULT={"TIMEOUT" if offline.timed_out else offline.returncode}',
            f'DIAGNOSTIC_DRY_RUN_RESULT={"SKIPPED" if dry_run is None else ("TIMEOUT" if dry_run.timed_out else dry_run.returncode)}',
        ]
        detail = compact_tail(primary)
        if detail:
            lines.append(f'PRIMARY_DETAIL={detail}')
        for index, snapshot in enumerate(primary.timeout_processes, start=1):
            lines.append(f'PRIMARY_TIMEOUT_PROCESS_{index}={snapshot}')
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        return path
    except OSError as exc:
        print(f'GRADLE_OBSERVATION_LOG_WARNING={type(exc).__name__}', file=sys.stderr)
        return None


def _read_proc_value(pid: int, file_name: str, keys: tuple[str, ...]) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        text = (Path('/proc') / str(pid) / file_name).read_text(encoding='utf-8', errors='replace')
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        return values
    for raw_line in text.splitlines():
        if ':' not in raw_line:
            continue
        key, value = raw_line.split(':', 1)
        if key in keys:
            values[key] = value.strip()
    return values


def capture_process_group(leader_pid: int) -> list[str]:
    try:
        pgid = os.getpgid(leader_pid)
    except (ProcessLookupError, PermissionError):
        return []
    try:
        ps = subprocess.run(
            ['ps', '-eo', 'pid=,ppid=,pgid=,stat=,etime=,pcpu=,pmem=,wchan=,comm='],
            text=True,
            capture_output=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    snapshots: list[str] = []
    for raw_line in ps.stdout.splitlines():
        parts = raw_line.split(None, 8)
        if len(parts) < 9:
            continue
        pid_s, ppid_s, pgid_s, stat, etime, pcpu, pmem, wchan, comm = parts
        try:
            if int(pgid_s) != pgid:
                continue
            pid = int(pid_s)
        except ValueError:
            continue
        status = _read_proc_value(pid, 'status', ('Threads', 'voluntary_ctxt_switches', 'nonvoluntary_ctxt_switches'))
        io = _read_proc_value(pid, 'io', ('read_bytes', 'write_bytes'))
        snapshots.append(
            ' '.join(
                [
                    f'pid={pid_s}',
                    f'ppid={ppid_s}',
                    f'stat={stat}',
                    f'etime={etime}',
                    f'cpu={pcpu}',
                    f'mem={pmem}',
                    f'wchan={wchan}',
                    f'comm={comm}',
                    f"threads={status.get('Threads', '?')}",
                    f"read_bytes={io.get('read_bytes', '?')}",
                    f"write_bytes={io.get('write_bytes', '?')}",
                ]
            )
        )
        if len(snapshots) >= MAX_PROCESS_SNAPSHOTS:
            break
    return snapshots


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
    env = os.environ.copy()
    env['HERMES_GRADLE_BOUNDED_HELPER'] = '1'
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        env=env,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return RunResult(cmd, proc.returncode, stdout, stderr, time.monotonic() - started)
    except subprocess.TimeoutExpired:
        snapshots = capture_process_group(proc.pid)
        _terminate_group(proc)
        stdout, stderr = proc.communicate()
        return RunResult(
            cmd,
            None,
            stdout,
            stderr,
            time.monotonic() - started,
            timed_out=True,
            timeout_processes=snapshots,
        )


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


def last_gradle_task(result: RunResult) -> str:
    text = '\n'.join(part for part in (result.stdout, result.stderr) if part)
    matches = re.findall(r'(?m)^> Task\s+(:[^\s]+)', text)
    if matches:
        return matches[-1]
    info_matches = re.findall(r"(?m)^Task '(:[^']+)'", text)
    return info_matches[-1] if info_matches else 'UNKNOWN'


def workspace_filesystem(workspace: Path) -> str:
    try:
        result = subprocess.run(
            ['findmnt', '-T', str(workspace), '-n', '-o', 'FSTYPE,SOURCE,TARGET'],
            text=True,
            capture_output=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return 'UNKNOWN'
    value = ' '.join(result.stdout.split())
    return value or 'UNKNOWN'


def classify_timeout(online: RunResult, offline: RunResult) -> str:
    if online.timed_out and not offline.timed_out and offline.returncode != 0:
        return 'DEPENDENCY_RESOLUTION'
    if online.timed_out and offline.timed_out:
        return 'PROJECT_CONFIGURATION'
    if online.returncode == 0:
        return 'BUILD_TASK_TIMEOUT'
    return 'PROJECT_CONFIGURATION'


def classify_timeout_detail(blocker: str, last_task: str, dry_run: RunResult | None) -> tuple[str, str]:
    if blocker == 'DEPENDENCY_RESOLUTION':
        return 'DEPENDENCY_RESOLUTION', 'dependency_or_repository_access'
    if blocker == 'PROJECT_CONFIGURATION':
        return 'PROJECT_CONFIGURATION', 'gradle_configuration_or_plugin_initialization'
    if dry_run is not None:
        if dry_run.timed_out:
            return 'TASK_GRAPH_TIMEOUT', 'task_graph_or_compile_classpath_resolution'
        if dry_run.returncode != 0:
            detail = compact_tail(dry_run).lower()
            if 'could not resolve' in detail or 'could not find' in detail or 'offline mode' in detail:
                return 'TASK_GRAPH_DEPENDENCY_FAILURE', 'compile_classpath_or_dependency_resolution'
            return 'TASK_GRAPH_FAILURE', 'task_graph_or_configuration_failure'
    task_name = last_task.rsplit(':', 1)[-1] if last_task != 'UNKNOWN' else ''
    if task_name == 'compileJava':
        return 'JAVA_COMPILE_EXECUTION', 'javac_or_annotation_processor_or_workspace_io'
    if task_name in {'compileKotlin', 'kaptKotlin', 'kaptGenerateStubsKotlin'}:
        return 'KOTLIN_COMPILE_EXECUTION', 'kotlin_compiler_or_kapt_or_workspace_io'
    if task_name.startswith('processResources'):
        return 'RESOURCE_PROCESSING', 'resource_copy_or_workspace_io'
    if task_name.startswith('test'):
        return 'TEST_EXECUTION', 'test_runtime_or_test_worker'
    return 'TASK_EXECUTION', 'gradle_task_execution_or_workspace_io'


def emit_result(prefix: str, result: RunResult) -> None:
    state = 'TIMEOUT' if result.timed_out else ('PASS' if result.returncode == 0 else 'FAIL')
    print(f'{prefix}_RESULT={state}')
    print(f'{prefix}_DURATION_SECONDS={result.duration:.1f}')
    print(f'{prefix}_COMMAND={q(result.args)}')
    detail = compact_tail(result)
    if detail:
        print(f'{prefix}_DETAIL={detail}')
    if result.timeout_processes:
        print(f'{prefix}_TIMEOUT_PROCESS_COUNT={len(result.timeout_processes)}')
        for index, snapshot in enumerate(result.timeout_processes, start=1):
            print(f'{prefix}_TIMEOUT_PROCESS_{index}={snapshot}')


def blocked(blocker: str) -> int:
    write_session_guard(blocker)
    print('GRADLE_STATUS=BLOCKED')
    print(f'GRADLE_BLOCKER={blocker}')
    print('PRIMARY_RETRY_ALLOWED=false')
    print('SESSION_DIRECT_GRADLE_ALLOWED=false')
    return 2


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

    clear_session_guard()
    capability = run_bounded(
        gradle_cmd(args.launcher, '--version'), workspace, args.capability_timeout
    )
    emit_result('CAPABILITY', capability)
    if capability.timed_out or capability.returncode != 0:
        return blocked('CAPABILITY')

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
        clear_session_guard()
        if primary.returncode == 0:
            print('GRADLE_STATUS=PASS')
            print('GRADLE_BLOCKER=NONE')
            return 0
        print('GRADLE_STATUS=FAIL')
        print('GRADLE_BLOCKER=BUILD_FAILURE')
        return 1

    timeout_task = last_gradle_task(primary)
    filesystem = workspace_filesystem(workspace)
    print(f'PRIMARY_LAST_TASK={timeout_task}')
    print(f'WORKSPACE_FILESYSTEM={filesystem}')

    online = run_bounded(
        gradle_cmd(args.launcher, 'help', '--info'), workspace, args.diagnostic_timeout
    )
    emit_result('DIAGNOSTIC_ONLINE', online)

    offline = run_bounded(
        gradle_cmd(args.launcher, 'help', '--offline', '--info'), workspace, args.diagnostic_timeout
    )
    emit_result('DIAGNOSTIC_OFFLINE', offline)

    blocker = classify_timeout(online, offline)
    dry_run: RunResult | None = None
    if blocker == 'BUILD_TASK_TIMEOUT':
        dry_run_task = timeout_task if timeout_task != 'UNKNOWN' else task
        dry_run = run_bounded(
            gradle_cmd(args.launcher, dry_run_task, '--dry-run', '--offline', '--info'),
            workspace,
            args.dry_run_timeout,
        )
        emit_result('DIAGNOSTIC_DRY_RUN', dry_run)
    else:
        print('DIAGNOSTIC_DRY_RUN_RESULT=SKIPPED')

    timeout_detail, candidates = classify_timeout_detail(blocker, timeout_task, dry_run)
    observation_log = write_observation_log(
        workspace=workspace,
        mode=args.mode,
        primary=primary,
        last_task=timeout_task,
        filesystem=filesystem,
        online=online,
        offline=offline,
        dry_run=dry_run,
        blocker=blocker,
        timeout_detail=timeout_detail,
        candidates=candidates,
    )
    write_session_guard(blocker)
    print('GRADLE_STATUS=BLOCKED')
    print(f'GRADLE_BLOCKER={blocker}')
    print(f'GRADLE_TIMEOUT_DETAIL={timeout_detail}')
    print(f'GRADLE_ROOT_CAUSE_CANDIDATES={candidates}')
    print(f'GRADLE_OBSERVATION_LOG={observation_log if observation_log is not None else "UNAVAILABLE"}')
    print('HOST_ACTIVITY=UNKNOWN')
    print('HOST_ACTIVITY_POLICY=OBSERVE_ONLY')
    print('PRIMARY_RETRY_ALLOWED=false')
    print('SESSION_DIRECT_GRADLE_ALLOWED=false')
    print('DIAGNOSTIC_POLICY=process-snapshot;single-online-help;single-offline-help;bounded-offline-dry-run;persist-observation-log;no-primary-retry')
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
