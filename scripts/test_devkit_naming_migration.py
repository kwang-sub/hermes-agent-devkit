#!/usr/bin/env python3
"""Frozen pre-rename configuration and state fixtures; never user data."""
from __future__ import annotations
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import devkit_default_profile as m


class NamingMigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        # Deliberately literal OLD values, not generated with desired().
        self.doc = {
            'model': {'provider': 'fixture', 'custom': 7},
            'memory': {'enabled': True}, 'user-setting': ['preserve'],
            'skills': {'external_dirs': ['/personal/lite', '/opt/custom-skills/shared',
                                         '/opt/custom-skills/lite'],
                       'auto_load': ['user-skill', 'dev-lite-session'], 'user-setting': True},
            'toolsets': ['terminal', 'hermes-cli', 'kanban'],
            'kanban': {'dispatch_in_gateway': False, 'custom': 'preserve'}}
        self.config = self.root / 'config.yaml'
        self.config.write_text(m.yaml.safe_dump(self.doc))
        self.old = self.root / 'devkit-lite'
        self.old.mkdir()
        self.old_journal = self.old / 'migration-state.json'
        self.old_journal.write_text(json.dumps({'schema': 1, 'phase': 'applied',
            'backup': 'devkit-lite/backups/old', 'moved_roles': []}))
        self.backup = self.old / 'backups/old/config.yaml'
        self.backup.parent.mkdir(parents=True)
        self.backup.write_bytes(b'old exact backup bytes\r\n')
        for name in ('auth.json', 'memories/MEMORY.md', 'sessions/history.txt',
                     'skills/my-note/SKILL.md'):
            p = self.root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(('opaque fixture: ' + name).encode())

    def snapshot(self):
        return {str(p.relative_to(self.root)): (hashlib.sha256(p.read_bytes()).hexdigest(),
                    p.stat().st_mtime_ns, p.stat().st_mode)
                for p in self.root.rglob('*') if p.is_file() and not p.is_symlink()}

    def test_previous_default_maps_managed_names_and_preserves_user_settings(self):
        original = self.config.read_bytes()
        old = self.snapshot()
        result = m.apply(self.root)
        current = m.mapping(self.config)
        self.assertEqual(current['skills']['external_dirs'],
            ['/personal/lite', '/opt/custom-skills/shared', '/opt/custom-skills/core'])
        self.assertEqual(current['skills']['auto_load'], ['user-skill', 'dev-session'])
        self.assertTrue(current['skills']['user-setting'])
        for key in ('model', 'memory', 'user-setting', 'toolsets', 'kanban'):
            self.assertEqual(current[key], self.doc[key])
        for name, value in old.items():
            if name != 'config.yaml':
                self.assertEqual(self.snapshot()[name], value)
        self.assertTrue(result['backup'].startswith('devkit-state/backups/'))
        self.assertEqual((self.root / result['backup'] / 'config.yaml').read_bytes(), original)
        self.assertTrue(m.status(self.root)['ready'])

    def test_old_completed_journal_and_backup_are_not_rewritten_or_relocated(self):
        before = self.snapshot()
        m.apply(self.root)
        after = self.snapshot()
        for name in before:
            if name.startswith('devkit-lite/'):
                self.assertEqual(before[name], after[name])
        self.assertEqual(json.loads(self.old_journal.read_text())['backup'],
                         'devkit-lite/backups/old')

    def test_plan_and_status_do_not_create_locks_or_new_state(self):
        before = self.snapshot()
        self.assertEqual(m.apply(self.root, dry_run=True)['status'], 'planned')
        self.assertFalse(m.status(self.root)['ready'])
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.root / 'devkit-state').exists())
        self.assertFalse((self.old / 'migration.lock').exists())

    def test_second_apply_preserves_bytes_and_timestamps(self):
        m.apply(self.root)
        before = self.snapshot()
        self.assertEqual(m.apply(self.root)['status'], 'unchanged')
        self.assertEqual(before, self.snapshot())

    def test_fresh_install_never_creates_old_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            m.apply(root)
            self.assertFalse((root / 'devkit-lite').exists())
            self.assertTrue((root / 'devkit-state/migration-state.json').is_file())
            self.assertEqual(m.mapping(root / 'config.yaml')['skills']['auto_load'], ['dev-session'])

    def test_aliases_deduplicate_without_removing_user_autoloads(self):
        doc = copy.deepcopy(self.doc)
        doc['skills']['auto_load'] = ['mine', 'dev-lite-session', 'dev-session',
                                      'dev-lite-review', 'dev-review', 'dev-implement-plan']
        result = m.desired(doc, '/opt/custom-skills')
        self.assertEqual(result['skills']['auto_load'], ['mine', 'dev-session', 'dev-review'])
        self.assertEqual(m.desired(result, '/opt/custom-skills'), result)

    def test_custom_root_nested_managed_path_and_unrelated_paths(self):
        doc = copy.deepcopy(self.doc)
        doc['skills']['external_dirs'] = ['/skills/lite/', '/skills/lite/dev-lite-review',
            '/skills/lite-extra', '/personal/lite', '/opt/custom-skills/lite', '/skills/core']
        dirs = m.desired(doc, '/skills')['skills']['external_dirs']
        self.assertEqual(dirs, ['/skills/core', '/skills/core/dev-review', '/skills/lite-extra',
            '/personal/lite', '/opt/custom-skills/core', '/skills/shared'])

    def test_old_prepared_journal_blocks_even_with_new_applied_journal(self):
        self.old_journal.write_text('{"schema":1,"phase":"prepared"}')
        new = self.root / 'devkit-state/migration-state.json'
        new.parent.mkdir()
        new.write_text('{"schema":1,"phase":"applied"}')
        before = self.snapshot()
        for action in (lambda: m.apply(self.root), lambda: m.apply(self.root, dry_run=True),
                       lambda: m.status(self.root)):
            with self.assertRaisesRegex(ValueError, 'Interrupted migration'):
                action()
            self.assertEqual(before, self.snapshot())

    def test_unknown_or_malformed_old_journals_fail_before_writing(self):
        for content in ('[]', 'null', '{}', '{"schema":99,"phase":"applied"}',
                        '{"schema":1,"phase":"unknown"}', 'invalid'):
            with self.subTest(content=content):
                self.old_journal.write_text(content)
                before = self.snapshot()
                with self.assertRaises((ValueError, json.JSONDecodeError)):
                    m.apply(self.root)
                self.assertEqual(before, self.snapshot())

    def test_new_prepared_journal_also_blocks(self):
        path = self.root / 'devkit-state/migration-state.json'
        path.parent.mkdir()
        path.write_text('{"schema":1,"phase":"prepared"}')
        with self.assertRaisesRegex(ValueError, 'Interrupted'):
            m.apply(self.root)

    def test_rolled_back_legacy_journal_allows_retry(self):
        self.old_journal.write_text('{"schema":1,"phase":"rolled-back"}')
        self.assertEqual(m.apply(self.root)['status'], 'applied')
        self.assertEqual(json.loads(self.old_journal.read_text())['phase'], 'rolled-back')

    def test_existing_old_profile_archive_remains_at_original_path(self):
        p = self.old / 'legacy-profiles/coder'
        p.mkdir(parents=True)
        (p / 'memory.md').write_bytes(b'old role memory')
        m.apply(self.root)
        self.assertEqual((p / 'memory.md').read_bytes(), b'old role memory')
        self.assertFalse((self.root / 'devkit-state/legacy-profiles/coder').exists())

    def test_active_role_and_old_archive_conflict_before_any_write(self):
        (self.root / 'profiles/coder').mkdir(parents=True)
        (self.old / 'legacy-profiles/coder').mkdir(parents=True)
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'Active/archive profile conflict'):
            m.apply(self.root)
        self.assertEqual(before, self.snapshot())

    def test_both_old_and_new_archives_are_not_silently_merged(self):
        for name in ('devkit-lite', 'devkit-state'):
            (self.root / name / 'legacy-profiles/coder').mkdir(parents=True, exist_ok=True)
        with self.assertRaisesRegex(ValueError, 'Active/archive profile conflict'):
            m.apply(self.root)

    def test_old_overlay_versions_are_verified_then_archived(self):
        for schema in (1, 2):
            with self.subTest(schema=schema), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / 'config.yaml').write_text(m.yaml.safe_dump(self.doc))
                marker = root / 'devkit-lite/profile-state.json'
                marker.parent.mkdir()
                value = m.fields(self.doc)
                marker.write_text(json.dumps({'schema': schema, 'phase': 'applied',
                                              'before': value, 'applied': value}))
                original = marker.read_bytes()
                result = m.apply(root)
                self.assertFalse(marker.exists())
                self.assertEqual((root / result['backup'] / 'profile-state.json').read_bytes(), original)
                self.assertIn('dev-session', m.mapping(root / 'config.yaml')['skills']['auto_load'])

    def test_duplicate_overlay_markers_fail_closed(self):
        for name in ('devkit-lite', 'devkit-state'):
            p = self.root / name / 'profile-state.json'
            p.parent.mkdir(exist_ok=True)
            p.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            m.apply(self.root)

    def test_user_edited_old_overlay_is_not_overwritten(self):
        p = self.old / 'profile-state.json'
        p.write_text(json.dumps({'schema': 2, 'phase': 'applied', 'before': {}, 'applied': {}}))
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'managed fields changed'):
            m.apply(self.root)
        self.assertEqual(before, self.snapshot())

    def test_legacy_lock_blocks_new_migrator(self):
        with (self.old / 'migration.lock').open('w') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            before = self.config.read_bytes()
            with self.assertRaises(BlockingIOError):
                m.apply(self.root)
            self.assertEqual(self.config.read_bytes(), before)
            self.assertFalse((self.root / 'devkit-state/migration-state.json').exists())

    def test_new_lock_blocks_same_version_migrator(self):
        folder = self.root / 'devkit-state'
        folder.mkdir()
        with (folder / 'migration.lock').open('w') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                m.apply(self.root)

    def test_legacy_journal_symlink_is_rejected(self):
        self.old_journal.unlink()
        self.old_journal.symlink_to(self.backup)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            m.apply(self.root)

    def test_non_directory_state_root_is_rejected(self):
        (self.root / 'devkit-state').write_text('not a directory')
        with self.assertRaisesRegex(ValueError, 'must be a directory'):
            m.apply(self.root)

    def test_fifo_lock_does_not_block_or_authorize_writes(self):
        os.mkfifo(self.old / 'migration.lock')
        with self.assertRaisesRegex(ValueError, 'regular file'):
            m.apply(self.root)

    def test_config_readback_failure_rolls_back_name_change(self):
        before = self.config.read_bytes()
        original_mapping = m.mapping
        seen_new = False
        def altered_readback(path):
            nonlocal seen_new
            result = original_mapping(path)
            if 'dev-session' in result.get('skills', {}).get('auto_load', []) and not seen_new:
                seen_new = True
                return {}
            return result
        with patch.object(m, 'mapping', side_effect=altered_readback):
            with self.assertRaisesRegex(RuntimeError, 'read-back'):
                m.apply(self.root)
        self.assertEqual(self.config.read_bytes(), before)
        self.assertEqual(json.loads((self.root / 'devkit-state/migration-state.json').read_text())['phase'], 'rolled-back')
        self.assertEqual(m.apply(self.root)['status'], 'applied')


if __name__ == '__main__':
    unittest.main(verbosity=2)
