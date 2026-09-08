#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import unittest

SCRIPT = Path(__file__).resolve().with_name("kanban_registration_event.py")


class KanbanRegistrationEventTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root / "kanban.db"
        conn = sqlite3.connect(self.db)
        try:
            conn.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, status TEXT)")
            conn.execute(
                "CREATE TABLE task_events ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, run_id INTEGER, "
                "kind TEXT, payload TEXT, created_at INTEGER)"
            )
            conn.execute("INSERT INTO tasks (id, status) VALUES ('t_test123', 'blocked')")
            conn.commit()
        finally:
            conn.close()

        package = self.root / "hermes_cli"
        package.mkdir()
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "kanban_db_connect.py").write_text(textwrap.dedent("""\
            import os, sqlite3
            def connect(board=None):
                conn = sqlite3.connect(os.environ['REG_TEST_DB'])
                conn.row_factory = sqlite3.Row
                return conn
        """), encoding="utf-8")
        (package / "kanban_db.py").write_text(textwrap.dedent("""\
            from contextlib import contextmanager
            from types import SimpleNamespace

            def get_task(conn, task_id):
                row = conn.execute('SELECT id, status FROM tasks WHERE id=?', (task_id,)).fetchone()
                return None if row is None else SimpleNamespace(id=row['id'], status=row['status'])

            @contextmanager
            def write_txn(conn):
                try:
                    conn.execute('BEGIN IMMEDIATE')
                    yield conn
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise
        """), encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_helper(self, task_id: str = "t_test123") -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.root)
        env["REG_TEST_DB"] = str(self.db)
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--board", "board-a", "--task-id", task_id],
            text=True,
            capture_output=True,
            env=env,
        )

    def events(self) -> list[sqlite3.Row]:
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        try:
            return conn.execute(
                "SELECT task_id, kind, payload FROM task_events ORDER BY id"
            ).fetchall()
        finally:
            conn.close()

    def test_first_run_queues_registered_event_and_second_is_idempotent(self) -> None:
        first = self.run_helper()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("REGISTRATION_EVENT_STATUS=queued", first.stdout)

        second = self.run_helper()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("REGISTRATION_EVENT_STATUS=existing", second.stdout)

        rows = self.events()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["task_id"], "t_test123")
        self.assertEqual(rows[0]["kind"], "registered")
        payload = json.loads(rows[0]["payload"])
        self.assertEqual(payload["source"], "devkit-standard-flow")
        self.assertEqual(payload["status"], "blocked")

    def test_missing_task_fails_without_event(self) -> None:
        proc = self.run_helper("t_missing")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("REGISTRATION_EVENT_STATUS=failed", proc.stdout)
        self.assertIn("task not found", proc.stdout)
        self.assertEqual(self.events(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
