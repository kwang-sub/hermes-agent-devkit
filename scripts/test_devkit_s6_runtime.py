#!/usr/bin/env python3
"""s6 runtime regressions using disposable paths, without Docker or user data."""
from pathlib import Path
from contextlib import redirect_stderr
import io
import os
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import devkit_s6_runtime as m


class ScandirResolutionTest(unittest.TestCase):
    def modules(self, scandir):
        package = types.ModuleType('hermes_cli')
        package.__path__ = []
        backend = types.ModuleType('hermes_cli.service_manager')
        backend.S6ServiceManager = lambda: types.SimpleNamespace(scandir=scandir)
        return {'hermes_cli': package, 'hermes_cli.service_manager': backend}

    def test_installed_backend_selects_current_and_legacy_scandir(self):
        for path in (Path('/run/hermes-service'), Path('/run/service')):
            with self.subTest(path=path), patch.dict(sys.modules, self.modules(path)):
                self.assertEqual(m.gateway_scandir(), path)

    def test_missing_backend_does_not_fall_back_to_root_scandir(self):
        with patch.dict(sys.modules, {'hermes_cli.service_manager': None}):
            with self.assertRaises(RuntimeError):
                m.gateway_scandir()

    def test_relative_backend_path_is_rejected(self):
        with patch.dict(sys.modules, self.modules(Path('relative/service'))):
            with self.assertRaises((ValueError, RuntimeError)):
                m.gateway_scandir()


class RuntimeProbeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.static = self.root / 'service'
        self.dynamic = self.root / 'hermes-service'
        for root in (self.static, self.dynamic):
            (root / '.s6-svscan').mkdir(parents=True)
            for name in ('control', 'lock'):
                (root / '.s6-svscan' / name).touch()
            self.make_service(root / 'gateway-default')
        self.make_service(self.static / 'devkit-notifier')
        self.real_access = os.access
        self.enterContext(patch.object(m, 'STATIC_SCANDIR', self.static))
        self.resolver = self.enterContext(patch.object(m, 'gateway_scandir', return_value=self.dynamic))
        self.running = self.enterContext(patch.object(m, 'service_running', return_value=True))
        self.enterContext(patch.object(m.os, 'access', side_effect=self.access))

    def make_service(self, slot):
        slot.mkdir()
        script = slot / 'run'
        script.write_text('#!/bin/sh\nexit 0\n')
        script.chmod(0o755)

    def access(self, path, mode):
        # Model the intentional root-owned static tree in a hermes-owned fixture.
        if Path(path) == self.static and mode & os.W_OK:
            return False
        return self.real_access(path, mode)

    def snapshot(self):
        return {str(path.relative_to(self.root)): path.read_bytes()
                for path in self.root.rglob('*') if path.is_file()}

    def test_split_layout_accepts_protected_static_tree(self):
        before = self.snapshot()
        m.check_gateway()
        self.running.assert_called_once_with(self.dynamic / 'gateway-default')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(list(self.dynamic.glob('.devkit-runtime-write-check*')), [])

    def test_legacy_layout_checks_its_writable_shared_scandir(self):
        self.resolver.return_value = self.static
        with patch.object(m.os, 'access', side_effect=self.real_access):
            m.check_gateway()
        self.running.assert_called_once_with(self.static / 'gateway-default')

    def test_existing_fixed_probe_marker_is_preserved(self):
        marker = self.dynamic / '.devkit-runtime-write-check'
        marker.write_bytes(b'existing runtime evidence')
        m.check_gateway()
        self.assertEqual(marker.read_bytes(), b'existing runtime evidence')
        self.assertEqual(list(self.dynamic.glob('.devkit-runtime-write-check*')), [marker])

    def test_dynamic_scandir_write_failure_is_reported(self):
        with patch.object(m.tempfile, 'TemporaryDirectory', side_effect=PermissionError('fixture denied')):
            with self.assertRaises((OSError, RuntimeError)):
                m.check_gateway()

    def test_split_layout_rejects_writable_root_scandir(self):
        with patch.object(m.os, 'access', side_effect=self.real_access):
            with self.assertRaises(RuntimeError):
                m.check_gateway()

    def test_unwritable_svscan_control_and_lock_are_rejected(self):
        for name in ('control', 'lock'):
            denied = self.dynamic / '.s6-svscan' / name
            def access(path, mode):
                return False if Path(path) == denied and mode & os.W_OK else self.access(path, mode)
            with self.subTest(name=name), patch.object(m.os, 'access', side_effect=access):
                with self.assertRaises(RuntimeError):
                    m.check_gateway()

    def test_missing_svscan_control_and_lock_are_rejected(self):
        for name in ('control', 'lock'):
            missing = self.dynamic / '.s6-svscan' / name
            with self.subTest(name=name):
                missing.unlink()
                try:
                    with self.assertRaises(RuntimeError):
                        m.check_gateway()
                finally:
                    missing.touch()

    def test_stopped_gateway_is_rejected(self):
        self.running.return_value = False
        with self.assertRaises(RuntimeError):
            m.check_gateway()
        self.running.assert_called_once_with(self.dynamic / 'gateway-default')

    def test_nonexecutable_gateway_run_is_rejected(self):
        (self.dynamic / 'gateway-default' / 'run').chmod(0o644)
        with self.assertRaises(RuntimeError):
            m.check_gateway()

    def test_notifier_stays_in_static_tree(self):
        self.resolver.side_effect = AssertionError('Notifier must not use the Gateway scandir')
        before = self.snapshot()
        m.check_notifier()
        self.running.assert_called_once_with(self.static / 'devkit-notifier')
        self.assertEqual(self.snapshot(), before)

    def test_stopped_notifier_is_rejected(self):
        self.running.return_value = False
        with self.assertRaises(RuntimeError):
            m.check_notifier()
        self.running.assert_called_once_with(self.static / 'devkit-notifier')

    def test_nonexecutable_notifier_run_is_rejected(self):
        (self.static / 'devkit-notifier' / 'run').chmod(0o644)
        with self.assertRaises(RuntimeError):
            m.check_notifier()


class ServiceStatusTest(unittest.TestCase):
    def test_only_successful_exact_true_means_running(self):
        slot = Path('/fixture/gateway-default')
        for output, expected in (('true\n', True), ('false\n', False), ('', False), ('true\nextra', False)):
            result = subprocess.CompletedProcess([], 0, output, '')
            with self.subTest(output=output), patch.object(m.subprocess, 'run', return_value=result):
                self.assertEqual(m.service_running(slot), expected)

    def test_failed_status_command_cannot_report_running(self):
        result = subprocess.CompletedProcess([], 1, 'true\n', 'fixture failure')
        with patch.object(m.subprocess, 'run', return_value=result):
            try:
                running = m.service_running(Path('/fixture/gateway-default'))
            except RuntimeError:
                running = False
            self.assertFalse(running)


class CommandLineTest(unittest.TestCase):
    def test_each_service_runs_its_own_check(self):
        for service in ('gateway', 'notifier'):
            with self.subTest(service=service), patch.object(sys, 'argv', ['probe', service]), \
                    patch.object(m, 'check_gateway') as gateway, patch.object(m, 'check_notifier') as notifier:
                self.assertEqual(m.main(), 0)
                self.assertEqual(gateway.call_count, int(service == 'gateway'))
                self.assertEqual(notifier.call_count, int(service == 'notifier'))

    def test_probe_errors_return_failure_to_the_updater(self):
        failures = (PermissionError('fixture denied'), RuntimeError('fixture stopped'),
                    subprocess.TimeoutExpired('s6-svstat', 5))
        for failure in failures:
            error = io.StringIO()
            with self.subTest(failure=type(failure).__name__), \
                    patch.object(sys, 'argv', ['probe', 'gateway']), \
                    patch.object(m, 'check_gateway', side_effect=failure), redirect_stderr(error):
                self.assertEqual(m.main(), 1)
                self.assertIn('[FAIL] s6 gateway runtime contract:', error.getvalue())


if __name__ == '__main__':
    unittest.main()
