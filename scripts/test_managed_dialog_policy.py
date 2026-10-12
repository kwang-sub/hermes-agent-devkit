#!/usr/bin/env python3
"""Managed launch patch tests; no browser or extra dependencies are required."""
from __future__ import annotations
import sys
import types
import unittest
from unittest.mock import patch
from patch_hermes_browser_dialog_policy import patch_source, INSERT, MARKER

SOURCE = '''def _agent_browser_command_env(socket_dir: str) -> dict[str, str]:
    from pm import env_for
    env = env_for("agent-browser", base_env={"OTHER": "preserved"})
    env["AGENT_BROWSER_SOCKET_DIR"] = socket_dir
    return env
'''


class ManagedDialogPolicyTests(unittest.TestCase):
    def environment(self, policy, env_override=None):
        module = types.ModuleType("tools.browser_tool_cdp")
        module._get_dialog_policy_config = lambda: (policy, 300.0)
        pm = types.ModuleType("pm")
        pm.env_for = lambda *a, base_env: {**base_env, **(env_override or {})}
        with patch.dict(sys.modules, {"tools": types.ModuleType("tools"),
                                     "tools.browser_tool_cdp": module, "pm": pm}):
            namespace = {}
            exec(patch_source(SOURCE), namespace)
            return namespace["_agent_browser_command_env"]("/tmp/test-owned")

    def test_must_respond_disables_lower_auto_accept(self):
        self.assertEqual(self.environment("must_respond")["AGENT_BROWSER_NO_AUTO_DIALOG"], "1")

    def test_auto_dismiss_is_not_overridden_by_lower_auto_accept(self):
        self.assertEqual(self.environment("auto_dismiss")["AGENT_BROWSER_NO_AUTO_DIALOG"], "1")

    def test_explicit_auto_accept_is_preserved(self):
        self.assertNotIn("AGENT_BROWSER_NO_AUTO_DIALOG", self.environment("auto_accept"))

    def test_supervisor_policy_wins_over_conflicting_lower_flag(self):
        self.assertEqual(self.environment("must_respond", {"AGENT_BROWSER_NO_AUTO_DIALOG": "0"})
                         ["AGENT_BROWSER_NO_AUTO_DIALOG"], "1")

    def test_unrelated_environment_and_socket_are_preserved(self):
        env = self.environment("must_respond")
        self.assertEqual(env["OTHER"], "preserved")
        self.assertEqual(env["AGENT_BROWSER_SOCKET_DIR"], "/tmp/test-owned")

    def test_patch_is_idempotent(self):
        result = patch_source(SOURCE)
        self.assertEqual(patch_source(result), result)
        self.assertEqual(result.count(MARKER), 1)

    def test_missing_anchor_rejected(self):
        with self.assertRaises(RuntimeError):
            patch_source(SOURCE.replace('env["AGENT_BROWSER_SOCKET_DIR"] = socket_dir', 'pass'))

    def test_partial_patch_rejected(self):
        with self.assertRaises(RuntimeError):
            patch_source(patch_source(SOURCE).replace('= "1"', '= "0"'))

    def test_wrong_function_rejected(self):
        with self.assertRaises(RuntimeError):
            patch_source(SOURCE.replace("_agent_browser_command_env", "_other"))

    def test_existing_upstream_policy_is_not_silently_overwritten(self):
        changed=SOURCE.replace('    return env', '    env["AGENT_BROWSER_NO_AUTO_DIALOG"]="0"\n    return env')
        with self.assertRaises(RuntimeError):
            patch_source(changed)

    def test_patch_is_after_pm_scrubbing(self):
        text = patch_source(SOURCE)
        self.assertGreater(text.index(INSERT), text.index('env = env_for'))


if __name__ == "__main__":
    unittest.main(verbosity=2)
