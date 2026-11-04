#!/usr/bin/env python3
"""Native/legacy preflight and scoped cleanup contracts; no live browser claim."""
from contextlib import contextmanager
import asyncio
import os
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from ui_runtime.hermes_compat import HermesRuntime
from ui_runtime.suite import EnvironmentBlocked


def module(name, **values):
    result = ModuleType(name)
    result.__dict__.update(values)
    return result


class RuntimeFixture:
    def __init__(self, native):
        self.native = native
        self.config = {}
        self.provider = None
        self.live_cdp = ''
        self.policy = 'must_respond'
        self.lower_flag = '1'
        self.binary = sys.executable  # Existing file only; it is never launched.
        self.desktop_env = {}
        self.placement = 'gateway'
        self.auto_start = False
        self.sessions = {}
        self.cleanup_calls = []
        self.execute = Mock(return_value={'success': True})
        self.registry = Mock()
        self.registry.get.return_value = None
        self.cli = module('tools.browser_use_cli', browser_exec=self.execute,
                          _find_cli=Mock(return_value=[sys.executable, '-m', 'browser_harness.run']),
                          _backend_cache_key=lambda task, name: f'bu-named-{name}@home',
                          _sidecar_daemon_name=lambda name: '_local_' + name)
        self.launcher = module('tools.browser_launcher',
                               _resolve_executable=Mock(side_effect=lambda: self.binary),
                               chromium_ready=Mock(side_effect=AssertionError('automatic install path used')))
        self.install = module('tools.browser_tool_install',
                              _find_agent_browser=Mock(side_effect=lambda validate: self.binary))
        self.lifecycle = module('tools.browser_session_lifecycle' if native else 'tools.browser_tool_lifecycle',
                                cleanup_browser=Mock(side_effect=self.cleanup),
                                cleanup_all_browsers=Mock(side_effect=AssertionError('global cleanup used')))
        self.modules = {
            'tools': module('tools', __path__=[]),
            'tools.browser_use_cli': self.cli,
            'tools.browser_dialog_tool': module('tools.browser_dialog_tool', browser_dialog=Mock()),
            'tools.browser_supervisor': module('tools.browser_supervisor', SUPERVISOR_REGISTRY=self.registry),
            'tools.browser_launcher': self.launcher,
            'tools.browser_tool_install': None if native else self.install,
            'tools.browser_tool': module('tools.browser_tool', _active_sessions=self.sessions),
            'tools.bot_desktop': module('tools.bot_desktop', __path__=[]),
            'tools.bot_desktop.runtime': module('tools.bot_desktop.runtime',
                published_env=lambda: self.desktop_env, _should_auto_start=lambda env: self.auto_start),
            'tools.bot_desktop.placement': module('tools.bot_desktop.placement', GATEWAY='gateway',
                resolve=lambda: SimpleNamespace(where=self.placement)),
            'hermes_cli': module('hermes_cli', __path__=[]),
            'hermes_cli.config': module('hermes_cli.config', read_raw_config=lambda: {'browser': self.config}),
            'websockets': module('websockets', connect=Mock(side_effect=AssertionError('unexpected browser connection'))),
        }
        if native:
            self.modules.update({
                'tools.browser_session': module('tools.browser_session', _active_sessions=self.sessions,
                                               owner_task_id=self.owner),
                'tools.browser_session_cloud': module('tools.browser_session_cloud',
                    browser_section=lambda: self.config, get_cloud_provider=lambda: self.provider,
                    is_headed_mode=lambda: bool(self.config.get('headed'))),
                'tools.browser_session_cdp': module('tools.browser_session_cdp',
                    get_cdp_override_raw=lambda: self.live_cdp,
                    get_dialog_policy_config=lambda: (self.policy, 30.0)),
                'tools.browser_session_lifecycle': self.lifecycle,
                'tools.browser_tool_session': None,
            })
        else:
            self.modules.update({
                'tools.browser_session': None,
                'tools.browser_tool_session': module('tools.browser_tool_session',
                    _agent_browser_command_env=lambda path: {'AGENT_BROWSER_NO_AUTO_DIALOG': self.lower_flag}),
                'tools.browser_tool_cloud': module('tools.browser_tool_cloud', _get_cloud_provider=lambda: self.provider),
                'tools.browser_tool_cdp': module('tools.browser_tool_cdp',
                    _get_dialog_policy_config=lambda: (self.policy, 30.0)),
                'tools.browser_tool_lifecycle': self.lifecycle,
            })

    @staticmethod
    def owner(key):
        return key.removesuffix('::local').rsplit('@', 1)[0]

    def cleanup(self, owner):
        self.cleanup_calls.append(owner)
        for key in list(self.sessions):
            match = self.owner(key) == owner if self.native else key in (owner, owner + '::local')
            if match:
                del self.sessions[key]


@contextmanager
def runtime_fixture(native=True):
    fixture = RuntimeFixture(native)
    with patch.dict(sys.modules, fixture.modules), patch.dict(os.environ, {}, clear=True):
        yield fixture


class PreflightTests(unittest.TestCase):
    def test_native_uses_existing_chromium_without_retired_agent_browser(self):
        with runtime_fixture() as fixture:
            runtime = HermesRuntime()
            runtime.require_managed()
            self.assertTrue(runtime.native)
            fixture.launcher._resolve_executable.assert_called_once_with()
            fixture.launcher.chromium_ready.assert_not_called()
            self.assertNotIn('AGENT_BROWSER_NO_AUTO_DIALOG', os.environ)

    def test_legacy_uses_noninstalling_agent_browser_lookup(self):
        with runtime_fixture(native=False) as fixture:
            runtime = HermesRuntime()
            runtime.require_managed()
            self.assertFalse(runtime.native)
            fixture.install._find_agent_browser.assert_called_once_with(validate=False)
            fixture.launcher._resolve_executable.assert_not_called()

    def test_missing_inner_dependency_is_not_treated_as_legacy(self):
        failure = ModuleNotFoundError('missing native dependency', name='native_dependency')
        with patch('ui_runtime.hermes_compat.import_module', side_effect=failure) as importer:
            with self.assertRaises(ModuleNotFoundError) as caught:
                HermesRuntime()
            self.assertIs(caught.exception, failure)
            importer.assert_called_once_with('tools.browser_session')

    def test_partial_native_install_does_not_fall_back_to_legacy(self):
        with runtime_fixture():
            with patch.dict(sys.modules, {'tools.browser_session_cdp': None}):
                with self.assertRaises(ModuleNotFoundError) as caught:
                    HermesRuntime()
                self.assertEqual(caught.exception.name, 'tools.browser_session_cdp')

    def test_missing_executable_does_not_install(self):
        for native in (True, False):
            with self.subTest(native=native), runtime_fixture(native) as fixture:
                fixture.binary = None
                with self.assertRaisesRegex(EnvironmentBlocked, 'no automatic dependency install'):
                    HermesRuntime().require_managed()
                fixture.launcher.chromium_ready.assert_not_called()

    def test_missing_harness_is_reported_before_launch(self):
        with runtime_fixture() as fixture:
            fixture.cli._find_cli.return_value = None
            with self.assertRaisesRegex(EnvironmentBlocked, 'browser-harness'):
                HermesRuntime().require_managed()
            fixture.execute.assert_not_called()

    def test_external_and_shared_settings_are_rejected_in_both_runtimes(self):
        settings = ({'cdp_url': 'http://remote.invalid'}, {'use_real_profile': True},
                    {'user_data_dir': '/existing-profile'}, {'use_gateway': True},
                    {'engine': 'lightpanda'}, {'backend': 'camofox'})
        for native in (True, False):
            for config in settings:
                with self.subTest(native=native, config=config), runtime_fixture(native) as fixture:
                    fixture.config = config
                    with self.assertRaises(EnvironmentBlocked):
                        HermesRuntime().require_managed()
                    fixture.execute.assert_not_called()

    def test_external_environment_is_not_overridden(self):
        for key in ('BU_CDP_URL', 'BU_CDP_WS', 'BROWSER_CDP_URL', 'BU_AUTOSPAWN',
                    'BROWSER_USE_API_KEY', 'BROWSERBASE_API_KEY', 'FIRECRAWL_API_KEY', 'CAMOFOX_URL'):
            with self.subTest(key=key), runtime_fixture():
                os.environ[key] = 'configured'
                with self.assertRaises(EnvironmentBlocked):
                    HermesRuntime().require_managed()
                self.assertEqual(os.environ[key], 'configured')

    def test_resolved_cloud_provider_is_not_replaced(self):
        for native in (True, False):
            with self.subTest(native=native), runtime_fixture(native) as fixture:
                fixture.provider = object()
                with self.assertRaisesRegex(EnvironmentBlocked, 'cloud browser'):
                    HermesRuntime().require_managed()

    def test_live_native_cdp_override_blocks_even_without_config_field(self):
        with runtime_fixture() as fixture:
            fixture.live_cdp = 'ws://remote.invalid/devtools/browser/test'
            with self.assertRaisesRegex(EnvironmentBlocked, 'live CDP'):
                HermesRuntime().require_managed()
            fixture.launcher._resolve_executable.assert_not_called()

    def test_shared_desktop_or_nonlocal_placement_is_not_started(self):
        for mode in ('active', 'auto-start', 'terminal', 'refused'):
            with self.subTest(mode=mode), runtime_fixture() as fixture:
                if mode == 'active': fixture.desktop_env = {'DISPLAY': ':42'}
                elif mode == 'auto-start': fixture.config = {'headed': True}; fixture.auto_start = True
                else: fixture.placement = mode
                with self.assertRaises(EnvironmentBlocked):
                    HermesRuntime().require_managed()
                fixture.launcher._resolve_executable.assert_not_called()


class DialogPolicyTests(unittest.TestCase):
    def test_native_policy_does_not_fabricate_agent_browser_flag(self):
        with runtime_fixture():
            evidence = HermesRuntime().dialog_policy_evidence('/tmp/unused')
            self.assertEqual(evidence['managed_dialog_backend'], 'native-cdp')
            self.assertEqual(evidence['configured_dialog_policy'], 'must_respond')
            self.assertNotIn('effective_no_auto_dialog', evidence)
            self.assertNotIn('effective_dialog_policy', evidence)  # Requires the attached supervisor.

    def test_legacy_still_requires_the_effective_launch_flag(self):
        with runtime_fixture(native=False) as fixture:
            runtime = HermesRuntime()
            self.assertEqual(runtime.dialog_policy_evidence('/tmp/unused')['effective_no_auto_dialog'], '1')
            fixture.lower_flag = '0'
            with self.assertRaisesRegex(EnvironmentBlocked, 'patch is absent'):
                runtime.dialog_policy_evidence('/tmp/unused')

    def test_automatic_dialog_policy_cannot_pass_an_explicit_probe(self):
        for native in (True, False):
            for policy in ('auto_accept', 'auto_dismiss'):
                with self.subTest(native=native, policy=policy), runtime_fixture(native) as fixture:
                    fixture.policy = policy
                    with self.assertRaisesRegex(EnvironmentBlocked, 'must_respond'):
                        HermesRuntime().dialog_policy_evidence('/tmp/unused')


class OwnedCleanupTests(unittest.TestCase):
    def test_native_named_profile_and_sidecar_are_cleaned_without_other_tasks(self):
        with runtime_fixture() as fixture:
            fixture.sessions.update({key: {} for key in ('bu-named-owned@home', 'bu-named-owned@home::local',
                'task@home', 'other@home', 'bu-named-foreign@home::local')})
            self.assertTrue(HermesRuntime().cleanup_owned('task', 'owned'))
            self.assertEqual(set(fixture.cleanup_calls), {'task', 'bu-named-owned'})
            self.assertEqual(set(fixture.sessions), {'other@home', 'bu-named-foreign@home::local'})
            fixture.lifecycle.cleanup_all_browsers.assert_not_called()

    def test_native_unremoved_named_session_is_not_confirmed(self):
        with runtime_fixture() as fixture:
            fixture.sessions['bu-named-owned@home::local'] = {}
            fixture.lifecycle.cleanup_browser.side_effect = lambda task: None
            self.assertFalse(HermesRuntime().cleanup_owned('task', 'owned'))

    def test_legacy_exact_task_and_sidecar_cleanup_is_preserved(self):
        with runtime_fixture(native=False) as fixture:
            fixture.sessions.update({key: {} for key in ('task', 'task::local', 'other')})
            self.assertTrue(HermesRuntime().cleanup_owned('task', 'owned'))
            self.assertEqual(fixture.cleanup_calls, ['task'])
            self.assertEqual(set(fixture.sessions), {'other'})

    def test_empty_owner_never_becomes_default_or_global_cleanup(self):
        with runtime_fixture() as fixture:
            for task, session in (('', 'owned'), ('task', '')):
                with self.assertRaises(ValueError):
                    HermesRuntime().cleanup_owned(task, session)
            fixture.lifecycle.cleanup_browser.assert_not_called()

    def test_ui_constructor_and_close_use_native_ownership(self):
        from ui_runtime.hermes import HermesBrowser
        with runtime_fixture() as fixture:
            browser = HermesBrowser(task_id='probe', allowed_origins=['http://127.0.0.1'])
            key = fixture.cli._backend_cache_key(browser.task_id, browser.session)
            fixture.sessions.update({key: {}, key + '::local': {}, 'foreign@home': {}})
            with patch('ui_runtime.hermes.subprocess.run', return_value=SimpleNamespace(returncode=0)):
                result = browser.close()
            self.assertEqual(result['status'], 'PASS', result)
            self.assertEqual(set(fixture.sessions), {'foreign@home'})
            self.assertEqual(browser.close(), result)

    def test_harness_failure_still_cleans_owned_native_browser(self):
        from ui_runtime.hermes import HermesBrowser
        with runtime_fixture() as fixture:
            browser = HermesBrowser(task_id='probe', allowed_origins=['http://127.0.0.1'])
            fixture.sessions[fixture.cli._backend_cache_key(browser.task_id, browser.session)] = {}
            fixture.cli._find_cli.return_value = None
            result = browser.close()
            self.assertEqual(result['status'], 'WARNING')
            self.assertFalse(fixture.sessions)


class ProbePreflightTests(unittest.TestCase):
    def test_provider_rejection_never_launches_or_cleans_a_browser(self):
        from probe_managed_dialog import one_case
        with runtime_fixture() as fixture:
            fixture.provider = object()
            args = SimpleNamespace(mode='hermes', offline_fixture=False)
            report = asyncio.run(one_case(args, 'http://127.0.0.1:10080', 'reload', 'dismiss', False))
            self.assertEqual(report['result'], 'BLOCKED')
            self.assertEqual(report['failed_phase'], 'prepare')
            fixture.execute.assert_not_called()
            fixture.lifecycle.cleanup_browser.assert_not_called()

    def test_attached_supervisor_policy_is_checked_before_trigger(self):
        from probe_managed_dialog import one_case
        with runtime_fixture() as fixture:
            supervisor = SimpleNamespace(dialog_policy='auto_accept', stop=Mock())
            fixture.registry.get.return_value = supervisor
            args = SimpleNamespace(mode='hermes', offline_fixture=False)
            with patch('probe_managed_dialog.command', new_callable=AsyncMock):
                report = asyncio.run(one_case(args, 'http://127.0.0.1:10080', 'reload', 'dismiss', False))
            self.assertEqual(report['result'], 'BLOCKED')
            self.assertEqual(report['effective_dialog_policy'], 'auto_accept')
            self.assertEqual(report['managed_dialog_backend'], 'native-cdp')
            self.assertNotIn('effective_no_auto_dialog', report)
            fixture.execute.assert_called_once()  # Fixture open only; no dialog trigger.
            supervisor.stop.assert_called_once()


if __name__ == '__main__':
    unittest.main(verbosity=2)
