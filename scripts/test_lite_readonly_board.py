#!/usr/bin/env python3
"""Cold WAL/read-only board checks keep active tasks and failure guards intact."""
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
import os
import pwd
import sqlite3
import subprocess
import sys
import tempfile
import unittest

import lite_default_profile as migration


class ReadOnlyBoardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.db = self.root / 'kanban.db'
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('CREATE TABLE tasks(status TEXT)')
            conn.executemany('INSERT INTO tasks VALUES (?)', [('ready',), ('running',), ('review',)])
            conn.commit()

    def test_checkpointed_wal_snapshot_keeps_source_bytes_and_files(self):
        before = self.db.read_bytes(); names = sorted(p.name for p in self.root.iterdir())
        self.assertEqual(migration._cold_board_counts(self.db), [('review', 1), ('running', 1)])
        self.assertEqual(before, self.db.read_bytes())
        self.assertEqual(names, sorted(p.name for p in self.root.iterdir()))

    def test_actual_readonly_directory_and_nonroot_query(self):
        # chmod is effective for an unprivileged runner; drop root only in local tests.
        self.root.chmod(0o555); self.db.chmod(0o444)
        try:
            code = ('import sys;sys.path.insert(0,' + repr(str(Path(migration.__file__).parent)) + ');'
                    'from pathlib import Path;import lite_default_profile as m;'
                    'assert m.read_active_task_counts(Path(' + repr(str(self.db)) + ')) == [("review",1),("running",1)]')
            options = {'user': pwd.getpwnam('nobody').pw_uid} if os.geteuid() == 0 else {}
            result = subprocess.run([sys.executable, '-c', code], text=True, capture_output=True, timeout=10, **options)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['kanban.db'])
        finally:
            self.root.chmod(0o700); self.db.chmod(0o600)

    def test_active_guard_still_blocks_cold_snapshot(self):
        with patch.object(migration, 'read_active_task_counts', migration._cold_board_counts):
            with self.assertRaisesRegex(RuntimeError, 'Active Kanban tasks'):
                migration.active_tasks(self.root)

    def test_live_wal_commits_are_seen_by_normal_reader(self):
        with closing(sqlite3.connect(self.db)) as writer:
            writer.execute('PRAGMA wal_autocheckpoint=0')
            writer.execute("INSERT INTO tasks VALUES ('running')"); writer.commit()
            self.assertEqual(dict(migration.read_active_task_counts(self.db))['running'], 2)
            with self.assertRaisesRegex(RuntimeError, 'SQLite sidecars'):
                migration._cold_board_counts(self.db)

    def test_any_sidecar_refuses_cold_fallback(self):
        for suffix in ('-wal', '-shm', '-journal'):
            sidecar = Path(str(self.db) + suffix); sidecar.touch()
            try:
                with self.assertRaisesRegex(RuntimeError, 'SQLite sidecars'):
                    migration._cold_board_counts(self.db)
            finally:
                sidecar.unlink()

    def test_broken_sidecar_symlink_also_refuses(self):
        Path(str(self.db) + '-wal').symlink_to(self.root / 'missing')
        with self.assertRaisesRegex(RuntimeError, 'SQLite sidecars'):
            migration._cold_board_counts(self.db)

    def test_concurrent_change_refuses_snapshot(self):
        original = migration._cold_board_signature(self.db)
        with patch.object(migration, '_cold_board_signature', side_effect=[original, original[:-1] + (0,)]):
            with self.assertRaisesRegex(RuntimeError, 'changed during read-only snapshot'):
                migration._cold_board_counts(self.db)

    def test_oversize_is_bounded(self):
        with patch.object(migration, '_COLD_BOARD_LIMIT', 1):
            with self.assertRaisesRegex(RuntimeError, 'snapshot limit'):
                migration._cold_board_counts(self.db)

    def test_corruption_is_not_an_empty_board(self):
        self.db.write_bytes(b'broken database')
        with self.assertRaises(sqlite3.DatabaseError):
            migration.read_active_task_counts(self.db)

    def test_readonly_and_cantopen_use_only_the_guarded_fallback(self):
        for code in (sqlite3.SQLITE_READONLY, sqlite3.SQLITE_CANTOPEN):
            error = sqlite3.OperationalError('cold WAL cannot create sidecars')
            error.sqlite_errorcode = code
            with patch.object(migration.sqlite3, 'connect', side_effect=error):
                with patch.object(migration, '_cold_board_counts', return_value=[('running', 1)]) as fallback:
                    self.assertEqual(migration.read_active_task_counts(self.db), [('running', 1)])
                    fallback.assert_called_once_with(self.db)

    def test_missing_source_is_never_created_by_fallback(self):
        missing = self.root / 'missing.db'
        with self.assertRaises((OSError, sqlite3.Error)):
            migration.read_active_task_counts(missing)
        self.assertFalse(missing.exists())

    def test_busy_error_does_not_use_fallback(self):
        with patch.object(migration.sqlite3, 'connect', side_effect=sqlite3.OperationalError('database is locked')):
            with patch.object(migration, '_cold_board_counts') as fallback:
                with self.assertRaises(sqlite3.OperationalError):
                    migration.read_active_task_counts(self.db)
                fallback.assert_not_called()


if __name__ == '__main__':
    unittest.main()
