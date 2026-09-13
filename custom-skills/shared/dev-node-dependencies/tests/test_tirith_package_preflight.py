#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "tirith_package_preflight.py"


FAKE_TIRITH = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

state = Path(os.environ["FAKE_TIRITH_STATE"])
mode = os.environ.get("FAKE_TIRITH_MODE", "allow")
args = sys.argv[1:]

if args[:2] == ["daemon", "status"]:
    raise SystemExit(0 if state.exists() else 1)
if args[:3] == ["daemon", "start", "--detach"]:
    state.write_text("running", encoding="utf-8")
    print("started")
    raise SystemExit(0)
if args and args[0] == "check":
    if mode == "allow":
        print(json.dumps({"action":"allow","findings":[]}))
        raise SystemExit(0)
    if mode == "positive":
        print(json.dumps({"action":"warn","findings":[{"rule_id":"package_risk","severity":"MEDIUM"}]}))
        raise SystemExit(2)
    if mode == "incomplete_then_allow":
        if state.exists():
            print(json.dumps({"action":"allow","findings":[]}))
            raise SystemExit(0)
        print(json.dumps({"action":"warn","findings":[{"rule_id":"analysis_incomplete","severity":"MEDIUM"}]}))
        raise SystemExit(2)
    if mode == "always_incomplete":
        print(json.dumps({"action":"warn","findings":[{"rule_id":"analysis_incomplete","severity":"MEDIUM"}]}))
        raise SystemExit(2)

print(json.dumps({"action":"block","findings":[{"rule_id":"unexpected"}]}))
raise SystemExit(1)
'''


class TirithPackagePreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.binary = root / "tirith"
        self.binary.write_text(textwrap.dedent(FAKE_TIRITH), encoding="utf-8")
        self.binary.chmod(0o755)
        self.state = root / "daemon.state"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def run_helper(self, mode: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["FAKE_TIRITH_MODE"] = mode
        env["FAKE_TIRITH_STATE"] = str(self.state)
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--tirith-bin",
                str(self.binary),
                "--command",
                "npm install @supabase/ssr",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            check=False,
        )

    def test_clean_allow_passes_without_daemon(self) -> None:
        proc = self.run_helper("allow")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("TIRITH_PREFLIGHT=allow", proc.stdout)
        self.assertIn("TIRITH_DAEMON=not-needed", proc.stdout)
        self.assertIn("TIRITH_RETRY=none", proc.stdout)

    def test_analysis_incomplete_starts_daemon_and_rechecks_once(self) -> None:
        proc = self.run_helper("incomplete_then_allow")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(self.state.exists())
        self.assertIn("TIRITH_FIRST_FINDINGS=analysis_incomplete", proc.stdout)
        self.assertIn("TIRITH_SECOND_ACTION=allow", proc.stdout)
        self.assertIn("TIRITH_RETRY=daemon-recheck-pass", proc.stdout)
        self.assertIn("TIRITH_PREFLIGHT=allow", proc.stdout)

    def test_positive_finding_never_starts_daemon_or_bypasses(self) -> None:
        proc = self.run_helper("positive")
        self.assertEqual(proc.returncode, 2)
        self.assertFalse(self.state.exists())
        self.assertIn("TIRITH_PREFLIGHT=approval_required", proc.stdout)
        self.assertIn("TIRITH_FIRST_FINDINGS=package_risk", proc.stdout)
        self.assertIn("TIRITH_RETRY=none", proc.stdout)

    def test_incomplete_after_daemon_remains_blocked(self) -> None:
        proc = self.run_helper("always_incomplete")
        self.assertEqual(proc.returncode, 2)
        self.assertTrue(self.state.exists())
        self.assertIn("TIRITH_PREFLIGHT=approval_required", proc.stdout)
        self.assertIn("TIRITH_RETRY=daemon-recheck-fail", proc.stdout)
        self.assertIn("TIRITH_SECOND_FINDINGS=analysis_incomplete", proc.stdout)

    def test_missing_binary_is_unavailable_not_security_bypass(self) -> None:
        missing = self.binary.parent / "missing-tirith"
        env = os.environ.copy()
        env.pop("TIRITH_BIN", None)
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--tirith-bin", str(missing), "--command", "npm install react"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            check=False,
        )
        # The host may have a real tirith on PATH; force a deterministic empty PATH.
        if "TIRITH_BINARY=NONE" not in proc.stdout:
            env["PATH"] = str(missing.parent)
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--tirith-bin", str(missing), "--command", "npm install react"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                check=False,
            )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("TIRITH_PREFLIGHT=unavailable", proc.stdout)
        self.assertIn("Hermes terminal guard remains authoritative", proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
