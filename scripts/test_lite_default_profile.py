#!/usr/bin/env python3
"""Lite-only profile migration tests: no actual Docker or persistent data."""
from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import lite_default_profile as migration
from lite_mode import selected, write_yaml, marker


class LiteDefaultMigrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.old = self.root / "profiles" / "coder"
        self.old.mkdir(parents=True)
        (self.old / "oauth.json").write_bytes(b"keep-private-data")
        self.config = self.root / "config.yaml"
        write_yaml(self.config, {
            "model": {"provider": "openai-codex", "id": "keep"},
            "custom_key": {"retain": True},
            "skills": {
                "external_dirs": ["/opt/custom-skills/coder", "/opt/custom-skills/personal"],
                "auto_load": ["dev-implement-plan", "my-custom-skill"],
            },
            "toolsets": ["hermes-cli"],
        })

    def test_dry_run_never_mutates(self):
        content = self.config.read_bytes()
        r = migration.apply(self.root, archive=True, dry_run=True)
        self.assertEqual(r["status"], "planned")
        self.assertEqual(self.config.read_bytes(), content)
        self.assertTrue(self.old.exists())

    def test_default_config_preserves_custom_and_is_idempotent(self):
        a = migration.apply(self.root)
        self.assertTrue(a["default_config_changed"])
        d, _ = migration.load(self.config)
        s = selected(d)
        self.assertEqual(d["model"]["id"], "keep")
        self.assertEqual(d["custom_key"]["retain"], True)
        self.assertIn("/opt/custom-skills/personal", s["dirs"])
        self.assertNotIn("/opt/custom-skills/coder", s["dirs"])
        self.assertIn("dev-lite-session", s["autoload"])
        self.assertNotIn("dev-implement-plan", s["autoload"])
        self.assertIn("my-custom-skill", s["autoload"])
        self.assertIn("kanban", s["tools"])
        content = self.config.read_bytes()
        b = migration.apply(self.root)
        self.assertFalse(b["default_config_changed"])
        self.assertEqual(self.config.read_bytes(), content)
        self.assertEqual((self.old / "oauth.json").read_bytes(), b"keep-private-data")

    def test_profiles_are_archived_without_deletion(self):
        migration.apply(self.root, archive=True)
        archive = self.root / "devkit-lite/legacy-profiles/coder/oauth.json"
        self.assertEqual(archive.read_bytes(), b"keep-private-data")
        self.assertFalse(self.old.exists())
        migration.apply(self.root, archive=True)
        self.assertEqual(archive.read_bytes(), b"keep-private-data")

    def test_archive_conflict_rejected_before_config_write(self):
        dest = self.root / "devkit-lite/legacy-profiles/coder"
        dest.mkdir(parents=True)
        prior = self.config.read_bytes()
        with self.assertRaisesRegex(ValueError, "Both active and archived"):
            migration.apply(self.root, archive=True)
        self.assertEqual(self.config.read_bytes(), prior)

    def test_running_task_blocks_before_mutation(self):
        db_path = self.root / "kanban.db"
        with sqlite3.connect(db_path) as conn:
            conn.execute("CREATE TABLE tasks (status TEXT)")
            conn.execute("INSERT INTO tasks VALUES ('running')")
        before = self.config.read_bytes()
        with self.assertRaises(RuntimeError):
            migration.apply(self.root, archive=True)
        self.assertEqual(self.config.read_bytes(), before)
        self.assertTrue(self.old.exists())

    def test_existing_overlay_is_archived_and_verified(self):
        from lite_mode import merge
        old_fields = selected(migration.load(self.config)[0])
        state = {"schema": 2, "phase": "applied", "before": old_fields,
                 "applied": merge(old_fields)}
        marker(self.root).parent.mkdir(parents=True)
        marker(self.root).write_text(json.dumps(state), encoding="utf-8")
        write_yaml(self.config, migration.replace(migration.load(self.config)[0], state["applied"]))
        migration.apply(self.root)
        self.assertFalse(marker(self.root).exists())
        self.assertTrue((self.root / "devkit-lite/profile-state.lite-only-archived.json").exists())

    def test_unknown_overlay_blocks(self):
        marker(self.root).parent.mkdir(parents=True)
        marker(self.root).write_text('{"schema": 99}', encoding="utf-8")
        old = self.config.read_bytes()
        with self.assertRaisesRegex(ValueError, "Unknown"):
            migration.apply(self.root)
        self.assertEqual(self.config.read_bytes(), old)


if __name__ == "__main__":
    unittest.main()
