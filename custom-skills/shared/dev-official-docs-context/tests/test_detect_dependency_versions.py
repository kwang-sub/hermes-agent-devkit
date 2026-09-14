#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "detect_dependency_versions.py"


def run_helper(workspace: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--workspace", str(workspace), *extra],
        text=True,
        capture_output=True,
        check=False,
    )


class DetectDependencyVersionsTest(unittest.TestCase):
    def test_npm_lock_resolved_version_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(json.dumps({
                "packageManager": "npm@11.17.0",
                "engines": {"node": ">=22.13.0"},
                "dependencies": {"next": "^16.3.0"},
            }), encoding="utf-8")
            (root / "package-lock.json").write_text(json.dumps({
                "lockfileVersion": 3,
                "packages": {
                    "": {"dependencies": {"next": "^16.3.0"}},
                    "node_modules/next": {"version": "16.3.5"},
                },
            }), encoding="utf-8")
            proc = run_helper(root, "--package", "next")
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertIn("DEPENDENCY_1_RESOLVED_VERSION=16.3.5", proc.stdout)
            self.assertIn("DEPENDENCY_1_VERSION_SOURCE=package-lock.json", proc.stdout)
            self.assertIn("PACKAGE_MANAGER=npm", proc.stdout)
            self.assertIn("STATUS=pass", proc.stdout)

    def test_scoped_package_from_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(json.dumps({
                "packageManager": "npm@11.0.0",
                "dependencies": {"@supabase/supabase-js": "^2.0.0"},
            }), encoding="utf-8")
            (root / "package-lock.json").write_text(json.dumps({
                "lockfileVersion": 3,
                "packages": {
                    "node_modules/@supabase/supabase-js": {"version": "2.57.4"},
                },
            }), encoding="utf-8")
            proc = run_helper(root, "--package", "@supabase/supabase-js")
            self.assertEqual(proc.returncode, 0, proc.stdout)
            self.assertIn("DEPENDENCY_1_RESOLVED_VERSION=2.57.4", proc.stdout)

    def test_multiple_package_roots_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("a", "b"):
                child = root / name
                child.mkdir()
                (child / "package.json").write_text("{}", encoding="utf-8")
            proc = run_helper(root, "--package", "next")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("multiple package roots found", proc.stdout)
            self.assertIn("STATUS=blocked", proc.stdout)

    def test_explicit_package_root_selects_leaf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text("{}", encoding="utf-8")
            leaf = root / "frontend"
            leaf.mkdir()
            (leaf / "package.json").write_text(json.dumps({
                "dependencies": {"react": "19.3.0"},
            }), encoding="utf-8")
            proc = run_helper(root, "--package-root", "frontend", "--package", "react")
            self.assertEqual(proc.returncode, 0, proc.stdout)
            self.assertIn("DEPENDENCY_1_RESOLVED_VERSION=19.3.0", proc.stdout)
            self.assertIn("DEPENDENCY_1_VERSION_SOURCE=package.json-exact", proc.stdout)

    def test_package_root_cannot_escape_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other:
            root = Path(tmp)
            outside = Path(other)
            (outside / "package.json").write_text("{}", encoding="utf-8")
            proc = run_helper(root, "--package-root", str(outside), "--package", "react")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("must stay inside workspace", proc.stdout)


if __name__ == "__main__":
    unittest.main()
