#!/usr/bin/env python3
"""Regression tests for integration assertions; no Docker or user data required."""
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import copy
import json
import sqlite3
import sys
import tempfile
import unittest

import devkit_image_fixture as fixture
from smoke_devkit_image import assert_mounts_preserved, assert_plan_result, mount_snapshot


class MountTests(unittest.TestCase):
    def setUp(self):
        self.mounts = [
            {'Type': 'volume', 'Name': 'ci-data', 'Source': '/volumes/ci-data/_data',
             'Destination': '/opt/data', 'Driver': 'local', 'Mode': '', 'RW': True, 'Propagation': ''},
            {'Type': 'bind', 'Source': '/ci/shared', 'Destination': '/opt/data/shared',
             'Mode': '', 'RW': False, 'Propagation': 'rprivate'},
        ]

    def test_mount_and_object_key_order_are_irrelevant(self):
        after = [dict(reversed(list(mount.items()))) for mount in reversed(self.mounts)]
        assert_mounts_preserved(json.dumps(self.mounts), json.dumps(after, indent=2))

    def test_real_mount_changes_are_rejected(self):
        for key, value in [('Source', '/another-volume'), ('Destination', '/other'),
                           ('RW', False), ('Name', 'different-volume'), ('Type', 'bind'),
                           ('Driver', 'other'), ('Mode', 'ro'), ('Propagation', 'rshared')]:
            with self.subTest(field=key):
                after = copy.deepcopy(self.mounts); after[0][key] = value
                with self.assertRaisesRegex(AssertionError, 'Docker mounts changed'):
                    assert_mounts_preserved(json.dumps(self.mounts), json.dumps(after))

    def test_added_and_removed_mounts_are_rejected(self):
        for after in (self.mounts[:1], self.mounts + [{'Destination': '/extra', 'RW': True}]):
            with self.assertRaises(AssertionError):
                assert_mounts_preserved(json.dumps(self.mounts), json.dumps(after))

    def test_malformed_or_duplicate_destinations_are_rejected(self):
        for mounts in ({}, [None], [{}], [{'Destination': ''}], self.mounts + [self.mounts[0]]):
            with self.subTest(mounts=mounts), self.assertRaises(ValueError):
                mount_snapshot(json.dumps(mounts))


class PlanTests(unittest.TestCase):
    def test_expected_plan_outcomes(self):
        for kind, code, error in [('legacy', 0, ''), ('previous-default', 0, ''), ('active', 1, '[BLOCKED] Active Kanban tasks'),
                                  ('collision', 1, '[BLOCKED] Active/archive profile conflict: coder'),
                                  ('old-collision', 1, '[BLOCKED] Active/archive profile conflict: coder'),
                                  ('interrupted', 1, '[BLOCKED] Interrupted migration')]:
            assert_plan_result(kind, SimpleNamespace(returncode=code, stdout='', stderr=error))

    def test_unrelated_failure_or_unexpected_success_is_not_a_pass(self):
        for kind, code in [('legacy', 1), ('previous-default', 1), ('interrupted', 0), ('interrupted', 1), ('old-collision', 0), ('old-collision', 1), ('active', 0), ('active', 1), ('collision', 0), ('collision', 1)]:
            with self.subTest(kind=kind, code=code), self.assertRaises(AssertionError):
                assert_plan_result(kind, SimpleNamespace(returncode=code, stdout='', stderr='Permission denied'))


class ConfigBaselineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.path = self.root / 'config.yaml'
        self.original = {'model': {'provider': 'keep'}, 'skills': {'auto_load': ['dev-implement-plan']}}
        self.path.write_text(fixture.yaml.safe_dump(self.original))

    def normalize(self, content, path=None):
        migrate = Mock(side_effect=lambda **kwargs: self.path.write_text(fixture.yaml.safe_dump(content)))
        module = SimpleNamespace(get_config_path=lambda: path or self.path, migrate_config=migrate)
        with patch.dict(sys.modules, {'hermes_cli.config': module}), patch.object(fixture, 'ROOT', self.root):
            result = fixture.upstream_config_baseline()
        migrate.assert_called_once_with(interactive=False, quiet=True)
        return result

    def test_baseline_includes_supported_upstream_version_stamp(self):
        normalized = dict(self.original, _config_version=51)
        self.assertEqual(self.normalize(normalized), normalized)

    def test_normalization_does_not_hide_user_setting_changes(self):
        changed = dict(self.original, model={'provider': 'wrong'})
        with self.assertRaisesRegex(AssertionError, 'Fixture setting changed'):
            self.normalize(changed)

    def test_unexpected_config_root_is_refused_before_migration(self):
        before = self.path.read_bytes()
        with self.assertRaisesRegex(AssertionError, 'Unexpected fixture config root'):
            self.normalize({}, self.root / 'elsewhere.yaml')
        self.assertEqual(before, self.path.read_bytes())


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        with closing(sqlite3.connect(self.root / 'state.db')) as conn:
            conn.execute('CREATE TABLE keep(value TEXT)')
            conn.executemany('INSERT INTO keep VALUES (?)', fixture.SESSION_ROWS); conn.commit()

    def test_schema_maintenance_is_not_data_loss(self):
        before = (self.root / 'state.db').read_bytes()
        with closing(sqlite3.connect(self.root / 'state.db')) as conn:
            conn.execute('CREATE TABLE runtime_metadata(version INTEGER)'); conn.commit()
        self.assertNotEqual(before, (self.root / 'state.db').read_bytes())
        fixture.verify_session_data(self.root)

    def test_lost_or_changed_rows_fail(self):
        for sql in ('UPDATE keep SET value="changed"', 'DELETE FROM keep'):
            with closing(sqlite3.connect(self.root / 'state.db')) as conn:
                conn.execute(sql); conn.commit()
            with self.assertRaises(AssertionError):
                fixture.verify_session_data(self.root)

    def test_wal_committed_changes_are_not_ignored(self):
        with closing(sqlite3.connect(self.root / 'state.db')) as conn:
            conn.execute('PRAGMA journal_mode=WAL'); conn.execute('PRAGMA wal_autocheckpoint=0')
            conn.execute('UPDATE keep SET value="changed-in-wal"'); conn.commit()
            with self.assertRaises(AssertionError):
                fixture.verify_session_data(self.root)

    def test_missing_database_is_not_created(self):
        missing = self.root / 'missing'; missing.mkdir()
        with self.assertRaises(sqlite3.OperationalError):
            fixture.verify_session_data(missing)
        self.assertFalse((missing / 'state.db').exists())

    def test_corrupt_database_fails(self):
        (self.root / 'state.db').write_bytes(b'not a database')
        with self.assertRaises(sqlite3.DatabaseError):
            fixture.verify_session_data(self.root)

    def test_blocked_fixture_checks_the_real_journal(self):
        (self.root / 'profiles/coder').mkdir(parents=True)
        (self.root / 'profiles/coder/SOUL.md').write_text('preserved')
        (self.root / 'config.yaml').write_text('{}')
        marker = self.root / 'devkit-ci-fixture.json'
        marker.write_text(json.dumps({'hashes': {}, 'original': {}}))
        with patch.object(fixture, 'ROOT', self.root), patch.object(fixture, 'MARKER', marker):
            fixture.verify(blocked=True)
            (self.root / 'devkit-state').mkdir()
            (self.root / 'devkit-state/migration-state.json').write_text('{"phase":"applied"}')
            with self.assertRaisesRegex(AssertionError, 'Blocked migration wrote its journal'):
                fixture.verify(blocked=True)


if __name__ == '__main__':
    unittest.main()
