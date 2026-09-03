from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap.py"
SPEC = importlib.util.spec_from_file_location("bootstrap_launcher", SCRIPT)
assert SPEC and SPEC.loader
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)


class BootstrapLauncherTest(unittest.TestCase):
    def test_full_preflight_flag_is_not_forwarded_to_project_bootstrap(self) -> None:
        args = [
            "--repo",
            "/workspace/example",
            "--full-preflight",
            "--board",
            "example",
        ]

        self.assertEqual(
            ["--repo", "/workspace/example", "--board", "example"],
            bootstrap.project_args(args),
        )

    def test_repository_lock_blocks_duplicate_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()

            with bootstrap.bootstrap_lock(str(repo)):
                with self.assertRaises(bootstrap.BootstrapLauncherError):
                    with bootstrap.bootstrap_lock(str(repo)):
                        pass


if __name__ == "__main__":
    unittest.main()
