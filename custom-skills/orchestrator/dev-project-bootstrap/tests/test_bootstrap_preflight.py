from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap_preflight.py"
SPEC = importlib.util.spec_from_file_location("bootstrap_preflight", SCRIPT)
assert SPEC and SPEC.loader
bootstrap_preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap_preflight)


def git(cmd: list[str], repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *cmd], cwd=repo, text=True, capture_output=True)


class BootstrapGitScanTest(unittest.TestCase):
    def make_repo(self, root: Path) -> Path:
        repo = root / "repo"
        repo.mkdir()
        git(["init", "-b", "dev"], repo)
        git(["config", "user.email", "test@example.invalid"], repo)
        git(["config", "user.name", "Bootstrap Preflight Test"], repo)
        git(["config", "core.autocrlf", "false"], repo)
        (repo / "app.txt").write_text("baseline\n", encoding="utf-8")
        git(["add", "app.txt"], repo)
        result = git(["commit", "-m", "baseline"], repo)
        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout)
        return repo

    def test_fast_scan_ignores_crlf_only_tracked_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))
            (repo / "app.txt").write_bytes(b"baseline\r\n")

            effective, eol_only, untracked_count = (
                bootstrap_preflight.inspect_git_changes(repo)
            )

            self.assertEqual([], effective)
            self.assertEqual([], eol_only)
            self.assertIsNone(untracked_count)

    def test_fast_scan_keeps_real_tracked_and_staged_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))
            (repo / "app.txt").write_text("real change\n", encoding="utf-8")
            (repo / "staged.txt").write_text("staged\n", encoding="utf-8")
            git(["add", "staged.txt"], repo)

            effective, _, _ = bootstrap_preflight.inspect_git_changes(repo)

            self.assertEqual(["app.txt", "staged.txt"], effective)

    def test_fast_scan_skips_untracked_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))
            (repo / "untracked.bin").write_bytes(b"x" * 1024)

            effective, _, untracked_count = (
                bootstrap_preflight.inspect_git_changes(repo)
            )

            self.assertEqual([], effective)
            self.assertIsNone(untracked_count)

    def test_full_scan_counts_eol_noise_and_untracked_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))
            (repo / "app.txt").write_bytes(b"baseline\r\n")
            (repo / "new.txt").write_text("new\n", encoding="utf-8")

            effective, eol_only, untracked_count = (
                bootstrap_preflight.inspect_git_changes(repo, full_scan=True)
            )

            self.assertEqual(["new.txt"], effective)
            self.assertEqual(["app.txt"], eol_only)
            self.assertEqual(1, untracked_count)


if __name__ == "__main__":
    unittest.main()
