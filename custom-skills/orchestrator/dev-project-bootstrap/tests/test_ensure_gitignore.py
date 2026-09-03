from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ensure_gitignore.py"
SPEC = importlib.util.spec_from_file_location("ensure_gitignore", SCRIPT)
assert SPEC and SPEC.loader
gitignore = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gitignore)


def git(cmd: list[str], repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *cmd], cwd=repo, text=True, capture_output=True)


class HermesGitIgnoreTest(unittest.TestCase):
    def make_repo(self, root: Path) -> Path:
        repo = root / "repo"
        repo.mkdir()
        result = git(["init", "-b", "dev"], repo)
        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout)
        return repo

    def test_creates_managed_block_and_ignores_only_local_flow_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))

            self.assertEqual("created", gitignore.ensure_gitignore(repo))
            text = (repo / ".gitignore").read_text(encoding="utf-8")

            self.assertIn(gitignore.MANAGED_START, text)
            self.assertIn("/.hermes/", text)
            self.assertIn("/.worktrees/", text)
            self.assertNotIn("AGENTS.md", text)
            self.assertNotIn(".gitattributes", text)
            gitignore.verify_managed_entries(repo)

    def test_preserves_existing_content_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))
            path = repo / ".gitignore"
            path.write_text("build/\n*.log\n", encoding="utf-8")

            self.assertEqual("updated", gitignore.ensure_gitignore(repo))
            first = path.read_text(encoding="utf-8")
            self.assertTrue(first.startswith("build/\n*.log\n"))

            self.assertEqual("unchanged", gitignore.ensure_gitignore(repo))
            second = path.read_text(encoding="utf-8")
            self.assertEqual(first, second)

    def test_repairs_tampered_managed_block_without_touching_user_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))
            path = repo / ".gitignore"
            path.write_text(
                "dist/\n\n"
                f"{gitignore.MANAGED_START}\n"
                "/.hermes/\n"
                f"{gitignore.MANAGED_END}\n"
                "keep-me/\n",
                encoding="utf-8",
            )

            self.assertEqual("updated", gitignore.ensure_gitignore(repo))
            text = path.read_text(encoding="utf-8")
            self.assertIn("dist/", text)
            self.assertIn("keep-me/", text)
            self.assertIn("/.worktrees/", text)
            self.assertEqual(1, text.count(gitignore.MANAGED_START))
            self.assertEqual(1, text.count(gitignore.MANAGED_END))

    def test_blocks_malformed_managed_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))
            path = repo / ".gitignore"
            path.write_text(f"{gitignore.MANAGED_START}\n/.hermes/\n", encoding="utf-8")

            with self.assertRaises(gitignore.GitIgnoreError):
                gitignore.ensure_gitignore(repo)


if __name__ == "__main__":
    unittest.main()
