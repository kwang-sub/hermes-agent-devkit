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
            "HERMES_KANBAN_REGISTRATION_EVENT_HELPER",
            "HERMES_KANBAN_NOTIFY_REGISTRATION_ACK_TIMEOUT_SECONDS",
            "HERMES_KANBAN_NOTIFY_REGISTRATION_ACK_POLL_SECONDS",
            "HERMES_CLI",
            "HERMES_PYTHON",
            "FAKE_HERMES_MODE",
            "FAKE_REGISTRATION_MODE",
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
            if "show" in args:
                if mode == "show-fail":
                    print("task not found", file=sys.stderr)
                    raise SystemExit(2)
                print(json.dumps({{"task": {{"id": "t_test123"}}}}))
                raise SystemExit(0)

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
                    "delivery_mode": "notify",
                    "last_event_id": 1,
                    "last_ping_event_id": 1
                }}]))
                raise SystemExit(0)

            print("unexpected command", file=sys.stderr)
            raise SystemExit(3)
        """), encoding="utf-8")
        fake.chmod(0o755)
        return fake, log

    def make_registration_helper(self, root: Path) -> tuple[Path, Path]:
        log = root / "registration.jsonl"
        helper = root / "registration_helper.py"
        helper.write_text(textwrap.dedent(f"""\
            import json
            import os
            from pathlib import Path
            import sys

            log = Path({str(log)!r})
            args = sys.argv[1:]
            with log.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(args) + "\\n")
            if os.getenv("FAKE_REGISTRATION_MODE") == "fail":
                print("REGISTRATION_EVENT_STATUS=failed")
                raise SystemExit(1)
            print("REGISTRATION_EVENT_STATUS=queued")
            print("REGISTRATION_EVENT_ID=1")
        """), encoding="utf-8")
        return helper, log

    def make_fake_runtime_python(self, root: Path) -> tuple[Path, Path]:
        log = root / "runtime-python.jsonl"
        runtime = root / "hermes-python"
        runtime.write_text(textwrap.dedent(f"""\
            #!{sys.executable}
            import json
            import os
            from pathlib import Path
            import sys

            log = Path({str(log)!r})
            with log.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(sys.argv[1:]) + "\\n")
            os.execv({sys.executable!r}, [{sys.executable!r}, *sys.argv[1:]])
        """), encoding="utf-8")
        runtime.chmod(0o755)
        return runtime, log

    def notification_env(self, fake: Path, registration: Path, **extra: str) -> dict[str, str]:
        env = {
            "HERMES_KANBAN_NOTIFY_ENABLED": "true",
            "HERMES_KANBAN_NOTIFY_PLATFORM": "discord",
            "HERMES_KANBAN_NOTIFY_TARGET": "123456789",
            "HERMES_KANBAN_NOTIFY_DELIVERY_MODE": "notify",
            "HERMES_KANBAN_NOTIFY_CHAT_TYPE": "channel",
            "HERMES_KANBAN_NOTIFY_PROFILE": "default",
            "HERMES_KANBAN_REGISTRATION_EVENT_HELPER": str(registration),
            "HERMES_KANBAN_NOTIFY_REGISTRATION_ACK_TIMEOUT_SECONDS": "0.1",
            "HERMES_KANBAN_NOTIFY_REGISTRATION_ACK_POLL_SECONDS": "0.01",
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
        self.assertIn("NOTIFY_BOARD=wow-batch", proc.stdout)

    def test_missing_config_blocks_dispatch_gate(self) -> None:
        proc = self.run_helper({"HERMES_KANBAN_NOTIFY_ENABLED": "true"})
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("NOTIFY_STATUS=failed", proc.stdout)
        self.assertIn("HERMES_KANBAN_NOTIFY_PLATFORM", proc.stdout)

    def test_success_subscribes_then_enqueues_registration_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake, log = self.make_fake_cli(root)
            registration, registration_log = self.make_registration_helper(root)
            proc = self.run_helper(self.notification_env(fake, registration))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("TASK_READBACK_VERIFIED=true", proc.stdout)
            self.assertIn("NOTIFY_STATUS=subscribed", proc.stdout)
            self.assertIn("NOTIFY_VERIFIED=true", proc.stdout)
            self.assertIn("NOTIFY_REGISTRATION_EVENT=queued", proc.stdout)
            self.assertIn("NOTIFY_REGISTRATION_EVENT_ID=1", proc.stdout)
            self.assertIn("NOTIFY_REGISTRATION_DELIVERED=true", proc.stdout)
            self.assertIn("NOTIFY_BOARD=wow-batch", proc.stdout)

            calls = self.read_log(log)
            self.assertEqual(len(calls), 4)
            for call in calls:
                self.assertEqual(call[:3], ["kanban", "--board", "wow-batch"])
            self.assertEqual(calls[0][3:6], ["show", "t_test123", "--json"])
            self.assertEqual(calls[1][3:5], ["notify-subscribe", "t_test123"])
            self.assertEqual(calls[2][3:6], ["notify-list", "t_test123", "--json"])
            self.assertEqual(calls[3][3:6], ["notify-list", "t_test123", "--json"])
            self.assertEqual(
                self.read_log(registration_log),
                [["--board", "wow-batch", "--task-id", "t_test123"]],
            )

    def test_explicit_hermes_python_runs_shared_and_registration_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake, _ = self.make_fake_cli(root)
            registration, registration_log = self.make_registration_helper(root)
            runtime, runtime_log = self.make_fake_runtime_python(root)
            proc = self.run_helper(
                self.notification_env(fake, registration, HERMES_PYTHON=str(runtime))
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("NOTIFY_STATUS=subscribed", proc.stdout)

            runtime_calls = self.read_log(runtime_log)
            self.assertEqual(len(runtime_calls), 2)
            self.assertEqual(Path(runtime_calls[0][0]).name, "kanban_notify_subscribe.py")
            self.assertEqual(Path(runtime_calls[1][0]), registration)
            self.assertEqual(
                self.read_log(registration_log),
                [["--board", "wow-batch", "--task-id", "t_test123"]],
            )

    def test_default_notifier_profile_is_default_gateway(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake, log = self.make_fake_cli(root)
            registration, _ = self.make_registration_helper(root)
            env = self.notification_env(fake, registration)
            env.pop("HERMES_KANBAN_NOTIFY_PROFILE")
            proc = self.run_helper(env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            subscribe = self.read_log(log)[1]
            idx = subscribe.index("--notifier-profile")
            self.assertEqual(subscribe[idx + 1], "default")

    def test_task_readback_failure_blocks_before_subscription(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake, log = self.make_fake_cli(root)
            registration, registration_log = self.make_registration_helper(root)
            proc = self.run_helper(self.notification_env(fake, registration, FAKE_HERMES_MODE="show-fail"))
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("task read-back failed", proc.stdout)
            self.assertEqual(len(self.read_log(log)), 1)
            self.assertFalse(registration_log.exists())

    def test_subscription_failure_blocks_before_registration_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake, log = self.make_fake_cli(root)
            registration, registration_log = self.make_registration_helper(root)
            proc = self.run_helper(self.notification_env(fake, registration, FAKE_HERMES_MODE="subscribe-fail"))
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("subscription command failed", proc.stdout)
            self.assertEqual(len(self.read_log(log)), 2)
            self.assertFalse(registration_log.exists())

    def test_subscription_must_be_visible_before_registration_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake, log = self.make_fake_cli(root)
            registration, registration_log = self.make_registration_helper(root)
            proc = self.run_helper(self.notification_env(fake, registration, FAKE_HERMES_MODE="verify-missing"))
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("did not find the expected", proc.stdout)
            self.assertEqual(len(self.read_log(log)), 3)
            self.assertFalse(registration_log.exists())

    def test_registration_enqueue_failure_blocks_dispatch_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake, log = self.make_fake_cli(root)
            registration, registration_log = self.make_registration_helper(root)
            proc = self.run_helper(self.notification_env(fake, registration, FAKE_REGISTRATION_MODE="fail"))
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("registration notification enqueue failed", proc.stdout)
            self.assertIn("NOTIFY_STATUS=failed", proc.stdout)
            self.assertEqual(len(self.read_log(log)), 3)
            self.assertEqual(len(self.read_log(registration_log)), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
