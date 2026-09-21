from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap.py"
SPEC = importlib.util.spec_from_file_location("bootstrap_launcher", SCRIPT)
assert SPEC and SPEC.loader
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return result.stdout.strip()


class BootstrapLauncherTest(unittest.TestCase):
    def test_launcher_only_flags_are_not_forwarded_to_project_bootstrap(self) -> None:
        args = [
            "--repo",
            "/workspace/example",
            "--full-preflight",
            "--refresh-stack",
            "--board",
            "example",
        ]

        self.assertEqual(
            ["--repo", "/workspace/example", "--board", "example"],
            bootstrap.project_args(args),
        )

    def test_configuration_security_stage_is_in_normal_and_refresh_paths(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(2, source.count('scripts / "ensure_config_security.py"'))
        self.assertLess(
            source.index('scripts / "ensure_gitignore.py"'),
            source.index('scripts / "ensure_config_security.py"'),
        )

    def test_repository_lock_blocks_duplicate_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()

            with bootstrap.bootstrap_lock(str(repo)):
                with self.assertRaises(bootstrap.BootstrapLauncherError):
                    with bootstrap.bootstrap_lock(str(repo)):
                        pass

    def test_windows_workspace_path_maps_to_container_workspace(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "HERMES_HOST_WORKSPACE_PATH": "D:/workspace",
                "HERMES_CONTAINER_WORKSPACE_PATH": "/workspace",
            },
            clear=False,
        ):
            self.assertEqual(
                "/workspace/product/oc/oc-dml",
                bootstrap.canonical_repo_path(r"D:\workspace\product\oc\oc-dml"),
            )

    def test_mechanically_converted_wsl_workspace_alias_is_recovered(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "HERMES_HOST_WORKSPACE_PATH": "D:/workspace",
                "HERMES_CONTAINER_WORKSPACE_PATH": "/workspace",
            },
            clear=False,
        ):
            self.assertEqual(
                "/workspace/product/oc/oc-dml",
                bootstrap.canonical_repo_path(
                    "/mnt/d/workspace/product/oc/oc-dml"
                ),
            )

    def test_custom_workspace_mapping_is_supported(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "HERMES_HOST_WORKSPACE_PATH": "E:/source",
                "HERMES_CONTAINER_WORKSPACE_PATH": "/code",
            },
            clear=False,
        ):
            self.assertEqual(
                "/code/team/app",
                bootstrap.canonical_repo_path("E:/source/team/app"),
            )
            self.assertEqual(
                "/code/team/app",
                bootstrap.canonical_repo_path("/mnt/e/source/team/app"),
            )

    def test_unrelated_mnt_path_is_not_rewritten(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "HERMES_HOST_WORKSPACE_PATH": "D:/workspace",
                "HERMES_CONTAINER_WORKSPACE_PATH": "/workspace",
            },
            clear=False,
        ):
            temp_path = "/mnt/c/Users/example/AppData/Local/Temp/image.png"
            self.assertEqual(temp_path, bootstrap.canonical_repo_path(temp_path))

    def test_rewrite_repo_arg_updates_forwarded_project_args(self) -> None:
        args = ["--repo", r"D:\workspace\product\oc\oc-dml", "--board", "oc-dml"]
        self.assertEqual(
            ["--repo", "/workspace/product/oc/oc-dml", "--board", "oc-dml"],
            bootstrap.rewrite_repo_arg(args, "/workspace/product/oc/oc-dml"),
        )

    def test_linked_worktree_resolves_to_primary_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            worktree = root / "linked"
            subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True, text=True)
            git(repo, "config", "user.name", "DevKit Test")
            git(repo, "config", "user.email", "devkit@example.invalid")
            (repo / "README.md").write_text("base\n", encoding="utf-8")
            git(repo, "add", "README.md")
            git(repo, "commit", "-m", "chore: base")
            git(repo, "branch", "feature/follow-up")
            git(repo, "worktree", "add", str(worktree), "feature/follow-up")

            env = os.environ.copy()
            primary = bootstrap.resolve_primary_repository(str(worktree), env=env)
            self.assertEqual(primary, repo.resolve())
            self.assertGreaterEqual(int(env.get("GIT_CONFIG_COUNT", "0")), 2)

    def test_linked_worktree_resolution_uses_process_local_safe_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            worktree = root / "linked"
            subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True, text=True)
            git(repo, "config", "user.name", "DevKit Test")
            git(repo, "config", "user.email", "devkit@example.invalid")
            (repo / "README.md").write_text("base\n", encoding="utf-8")
            git(repo, "add", "README.md")
            git(repo, "commit", "-m", "chore: base")
            git(repo, "branch", "feature/safe")
            git(repo, "worktree", "add", str(worktree), "feature/safe")

            env = os.environ.copy()
            env["GIT_TEST_ASSUME_DIFFERENT_OWNER"] = "1"
            primary = bootstrap.resolve_primary_repository(str(worktree), env=env)
            self.assertEqual(primary, repo.resolve())
            safe_values = {
                env.get(f"GIT_CONFIG_VALUE_{index}")
                for index in range(int(env.get("GIT_CONFIG_COUNT", "0")))
                if env.get(f"GIT_CONFIG_KEY_{index}") == "safe.directory"
            }
            self.assertIn(str(worktree.resolve()), safe_values)
            self.assertIn(str(repo.resolve()), safe_values)


    def test_non_git_project_requires_explicit_acknowledgement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "legacy"
            project.mkdir()
            with self.assertRaises(bootstrap.BootstrapLauncherError):
                bootstrap.resolve_project_workspace(
                    str(project),
                    env=os.environ.copy(),
                    allow_non_git=False,
                )

            resolved, is_git = bootstrap.resolve_project_workspace(
                str(project),
                env=os.environ.copy(),
                allow_non_git=True,
            )
            self.assertEqual(resolved, project.resolve())
            self.assertFalse(is_git)

    def test_recorded_non_git_acknowledgement_is_reused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "legacy"
            metadata = project / ".hermes" / "project.yaml"
            metadata.parent.mkdir(parents=True)
            metadata.write_text(
                "# managed-by: dev-project-bootstrap\n"
                "version: 4\n\n"
                "version_control:\n"
                "  type: \"none\"\n"
                "  non_git_write_acknowledged: true\n",
                encoding="utf-8",
            )

            resolved, is_git = bootstrap.resolve_project_workspace(
                str(project),
                env=os.environ.copy(),
                allow_non_git=False,
            )
            self.assertEqual(resolved, project.resolve())
            self.assertFalse(is_git)


if __name__ == "__main__":
    unittest.main()
