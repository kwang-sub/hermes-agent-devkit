#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "subscribe_notification.py"


class SubscribeNotificationTests(unittest.TestCase):
    def run_helper(self, env_overrides: dict[str, str]) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        for key in (
            "HERMES_KANBAN_NOTIFY_ENABLED",
            "HERMES_KANBAN_NOTIFY_PLATFORM",
            "HERMES_KANBAN_NOTIFY_TARGET",
            "HERMES_KANBAN_NOTIFY_DELIVERY_MODE",
            "HERMES_KANBAN_NOTIFY_CHAT_TYPE",
            "HERMES_CLI",
        ):
            env.pop(key, None)
        env.update(env_overrides)
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--task-id", "t_test123"],
            text=True,
            capture_output=True,
            env=env,
        )

    def test_disabled_is_noop(self) -> None:
        proc = self.run_helper({"HERMES_KANBAN_NOTIFY_ENABLED": "false"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("NOTIFY_STATUS=disabled", proc.stdout)

    def test_missing_config_is_non_blocking_warning(self) -> None:
        proc = self.run_helper({"HERMES_KANBAN_NOTIFY_ENABLED": "true"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("NOTIFY_STATUS=warning", proc.stdout)
        self.assertIn("HERMES_KANBAN_NOTIFY_PLATFORM", proc.stdout)

    def test_success_builds_platform_neutral_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "args.txt"
            fake = Path(tmp) / "hermes"
            fake.write_text(textwrap.dedent(f"""\
                #!/bin/sh
                printf '%s\\n' "$@" > '{log}'
                exit 0
            """), encoding="utf-8")
            fake.chmod(0o755)
            proc = self.run_helper({
                "HERMES_KANBAN_NOTIFY_ENABLED": "true",
                "HERMES_KANBAN_NOTIFY_PLATFORM": "discord",
                "HERMES_KANBAN_NOTIFY_TARGET": "123456789",
                "HERMES_KANBAN_NOTIFY_DELIVERY_MODE": "notify",
                "HERMES_KANBAN_NOTIFY_CHAT_TYPE": "channel",
                "HERMES_CLI": str(fake),
            })
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("NOTIFY_STATUS=subscribed", proc.stdout)
            args = log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(args[:3], ["kanban", "notify-subscribe", "t_test123"])
            self.assertIn("discord", args)
            self.assertIn("123456789", args)
            self.assertIn("channel", args)

    def test_command_failure_does_not_block_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "hermes"
            fake.write_text("#!/bin/sh\necho gateway unavailable >&2\nexit 2\n", encoding="utf-8")
            fake.chmod(0o755)
            proc = self.run_helper({
                "HERMES_KANBAN_NOTIFY_ENABLED": "true",
                "HERMES_KANBAN_NOTIFY_PLATFORM": "discord",
                "HERMES_KANBAN_NOTIFY_TARGET": "123",
                "HERMES_CLI": str(fake),
            })
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("NOTIFY_STATUS=warning", proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
