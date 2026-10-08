#!/usr/bin/env python3
"""Task-scoped handoff and lifecycle cleanup regression tests."""
from __future__ import annotations

from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom-skills" / "_lib"))
from task_handoff import (
    cleanup_completed_handoff, clear_handoff, handoff_path,
    load_handoff, save_handoff,
)


class TaskHandoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        self.db = Path(self.tmp.name) / "board.db"
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                "CREATE TABLE tasks(id TEXT PRIMARY KEY, status TEXT, workspace_path TEXT)"
            )
            conn.execute(
                "INSERT INTO tasks VALUES(?,?,?)", ("t_A", "review", str(self.repo))
            )
            conn.execute(
                "INSERT INTO tasks VALUES(?,?,?)", ("t_B", "review", str(self.repo))
            )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def save(self, task_id: str, fingerprint: str) -> None:
        save_handoff(
            self.repo, scope=["route.java"], effective_paths=["route.java"],
            fingerprint=fingerprint, task_id=task_id,
        )

    def test_task_a_cannot_replace_or_delete_task_b(self) -> None:
        self.save("t_A", "a" * 64)
        self.save("t_B", "b" * 64)
        self.assertNotEqual(
            handoff_path(self.repo, "t_A"), handoff_path(self.repo, "t_B")
        )
        self.assertEqual(
            load_handoff(self.repo, "t_B")["effective_scope_sha256"], "b" * 64
        )
        clear_handoff(self.repo, "t_A")
        self.assertIsNone(load_handoff(self.repo, "t_A"))
        self.assertIsNotNone(load_handoff(self.repo, "t_B"))

    def test_completion_gate_preserves_active_and_other_task(self) -> None:
        self.save("t_A", "a" * 64)
        self.save("t_B", "b" * 64)
        self.assertFalse(cleanup_completed_handoff(
            board_db=self.db, workspace=self.repo, task_id="t_A"))
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE tasks SET status='done' WHERE id='t_A'")
        self.assertFalse(cleanup_completed_handoff(
            board_db=self.db, workspace=Path(self.tmp.name), task_id="t_A"))
        self.assertTrue(cleanup_completed_handoff(
            board_db=self.db, workspace=self.repo, task_id="t_A"))
        self.assertFalse(cleanup_completed_handoff(
            board_db=self.db, workspace=self.repo, task_id="t_A"))
        self.assertIsNotNone(load_handoff(self.repo, "t_B"))

    def test_invalid_id_and_worktree_path_safety(self) -> None:
        with self.assertRaises(ValueError):
            handoff_path(self.repo, "../t_A")
        self.assertFalse(cleanup_completed_handoff(
            board_db=self.db, workspace=self.repo, task_id="t_unknown"))
        self.assertTrue(
            str(handoff_path(self.repo, "t_A")).startswith(str(self.repo / ".git"))
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
