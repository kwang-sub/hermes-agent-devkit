#!/usr/bin/env python3
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'gradle_verification.py'


def make_launcher(base: Path, behavior: str) -> Path:
    launcher = base / 'hermes-java'
    launcher.write_text(textwrap.dedent(f'''\
        #!/usr/bin/env python3
        import os, sys, time
        args = sys.argv[1:]
        log = os.environ['GV_LOG']
        with open(log, 'a', encoding='utf-8') as f:
            f.write(' '.join(args) + '\\n')
        if '--version' in args:
            print('Gradle 8.5')
            raise SystemExit(0)
        if 'help' in args:
            if '--offline' in args:
                mode = os.environ.get('GV_OFFLINE', 'pass')
            else:
                mode = os.environ.get('GV_ONLINE', 'pass')
        else:
            mode = os.environ.get('GV_PRIMARY', '{behavior}')
        if mode == 'pass':
            print('BUILD SUCCESSFUL')
            raise SystemExit(0)
        if mode == 'fail':
            print('BUILD FAILED', file=sys.stderr)
            raise SystemExit(1)
        if mode == 'missing':
            print('Could not resolve dependency in offline mode', file=sys.stderr)
            raise SystemExit(1)
        if mode == 'sleep':
            time.sleep(5)
            raise SystemExit(0)
        raise SystemExit(3)
    '''), encoding='utf-8')
    launcher.chmod(0o755)
    return launcher


class GradleVerificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.repo = self.base / 'repo'
        self.repo.mkdir()
        (self.repo / 'gradlew').write_text('#!/bin/sh\n', encoding='utf-8')
        self.log = self.base / 'calls.log'
        self.guard_root = self.base / 'session-blocks'

    def tearDown(self):
        self.tmp.cleanup()

    def run_helper(self, primary='pass', online='pass', offline='pass', mode='TARGETED_TEST'):
        launcher = make_launcher(self.base, primary)
        env = os.environ.copy()
        env.update({
            'GV_LOG': str(self.log),
            'GV_PRIMARY': primary,
            'GV_ONLINE': online,
            'GV_OFFLINE': offline,
            'HERMES_KANBAN_TASK': 't_test',
            'HERMES_SESSION_ID': 'session_test',
            'HERMES_GRADLE_SESSION_GUARD_ROOT': str(self.guard_root),
        })
        cmd = [sys.executable, str(SCRIPT), '--workspace', str(self.repo), '--mode', mode,
               '--launcher', str(launcher), '--capability-timeout', '1', '--verification-timeout', '1', '--diagnostic-timeout', '1']
        if mode == 'TARGETED_TEST':
            cmd += ['--test', 'com.example.TargetTest']
        return subprocess.run(cmd, text=True, capture_output=True, env=env)

    def calls(self):
        return self.log.read_text(encoding='utf-8').splitlines() if self.log.exists() else []

    def guard(self):
        return self.guard_root / 't_test--session_test.blocked'

    def test_pass_runs_capability_and_primary_once(self):
        proc = self.run_helper(primary='pass')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('GRADLE_STATUS=PASS', proc.stdout)
        self.assertFalse(self.guard().exists())
        calls = self.calls()
        self.assertEqual(len(calls), 2)
        self.assertIn('--version', calls[0])
        self.assertIn('test --tests com.example.TargetTest', calls[1])
        self.assertIn('--no-daemon --console=plain', calls[1])

    def test_build_failure_does_not_run_diagnostics(self):
        proc = self.run_helper(primary='fail')
        self.assertEqual(proc.returncode, 1)
        self.assertIn('GRADLE_BLOCKER=BUILD_FAILURE', proc.stdout)
        self.assertFalse(self.guard().exists())
        self.assertEqual(len(self.calls()), 2)

    def test_timeout_runs_diagnostics_without_primary_retry_and_writes_guard(self):
        proc = self.run_helper(primary='sleep', online='pass', offline='pass')
        self.assertEqual(proc.returncode, 2)
        self.assertIn('GRADLE_BLOCKER=BUILD_TASK_TIMEOUT', proc.stdout)
        self.assertIn('PRIMARY_RETRY_ALLOWED=false', proc.stdout)
        self.assertIn('SESSION_DIRECT_GRADLE_ALLOWED=false', proc.stdout)
        self.assertTrue(self.guard().is_file())
        self.assertIn('GRADLE_BLOCKER=BUILD_TASK_TIMEOUT', self.guard().read_text(encoding='utf-8'))
        calls = self.calls()
        self.assertEqual(len(calls), 4)
        primary_calls = [c for c in calls if 'test --tests' in c]
        self.assertEqual(len(primary_calls), 1)
        self.assertTrue(any('help --info' in c for c in calls))
        self.assertTrue(any('help --offline --info' in c for c in calls))

    def test_online_timeout_offline_missing_is_dependency_resolution(self):
        proc = self.run_helper(primary='sleep', online='sleep', offline='missing')
        self.assertEqual(proc.returncode, 2)
        self.assertIn('GRADLE_BLOCKER=DEPENDENCY_RESOLUTION', proc.stdout)
        self.assertTrue(self.guard().is_file())

    def test_both_diagnostics_timeout_is_project_configuration(self):
        proc = self.run_helper(primary='sleep', online='sleep', offline='sleep')
        self.assertEqual(proc.returncode, 2)
        self.assertIn('GRADLE_BLOCKER=PROJECT_CONFIGURATION', proc.stdout)
        self.assertTrue(self.guard().is_file())

    def test_compile_mode_uses_compile_java(self):
        proc = self.run_helper(primary='pass', mode='COMPILE')
        self.assertEqual(proc.returncode, 0)
        self.assertTrue(any('compileJava' in c for c in self.calls()))

    def test_targeted_test_requires_selector(self):
        launcher = make_launcher(self.base, 'pass')
        env = os.environ.copy(); env['GV_LOG'] = str(self.log)
        proc = subprocess.run([sys.executable, str(SCRIPT), '--workspace', str(self.repo), '--mode', 'TARGETED_TEST', '--launcher', str(launcher)], text=True, capture_output=True, env=env)
        self.assertEqual(proc.returncode, 2)
        self.assertIn('requires at least one --test', proc.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
