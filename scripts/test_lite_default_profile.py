#!/usr/bin/env python3
"""Filesystem regressions for safe Lite cutover; no live credentials or Docker."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lite_default_profile as m

class MigrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = self.root / 'config.yaml'
        self.doc = {'model': {'provider': 'keep', 'custom': {'value': 19}},
                    'memory': {'enabled': True}, 'unknown-setting': ['preserve'],
                    'skills': {'external_dirs': ['/opt/custom-skills/coder','/personal'],
                               'auto_load': ['custom-skill','dev-implement-plan']},
                    'toolsets': ['terminal'], 'kanban': {'other': 'keep'}}
        self.save(self.doc)
        for role in m.ROLES:
            home = self.root/'profiles'/role
            home.mkdir(parents=True)
            (home/'oauth.json').write_bytes(b'opaque-credential-fixture')
            (home/'memory.md').write_bytes(b'private-memory-fixture')
        for name in ('auth.json','sessions.db','memories.md'):
            (self.root/name).write_bytes(b'opaque-'+name.encode())

    def save(self, doc):
        self.config.write_text(m.yaml.safe_dump(doc))

    def snapshot(self):
        return {str(p.relative_to(self.root)):hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.root.rglob('*') if p.is_file() and not p.is_symlink()}

    def test_plan_is_byte_for_byte_read_only(self):
        before=self.snapshot()
        result=m.apply(self.root,dry_run=True)
        self.assertEqual(result['status'],'planned')
        self.assertEqual(self.snapshot(),before)

    def test_cutover_preserves_data_and_unknown_config(self):
        result=m.apply(self.root)
        self.assertEqual(result['status'],'applied')
        current=m.mapping(self.config)
        for key in ('model','memory','unknown-setting'):
            self.assertEqual(current[key],self.doc[key])
        self.assertEqual(current['kanban'],{'other':'keep','dispatch_in_gateway':False})
        self.assertIn('/personal',current['skills']['external_dirs'])
        self.assertIn('custom-skill',current['skills']['auto_load'])
        self.assertNotIn('dev-implement-plan',current['skills']['auto_load'])
        for role in m.ROLES:
            path=self.root/'devkit-lite/legacy-profiles'/role
            self.assertEqual((path/'oauth.json').read_bytes(),b'opaque-credential-fixture')
            self.assertEqual((path/'memory.md').read_bytes(),b'private-memory-fixture')
            self.assertFalse((self.root/'profiles'/role).exists())
        for name in ('auth.json','sessions.db','memories.md'):
            self.assertEqual((self.root/name).read_bytes(),b'opaque-'+name.encode())
        self.assertTrue(m.status(self.root)['ready'])

    def test_second_apply_does_not_rewrite_anything(self):
        m.apply(self.root)
        before=self.snapshot()
        self.assertEqual(m.apply(self.root)['status'],'unchanged')
        self.assertEqual(self.snapshot(),before)

    def test_backups_are_private_and_exact(self):
        original=self.config.read_bytes()
        result=m.apply(self.root)
        backup=self.root/result['backup']/'config.yaml'
        self.assertEqual(backup.read_bytes(),original)
        self.assertEqual(backup.stat().st_mode & 0o777,0o600)

    def test_archive_collision_precedes_every_write(self):
        (self.root/'devkit-lite/legacy-profiles/coder').mkdir(parents=True)
        before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'conflict'):
            m.apply(self.root)
        self.assertEqual(self.snapshot(),before)

    def make_db(self, relative, status):
        db=self.root/relative;db.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(db) as conn:
            conn.execute('CREATE TABLE tasks (id TEXT, status TEXT)')
            conn.execute('INSERT INTO tasks VALUES (?,?)',('fixture',status))
        return db

    def test_running_and_review_block_all_known_locations(self):
        for dbpath in ('kanban.db','kanban/boards/demo/kanban.db','profiles/coder/kanban.db',
                       'profiles/reviewer/kanban/boards/demo/kanban.db'):
            with self.subTest(dbpath=dbpath):
                db=self.make_db(dbpath,'running')
                before=self.snapshot()
                with self.assertRaisesRegex(RuntimeError,'Active Kanban'):
                    m.apply(self.root)
                self.assertEqual(self.snapshot(),before)
                db.unlink()
        self.make_db('kanban.db','review')
        with self.assertRaises(RuntimeError): m.apply(self.root)

    def test_completed_kanban_is_never_rewritten(self):
        db=self.make_db('kanban.db','done');original=db.read_bytes()
        m.apply(self.root)
        self.assertEqual(db.read_bytes(),original)

    def test_unknown_database_schema_blocks_before_writes(self):
        with sqlite3.connect(self.root/'kanban.db') as db:
            db.execute('CREATE TABLE other (x TEXT)')
        before=self.snapshot()
        with self.assertRaises(sqlite3.Error):m.apply(self.root)
        self.assertEqual(before,self.snapshot())

    def test_symlink_ancestors_are_rejected(self):
        for rel in ('devkit-lite','profiles/coder','config.yaml'):
            with self.subTest(rel=rel),tempfile.TemporaryDirectory() as out:
                target=self.root/rel
                if target.is_dir():
                    target.rename(self.root/(target.name+'-saved'))
                elif target.exists():target.unlink()
                target.symlink_to(out,target_is_directory=True)
                try:
                    with self.assertRaises(ValueError):m.apply(self.root)
                finally:
                    target.unlink()
                    saved=self.root/(target.name+'-saved')
                    if saved.exists():saved.rename(target)
                    if rel=='config.yaml':self.save(self.doc)

    def marker(self, schema=2, phase='applied'):
        values=m.fields(self.doc)
        state={'schema':schema,'phase':phase,'before':values,'applied':values}
        file=self.root/'devkit-lite/profile-state.json'
        file.parent.mkdir(parents=True,exist_ok=True)
        file.write_text(json.dumps(state))
        return file

    def test_legacy_v1_and_v2_retire_without_restoring_stale_config(self):
        for schema in (1,2):
            with self.subTest(schema=schema):
                marker=self.marker(schema)
                original=marker.read_bytes()
                result=m.apply(self.root)
                self.assertEqual((self.root/result['backup']/'profile-state.json').read_bytes(),original)
                self.assertFalse(marker.exists())
                self.assertEqual(m.mapping(self.config)['model'],self.doc['model'])
                # Reset only this isolated test fixture for the second legacy schema.
                self.save(self.doc)

    def test_modified_overlay_fields_are_not_overwritten(self):
        self.marker()
        doc=m.mapping(self.config);doc['skills']['external_dirs'].append('/changed')
        self.save(doc);before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'managed fields changed'):m.apply(self.root)
        self.assertEqual(before,self.snapshot())

    def test_unknown_or_malformed_overlay_rejected(self):
        for schema,phase in ((99,'applied'),(2,'unknown')):
            self.marker(schema,phase)
            with self.assertRaises(ValueError):m.apply(self.root)

    def test_archive_failure_rolls_back_earlier_moves(self):
        old=self.config.read_bytes();real=m.os.rename;calls=0
        def fail_second(src,dst):
            nonlocal calls
            calls+=1
            if calls==2:raise OSError('injected failure')
            return real(src,dst)
        with patch.object(m.os,'rename',side_effect=fail_second):
            with self.assertRaises(OSError):m.apply(self.root)
        self.assertEqual(self.config.read_bytes(),old)
        for role in m.ROLES:self.assertTrue((self.root/'profiles'/role/'oauth.json').exists())
        journal=json.loads((self.root/'devkit-lite/migration-state.json').read_text())
        self.assertEqual(journal['phase'],'rolled-back')
        self.assertEqual(m.apply(self.root)['status'],'applied')

    def test_unfinished_journal_needs_explicit_recovery(self):
        p=self.root/'devkit-lite/migration-state.json';p.parent.mkdir()
        p.write_text('{"schema":1,"phase":"prepared"}')
        with self.assertRaisesRegex(ValueError,'Interrupted'):m.apply(self.root)

    def test_custom_skill_root_and_new_volume(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            self.assertEqual(m.apply(root,skills_root='/skills')['status'],'applied')
            self.assertTrue(m.status(root,'/skills')['ready'])
            self.assertEqual(m.mapping(root/'config.yaml')['skills']['external_dirs'],['/skills/shared','/skills/lite'])

    def test_invalid_yaml_and_types_block_without_writes(self):
        for value in ('invalid: [', '[]', 'skills: x', 'toolsets: x', 'kanban: x'):
            self.config.write_text(value);before=self.snapshot()
            with self.assertRaises((ValueError,m.yaml.YAMLError)):m.apply(self.root)
            self.assertEqual(before,self.snapshot())

    def test_apply_cli_cannot_change_a_running_install(self):
        before=self.snapshot()
        proc=subprocess.run([sys.executable,str(Path(m.__file__)),'apply','--data-root',str(self.root)],capture_output=True,text=True)
        self.assertEqual(proc.returncode,1)
        self.assertIn('boot',proc.stderr)
        self.assertEqual(before,self.snapshot())

    def test_status_reports_actual_configuration_not_only_marker(self):
        self.assertFalse(m.status(self.root)['ready'])
        m.apply(self.root)
        self.assertTrue(m.status(self.root)['ready'])
        self.save(self.doc)
        self.assertFalse(m.status(self.root)['ready'])

if __name__=='__main__':unittest.main(verbosity=2)
