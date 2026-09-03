from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


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


if __name__ == "__main__":
    unittest.main()
