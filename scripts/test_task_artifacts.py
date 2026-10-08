#!/usr/bin/env python3
"""Task scratch/snapshot hygiene and status-guarded cleanup regressions."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import task_artifacts as artifacts


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.scratch = self.root / "scratch"
        self.db = self.root / "board.db"
        self.user_file = self.project / "user.py"
        self.user_file.write_text("print('keep')\n")
        with sqlite3.connect(self.db) as db:
            db.execute(
                "CREATE TABLE tasks(id TEXT PRIMARY KEY, status TEXT, workspace_path TEXT)"
            )
            db.execute(
                "INSERT INTO tasks VALUES (?,?,?)", ("t_a", "review", str(self.project))
            )

    def tearDown(self):
        self.temp.cleanup()

    def test_cleanup_only_owned_scratch_after_done(self):
        scratch = artifacts.allocate_scratch(self.scratch, self.project, "t_a")
        (scratch / "analysis.py").write_text("print('temp')\n")
        self.assertFalse(artifacts.cleanup_completed_scratch(
            board_db=self.db, workspace=self.project,
            task_id="t_a", root=self.scratch))
        self.assertTrue((scratch / "analysis.py").exists())
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE tasks SET status='done' WHERE id='t_a'")
        self.assertTrue(artifacts.cleanup_completed_scratch(
            board_db=self.db, workspace=self.project,
            task_id="t_a", root=self.scratch))
        self.assertFalse(scratch.exists())
        self.assertTrue(self.user_file.exists())

    def test_unmarked_directory_not_removed(self):
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE tasks SET status='done' WHERE id='t_a'")
        scratch = artifacts.scratch_path(self.scratch, self.project, "t_a")
        scratch.mkdir(parents=True)
        (scratch / "unexpected.py").write_text("safe\n")
        self.assertFalse(artifacts.cleanup_completed_scratch(
            board_db=self.db, workspace=self.project,
            task_id="t_a", root=self.scratch))
        self.assertTrue((scratch / "unexpected.py").exists())

    def test_snapshot_reader_limits_scope_and_fields(self):
        cache = self.root / "spillover"
        cache.mkdir()
        snapshot = cache / "call_example.txt"
        snapshot.write_text(json.dumps({
            "task": {"id": "t_a", "title": "title", "status": "review",
                     "body": "change", "comments": [{"body": "old"}, {"body": "new"}]}
        }))
        with patch.dict(os.environ, {"HERMES_DEVKIT_SNAPSHOT_FIXTURE_ROOT": str(cache)}):
            result = artifacts.inspect_snapshot(
                source=snapshot, profile="coder",
                fields=["id", "status", "body"], last_comments=1)
            self.assertEqual(result["id"], "t_a")
            self.assertEqual(len(result["comments"]), 1)
            with self.assertRaises(artifacts.ArtifactError):
                artifacts.inspect_snapshot(
                    source=snapshot, profile="coder", fields=["secret"], last_comments=0)

    def test_invalid_task_id_does_not_escape_root(self):
        with self.assertRaises(artifacts.ArtifactError):
            artifacts.allocate_scratch(self.scratch, self.project, "../unsafe")


if __name__ == "__main__":
    unittest.main(verbosity=2)
