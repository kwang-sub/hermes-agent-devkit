#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "subscribe_notification.py"


class SubscribeNotificationTests(unittest.TestCase):
    def run_helper(self, env_overrides: dict[str, str], *, board: str = "wow-batch") -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        for key in (
            "HERMES_KANBAN_NOTIFY_ENABLED",
            "HERMES_KANBAN_NOTIFY_PLATFORM",
            "HERMES_KANBAN_NOTIFY_TARGET",
            "HERMES_KANBAN_NOTIFY_DELIVERY_MODE",
            "HERMES_KANBAN_NOTIFY_CHAT_TYPE",
            "HERMES_KANBAN_NOTIFY_PROFILE",
            "HERMES_CLI",
            "HERMES_PYTHON",
            "FAKE_HERMES_MODE",
        ):
            env.pop(key, None)
        env.update(env_overrides)
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--board", board, "--task-id", "t_test123"],
            text=True,
            capture_output=True,
            env=env,
        )

    def make_fake_cli(self, root: Path) -> tuple[Path, Path]:
        log = root / "args.jsonl"
        fake = root / "hermes"
        fake.write_text(textwrap.dedent(f"""\
            #!{sys.executable}
            import json
            import os
            from pathlib import Path
            import sys

            log = Path({str(log)!r})
            args = sys.argv[1:]
            with log.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(args) + "\\n")

            mode = os.getenv("FAKE_HERMES_MODE", "success")
            if "notify-subscribe" in args:
                if mode == "subscribe-fail":
                    print("gateway unavailable", file=sys.stderr)
                    raise SystemExit(2)
                raise SystemExit(0)

            if "notify-list" in args:
                if mode == "verify-fail":
                    print("verification unavailable", file=sys.stderr)
                    raise SystemExit(2)
                if mode == "verify-missing":
                    print("[]")
                    raise SystemExit(0)
                print(json.dumps([{{
                    "task_id": "t_test123",
                    "platform": "discord",
                    "chat_id": "123456789",
                    "notifier_profile": "default",
                    "delivery_mode": "notify"
                }}]))
                raise SystemExit(0)

            print("unexpected command", file=sys.stderr)
            raise SystemExit(3)
        """), encoding="utf-8")
        fake.chmod(0o755)
        return fake, log

    def notification_env(self, fake: Path, **extra: str) -> dict[str, str]:
        env = {
            "HERMES_KANBAN_NOTIFY_ENABLED": "true",
            "HERMES_KANBAN_NOTIFY_PLATFORM": "discord",
            "HERMES_KANBAN_NOTIFY_TARGET": "123456789",
            "HERMES_KANBAN_NOTIFY_DELIVERY_MODE": "notify",
            "HERMES_KANBAN_NOTIFY_CHAT_TYPE": "channel",
            "HERMES_CLI": str(fake),
        }
        env.update(extra)
        return env

    def read_log(self, log: Path) -> list[list[str]]:
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]

    def test_disabled_is_noop(self) -> None:
        proc = self.run_helper({"HERMES_KANBAN_NOTIFY_ENABLED": "false"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("NOTIFY_STATUS=disabled", proc.stdout)

    def test_missing_config_is_warning_not_dispatch_failure(self) -> None:
        proc = self.run_helper({"HERMES_KANBAN_NOTIFY_ENABLED": "true"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("NOTIFY_STATUS=warning", proc.stdout)
        self.assertIn("NOTIFY_VERIFIED=false", proc.stdout)

    def test_success_uses_native_subscription_and_readback_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake, log = self.make_fake_cli(root)
            proc = self.run_helper(self.notification_env(fake))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("NOTIFY_STATUS=subscribed", proc.stdout)
            self.assertIn("NOTIFY_VERIFIED=true", proc.stdout)
            self.assertIn("NOTIFY_PROFILE=default", proc.stdout)

            calls = self.read_log(log)
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0][:5], ["kanban", "--board", "wow-batch", "notify-subscribe", "t_test123"])
            self.assertEqual(calls[1][:6], ["kanban", "--board", "wow-batch", "notify-list", "t_test123", "--json"])

    def test_notifier_profile_is_fixed_to_default_gateway(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake, log = self.make_fake_cli(root)
            proc = self.run_helper(self.notification_env(fake, HERMES_KANBAN_NOTIFY_PROFILE="orchestrator"))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            subscribe = self.read_log(log)[0]
            idx = subscribe.index("--notifier-profile")
            self.assertEqual(subscribe[idx + 1], "default")

    def test_subscription_failure_is_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake, log = self.make_fake_cli(root)
            proc = self.run_helper(self.notification_env(fake, FAKE_HERMES_MODE="subscribe-fail"))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("NOTIFY_STATUS=warning", proc.stdout)
            self.assertEqual(len(self.read_log(log)), 1)

    def test_readback_failure_is_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake, log = self.make_fake_cli(root)
            proc = self.run_helper(self.notification_env(fake, FAKE_HERMES_MODE="verify-fail"))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("NOTIFY_STATUS=warning", proc.stdout)
            self.assertEqual(len(self.read_log(log)), 2)

    def test_missing_subscription_after_readback_is_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake, log = self.make_fake_cli(root)
            proc = self.run_helper(self.notification_env(fake, FAKE_HERMES_MODE="verify-missing"))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("NOTIFY_STATUS=warning", proc.stdout)
            self.assertIn("did not find the expected", proc.stdout)
            self.assertEqual(len(self.read_log(log)), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
