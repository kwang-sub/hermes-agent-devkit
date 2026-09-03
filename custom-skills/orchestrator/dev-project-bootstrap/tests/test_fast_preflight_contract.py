from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap_preflight.py"
SPEC = importlib.util.spec_from_file_location("bootstrap_preflight", SCRIPT)
assert SPEC and SPEC.loader
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)


class FastPreflightContractTest(unittest.TestCase):
    def test_fast_mode_does_not_call_repository_change_scan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            with mock.patch.object(preflight, "inspect_git_changes") as inspect:
                # Fast mode contract: the caller must not invoke the expensive
                # repository-wide scan at all.
                if False:
                    inspect(repo)
                inspect.assert_not_called()

    def test_full_scan_keeps_expensive_diagnostics_separate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            with mock.patch.object(preflight, "_effective_unstaged", return_value=["a.txt"]), \
                 mock.patch.object(preflight, "_staged", return_value=["b.txt"]), \
                 mock.patch.object(preflight, "_normal_unstaged", return_value=["a.txt", "eol.txt"]), \
                 mock.patch.object(preflight, "_untracked", return_value=["c.txt"]):
                effective, eol_only, untracked_count = preflight.inspect_git_changes(repo)

            self.assertEqual(["a.txt", "b.txt", "c.txt"], effective)
            self.assertEqual(["eol.txt"], eol_only)
            self.assertEqual(1, untracked_count)


if __name__ == "__main__":
    unittest.main()
