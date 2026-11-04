#!/usr/bin/env python3
"""Regression tests for legacy patching and the native dialog contract gate.

Small executable fixtures model the upstream interfaces. They never start a
browser or access configuration, and deliberate behavior changes must be blocked.
"""
from __future__ import annotations

import ast
import asyncio
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import textwrap
import types
import unittest

from check_hermes_native_dialog_policy import verify_config_forwarding, verify_responses
from patch_hermes_browser_dialog_policy import MARKER


def source(value: str) -> str:
    return textwrap.dedent(value).lstrip()


LEGACY = source('''
    def _agent_browser_command_env(socket_dir):
        env = {"PRESERVED": "value"}
        env["AGENT_BROWSER_SOCKET_DIR"] = socket_dir
        return env
''')

CONFIG = source('''
    def get_dialog_policy_config():
        from tools.browser_session_cloud import browser_cfg
        from tools.browser_supervisor_dialogs import DEFAULT_DIALOG_POLICY, _VALID_POLICIES
        policy = browser_cfg("dialog_policy", DEFAULT_DIALOG_POLICY)
        if policy not in _VALID_POLICIES:
            policy = DEFAULT_DIALOG_POLICY
        return policy, float(browser_cfg("dialog_timeout_s", 300.0))
''')

CLI = source('''
    def _attach_vault_supervisor(env, task_id):
        from tools.browser_session_cdp import get_dialog_policy_config, resolve_cdp_override
        from tools.browser_supervisor import SUPERVISOR_REGISTRY
        policy, timeout_s = get_dialog_policy_config()
        SUPERVISOR_REGISTRY.get_or_start(
            task_id=task_id, cdp_url=resolve_cdp_override(env["BU_CDP_WS"]),
            dialog_policy=policy, dialog_timeout_s=timeout_s)

    def dispatch(env, task_id, cmd, code, timeout):
        _attach_vault_supervisor(env, task_id)
        return _run_cli_killing_process_group(cmd, code, env, timeout)
''')

DIALOGS = source('''
    from types import SimpleNamespace

    DEFAULT_DIALOG_POLICY = "must_respond"
    DEFAULT_DIALOG_TIMEOUT_S = 300.0
    _VALID_POLICIES = {"must_respond", "auto_dismiss", "auto_accept"}

    class DialogSupervisionMixin:
        async def _on_dialog_opening(self, params, session_id):
            self._dialog_seq += 1
            dialog = SimpleNamespace(id=str(self._dialog_seq), type=params["type"],
                                     cdp_session_id=session_id)
            if self.dialog_policy == "must_respond":
                self._pending_dialogs[dialog.id] = dialog
                return
            await self._handle_dialog_cdp(
                dialog, accept=self.dialog_policy == "auto_accept", prompt_text="")

        async def _handle_dialog_cdp(self, dialog, *, accept, prompt_text):
            await self._cdp("Page.handleJavaScriptDialog", {"accept": accept},
                            session_id=dialog.cdp_session_id, timeout=5.0)
            self._pending_dialogs.pop(dialog.id, None)

        async def _on_dialog_closed(self, params, session_id):
            pass

        EVENT_HANDLERS = {
            "Page.javascriptDialogOpening": _on_dialog_opening,
            "Page.javascriptDialogClosed": _on_dialog_closed,
        }
''')

SUPERVISOR = source('''
    import threading
    from tools.browser_supervisor_dialogs import (
        DialogSupervisionMixin, DEFAULT_DIALOG_POLICY, DEFAULT_DIALOG_TIMEOUT_S)

    class FrameTrackingMixin:
        EVENT_HANDLERS = {}

    class CDPSupervisor(DialogSupervisionMixin, FrameTrackingMixin):
        def __init__(self, task_id, cdp_url, *, dialog_policy=DEFAULT_DIALOG_POLICY,
                     dialog_timeout_s=DEFAULT_DIALOG_TIMEOUT_S):
            self.task_id, self.cdp_url = task_id, cdp_url
            self.dialog_policy = dialog_policy
            self.dialog_timeout_s = dialog_timeout_s
            self._state_lock = threading.Lock()
            self._pending_dialogs, self._dialog_watchdogs = {}, {}
            self._recent_dialogs = []
            self._dialog_seq, self._page_session_id = 0, None

        _EVENT_HANDLERS = {
            **DialogSupervisionMixin.EVENT_HANDLERS,
            **FrameTrackingMixin.EVENT_HANDLERS,
        }

        def respond_to_dialog(self, action, dialog, prompt_text=""):
            return self._handle_dialog_cdp(
                dialog, accept=(action == "accept"), prompt_text=prompt_text)

    class _SupervisorRegistry:
        def get_or_start(self, task_id, cdp_url, *, dialog_policy=DEFAULT_DIALOG_POLICY,
                         dialog_timeout_s=DEFAULT_DIALOG_TIMEOUT_S, start_timeout=15.0):
            supervisor = CDPSupervisor(
                task_id=task_id, cdp_url=cdp_url,
                dialog_policy=dialog_policy, dialog_timeout_s=dialog_timeout_s)
            supervisor.start(timeout=start_timeout)
            return supervisor
''')

NATIVE_SOURCES = {
    "browser_session.py": source('''
        def _create_chromium_session(key):
            from tools.browser_launcher import launch_chromium
            return launch_chromium(key)
    '''),
    "browser_launcher.py": source('''
        import subprocess

        def launch_chromium(key):
            return _launch_owned(key)

        def _launch_owned(key):
            return _spawn(["chromium", key], {})

        def _spawn(argv, env):
            return subprocess.Popen(argv, env=env)
    '''),
    "browser_session_cdp.py": CONFIG,
    "browser_use_cli.py": CLI,
    "browser_supervisor.py": SUPERVISOR,
    "browser_supervisor_dialogs.py": DIALOGS,
    "browser_dialog_tool.py": source('''
        def browser_dialog(action, prompt_text=None, dialog_id=None, task_id=None):
            supervisor = SUPERVISOR_REGISTRY.get(task_id)
            return supervisor.respond_to_dialog(
                action=action, prompt_text=prompt_text, dialog_id=dialog_id)
    '''),
}


def dialog_module(value: str = DIALOGS) -> types.ModuleType:
    module = types.ModuleType("fixture_dialogs")
    exec(compile(value, "<dialog-behavior-fixture>", "exec"), module.__dict__)
    return module


def snapshot(root: Path) -> dict:
    """Include generated files too: native validation must not write a pyc cache."""
    return {str(path.relative_to(root)): (path.read_bytes(), stat.S_IMODE(path.stat().st_mode),
                                        path.stat().st_mtime_ns)
            for path in root.rglob("*") if path.is_file()}


class PatchCLITests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="devkit-dialog-contract-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.tools = self.root / "tools"
        self.tools.mkdir()
        self.legacy = self.tools / "browser_tool_session.py"

    def run_patch(self, *, check_only=False):
        command = [sys.executable, str(Path(__file__).with_name("patch_hermes_browser_dialog_policy.py")),
                   "--hermes-root", str(self.root)]
        if check_only:
            command.append("--check-only")
        return subprocess.run(command, capture_output=True, text=True, timeout=15, check=False)

    def native_layout(self):
        for name, value in NATIVE_SOURCES.items():
            (self.tools / name).write_text(value, encoding="utf-8")

    def replace(self, name, before, after):
        path = self.tools / name
        value = path.read_text(encoding="utf-8")
        self.assertEqual(value.count(before), 1, "mutation must target one fixture operation")
        path.write_text(value.replace(before, after), encoding="utf-8")

    def assert_blocked(self, result):
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("BROWSER_DIALOG_POLICY_PATCH=BLOCKED:", result.stdout)
        self.assertNotIn("BROWSER_DIALOG_POLICY_PATCH=PASS", result.stdout)

    def test_legacy_check_only_rejects_uninstalled_patch_without_writing(self):
        self.legacy.write_text(LEGACY, encoding="utf-8")
        before = snapshot(self.root)
        result = self.run_patch(check_only=True)
        self.assert_blocked(result)
        self.assertIn("not installed", result.stdout)
        self.assertEqual(snapshot(self.root), before)

    def test_legacy_apply_preserves_mode_and_repeat_is_idempotent(self):
        self.legacy.write_text(LEGACY, encoding="utf-8")
        self.legacy.chmod(0o751)
        mode = stat.S_IMODE(self.legacy.stat().st_mode)
        applied = self.run_patch()
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        self.assertIn("CONTRACT=legacy-agent-browser-patched", applied.stdout)
        self.assertEqual(self.legacy.read_text(encoding="utf-8").count(MARKER), 1)
        self.assertEqual(stat.S_IMODE(self.legacy.stat().st_mode), mode)
        before = snapshot(self.root)
        for check_only in (True, False):
            with self.subTest(check_only=check_only):
                result = self.run_patch(check_only=check_only)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(snapshot(self.root), before)
        self.assertEqual(list(self.tools.glob(".dialog-policy-*")), [])

    def test_native_apply_and_check_are_read_only(self):
        self.native_layout()
        before = snapshot(self.root)
        for check_only in (False, True):
            with self.subTest(check_only=check_only):
                result = self.run_patch(check_only=check_only)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("CONTRACT=native-chromium-supervisor", result.stdout)
                self.assertIn("BROWSER_DIALOG_POLICY_PATCH=PASS", result.stdout)
                self.assertEqual(snapshot(self.root), before)

    def test_missing_legacy_and_native_implementations_is_blocked(self):
        self.assert_blocked(self.run_patch())

    def test_missing_native_supervisor_does_not_pass_as_retirement(self):
        self.native_layout()
        (self.tools / "browser_supervisor.py").unlink()
        self.assert_blocked(self.run_patch(check_only=True))

    def test_present_legacy_file_cannot_fall_back_to_native_on_drift(self):
        self.native_layout()
        self.legacy.write_text("def unrelated_function():\n    pass\n", encoding="utf-8")
        before = snapshot(self.root)
        result = self.run_patch()
        self.assert_blocked(result)
        self.assertNotIn("CONTRACT=native-chromium-supervisor", result.stdout)
        self.assertEqual(snapshot(self.root), before)

    def test_unknown_native_launcher_is_rejected(self):
        self.native_layout()
        self.replace("browser_launcher.py", "subprocess.Popen(argv, env=env)",
                     "unverified_launcher(argv, env=env)")
        self.assert_blocked(self.run_patch())

    def test_missing_supervisor_attachment_is_rejected(self):
        self.native_layout()
        self.replace("browser_use_cli.py", "    _attach_vault_supervisor(env, task_id)\n", "    pass\n")
        self.assert_blocked(self.run_patch())

    def test_supervisor_attachment_after_browser_execution_is_rejected(self):
        self.native_layout()
        self.replace("browser_use_cli.py",
                     "    _attach_vault_supervisor(env, task_id)\n"
                     "    return _run_cli_killing_process_group(cmd, code, env, timeout)\n",
                     "    result = _run_cli_killing_process_group(cmd, code, env, timeout)\n"
                     "    _attach_vault_supervisor(env, task_id)\n"
                     "    return result\n")
        self.assert_blocked(self.run_patch())

    def test_supervisor_must_use_the_verified_dialog_handlers(self):
        self.native_layout()
        self.replace("browser_supervisor.py", "CDPSupervisor(DialogSupervisionMixin, FrameTrackingMixin)",
                     "CDPSupervisor(FrameTrackingMixin)")
        self.assert_blocked(self.run_patch())

    def test_constructor_must_preserve_requested_policy(self):
        self.native_layout()
        self.replace("browser_supervisor.py", "self.dialog_policy = dialog_policy",
                     'self.dialog_policy = "auto_accept"')
        self.assert_blocked(self.run_patch())

    def test_registry_must_forward_requested_policy(self):
        self.native_layout()
        self.replace("browser_supervisor.py", "dialog_policy=dialog_policy, ", "")
        self.assert_blocked(self.run_patch())

    def test_dialog_opening_event_must_reach_the_verified_handler(self):
        self.native_layout()
        self.replace("browser_supervisor_dialogs.py",
                     '        "Page.javascriptDialogOpening": _on_dialog_opening,\n', "")
        self.assert_blocked(self.run_patch())

    def test_supervisor_must_keep_dialog_events_connected(self):
        self.native_layout()
        self.replace("browser_supervisor.py", "        **DialogSupervisionMixin.EVENT_HANDLERS,\n", "")
        self.assert_blocked(self.run_patch())

    def test_supervisor_must_not_override_dialog_opening_handler(self):
        self.native_layout()
        self.replace("browser_supervisor.py", "        **FrameTrackingMixin.EVENT_HANDLERS,\n",
                     "        **FrameTrackingMixin.EVENT_HANDLERS,\n"
                     '        "Page.javascriptDialogOpening": lambda *args: None,\n')
        self.assert_blocked(self.run_patch())

    def test_dialog_tool_cannot_replace_requested_action(self):
        self.native_layout()
        self.replace("browser_dialog_tool.py", "action=action", 'action="accept"')
        self.assert_blocked(self.run_patch())

    def test_supervisor_cannot_translate_dismiss_as_accept(self):
        self.native_layout()
        self.replace("browser_supervisor.py", 'accept=(action == "accept")', "accept=True")
        self.assert_blocked(self.run_patch())

    def test_native_behavior_failure_is_reported_by_cli(self):
        self.native_layout()
        self.replace("browser_supervisor_dialogs.py", '{"accept": accept}', '{"accept": not accept}')
        self.assert_blocked(self.run_patch(check_only=True))


class NativePolicyBehaviorTests(unittest.TestCase):
    def test_valid_config_and_policy_variants_reach_supervisor(self):
        verify_config_forwarding(ast.parse(CONFIG), ast.parse(CLI), dialog_module())

    def test_hardcoded_accept_policy_is_rejected(self):
        cli = CLI.replace("dialog_policy=policy", 'dialog_policy="auto_accept"')
        with self.assertRaisesRegex(RuntimeError, "policy is not forwarded"):
            verify_config_forwarding(ast.parse(CONFIG), ast.parse(cli), dialog_module())

    def test_configured_timeout_is_preserved(self):
        cli = CLI.replace("dialog_timeout_s=timeout_s", "dialog_timeout_s=300.0")
        with self.assertRaisesRegex(RuntimeError, "policy is not forwarded"):
            verify_config_forwarding(ast.parse(CONFIG), ast.parse(cli), dialog_module())

    def test_invalid_policy_must_not_fall_back_to_auto_accept(self):
        config = CONFIG.replace("policy = DEFAULT_DIALOG_POLICY", 'policy = "auto_accept"')
        with self.assertRaisesRegex(RuntimeError, "policy is not forwarded"):
            verify_config_forwarding(ast.parse(config), ast.parse(CLI), dialog_module())

    def test_native_confirm_and_beforeunload_response_contract(self):
        asyncio.run(verify_responses(dialog_module(), ast.parse(SUPERVISOR)))

    def test_must_respond_cannot_accept_before_explicit_response(self):
        dialogs = DIALOGS.replace("self._pending_dialogs[dialog.id] = dialog",
                                  'await self._handle_dialog_cdp(dialog, accept=True, prompt_text="")')
        with self.assertRaisesRegex(RuntimeError, "before an explicit response"):
            asyncio.run(verify_responses(dialog_module(dialogs), ast.parse(SUPERVISOR)))

    def test_accept_and_dismiss_cannot_be_swapped(self):
        dialogs = DIALOGS.replace('{"accept": accept}', '{"accept": not accept}')
        with self.assertRaisesRegex(RuntimeError, "accept/dismiss behavior changed"):
            asyncio.run(verify_responses(dialog_module(dialogs), ast.parse(SUPERVISOR)))

    def test_responded_dialog_must_leave_pending_queue(self):
        dialogs = DIALOGS.replace("self._pending_dialogs.pop(dialog.id, None)", "pass")
        with self.assertRaisesRegex(RuntimeError, "accept/dismiss behavior changed"):
            asyncio.run(verify_responses(dialog_module(dialogs), ast.parse(SUPERVISOR)))

    def test_default_must_require_explicit_response(self):
        module = dialog_module()
        module.DEFAULT_DIALOG_POLICY = "auto_accept"
        with self.assertRaisesRegex(RuntimeError, "default no longer requires an explicit response"):
            asyncio.run(verify_responses(module, ast.parse(SUPERVISOR)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
