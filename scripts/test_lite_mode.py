#!/usr/bin/env python3
"""Regression tests for the non-destructive Hermes Lite adapter."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
import tempfile
import unittest

import lite_mode as lite


class LiteProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = self.root / "config.yaml"
        self.config.write_text(
            "model: custom-provider/model\n"
            "user_config:\n  preferences: keep\n"
            "skills:\n  external_dirs:\n    - /home/user/custom-skills\n"
            "toolsets:\n  - hermes-cli\n",
            encoding="utf-8",
        )
        (self.root / "memories").mkdir()
        (self.root / "memories" / "MEMORY.md").write_text("original memory", encoding="utf-8")
        (self.root / "sessions").mkdir()
        (self.root / "sessions" / "keep").write_text("session", encoding="utf-8")
        self.original = lite.load(self.config)[0]

    def test_apply_restore_preserve_other_fields_and_data(self):
        lite.apply(self.root)
        after = lite.load(self.config)[0]
        self.assertEqual(after["model"], "custom-provider/model")
        self.assertEqual(after["user_config"], {"preferences": "keep"})
        self.assertEqual(after["skills"]["external_dirs"][0], "/home/user/custom-skills")
        self.assertIn("kanban", after["toolsets"])
        self.assertTrue(lite.marker(self.root).exists())
        self.assertEqual(len(list((self.root / "devkit-lite" / "backups").glob("config-*.yaml"))), 1)

        # A user may update unrelated model settings while Lite is active.
        after["model"] = "other/model"
        lite.write_yaml(self.config, after)
        lite.restore(self.root)
        restored = lite.load(self.config)[0]
        self.assertEqual(restored["model"], "other/model")
        self.assertEqual(lite.selected(restored), lite.selected(self.original))
        self.assertEqual((self.root / "memories" / "MEMORY.md").read_text(), "original memory")
        self.assertEqual((self.root / "sessions" / "keep").read_text(), "session")
        self.assertFalse(lite.marker(self.root).exists())

    def test_idempotent_apply(self):
        lite.apply(self.root)
        first_state = lite.read_marker(self.root)
        first_backups = list((self.root / "devkit-lite" / "backups").iterdir())
        lite.apply(self.root)
        self.assertEqual(first_state, lite.read_marker(self.root))
        self.assertEqual(first_backups, list((self.root / "devkit-lite" / "backups").iterdir()))

    def test_conflicting_user_skill_change_refuses_restore(self):
        lite.apply(self.root)
        edited = lite.load(self.config)[0]
        edited["skills"]["external_dirs"].append("/home/user/new-skills")
        lite.write_yaml(self.config, edited)
        with self.assertRaisesRegex(RuntimeError, "refusing overwrite"):
            lite.restore(self.root)
        self.assertTrue(lite.marker(self.root).exists())
        self.assertIn("/home/user/new-skills", lite.load(self.config)[0]["skills"]["external_dirs"])

    def test_running_kanban_is_blocked_without_mutation(self):
        board = self.root / "kanban" / "boards" / "demo"
        board.mkdir(parents=True)
        path = board / "kanban.db"
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE tasks (status TEXT)")
            conn.execute("INSERT INTO tasks(status) VALUES ('running')")
            conn.commit()
        with self.assertRaisesRegex(RuntimeError, "Active Kanban"):
            lite.apply(self.root)
        self.assertFalse(lite.marker(self.root).exists())
        self.assertEqual(lite.load(self.config)[0], self.original)
        with sqlite3.connect(path) as conn:
            self.assertEqual(conn.execute("SELECT status FROM tasks").fetchone()[0], "running")

    def test_prepared_state_can_be_retried(self):
        lite.apply(self.root)
        state = lite.read_marker(self.root)
        state["phase"] = "prepared"
        lite.write_marker(self.root, state)
        lite.apply(self.root)
        self.assertEqual(lite.read_marker(self.root)["phase"], "applied")

    def test_original_absent_restores_absence(self):
        self.config.unlink()
        lite.apply(self.root)
        self.assertTrue(self.config.exists())
        lite.restore(self.root)
        self.assertFalse(self.config.exists())

    def test_invalid_yaml_blocks_before_creating_marker(self):
        self.config.write_text("skills: [not-a-map]", encoding="utf-8")
        with self.assertRaises(ValueError):
            lite.apply(self.root)
        self.assertFalse(lite.marker(self.root).exists())

    def test_writes_keep_private_permissions(self):
        self.config.chmod(0o600)
        lite.apply(self.root)
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
