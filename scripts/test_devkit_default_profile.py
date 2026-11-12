#!/usr/bin/env python3
"""Filesystem regressions for safe DevKit cutover; no live credentials or Docker."""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import devkit_default_profile as m

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
            path=self.root/'devkit-state/legacy-profiles'/role
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
        (self.root/'devkit-state/legacy-profiles/coder').mkdir(parents=True)
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
        for rel in ('devkit-state','profiles/coder','config.yaml'):
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
        file=self.root/'devkit-state/profile-state.json'
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
        journal=json.loads((self.root/'devkit-state/migration-state.json').read_text())
        self.assertEqual(journal['phase'],'rolled-back')
        self.assertEqual(m.apply(self.root)['status'],'applied')

    def test_unfinished_journal_needs_explicit_recovery(self):
        p=self.root/'devkit-state/migration-state.json';p.parent.mkdir()
        p.write_text('{"schema":1,"phase":"prepared"}')
        with self.assertRaisesRegex(ValueError,'Interrupted'):m.apply(self.root)

    def test_custom_skill_root_and_new_volume(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            self.assertEqual(m.apply(root,skills_root='/skills')['status'],'applied')
            self.assertTrue(m.status(root,'/skills')['ready'])
            self.assertEqual(m.mapping(root/'config.yaml')['skills']['external_dirs'],['/skills/shared','/skills/core'])

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

    def s6_runtime(self, root, shared_scandir=False):
        helper=types.ModuleType('devkit_s6_runtime')
        helper.STATIC_SCANDIR=root/'service'
        dynamic=helper.STATIC_SCANDIR if shared_scandir else root/'hermes-service'
        helper.gateway_scandir=lambda:dynamic
        return helper

    def test_live_gateway_in_dynamic_or_legacy_tree_blocks_before_migration(self):
        for legacy in (False,True):
            with self.subTest(legacy=legacy),tempfile.TemporaryDirectory() as temp:
                helper=self.s6_runtime(Path(temp))
                scandir=helper.STATIC_SCANDIR if legacy else helper.gateway_scandir()
                slot=scandir/'gateway-default';slot.mkdir(parents=True)
                run=slot/'run';run.write_bytes(b'owned service script')
                before=self.snapshot()
                args=['devkit_default_profile.py','apply','--boot','--data-root',str(self.root)]
                with patch.dict(sys.modules,{'devkit_s6_runtime':helper}), \
                     patch.object(m.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'true\n','')) as probe, \
                     patch.object(sys,'argv',args),patch('sys.stderr',new_callable=io.StringIO) as stderr:
                    self.assertEqual(m.main(),1)
                self.assertIn('Live gateway detected',stderr.getvalue())
                probe.assert_called_once_with(['/command/s6-svstat','-o','up',str(slot)],capture_output=True,text=True,timeout=5)
                self.assertEqual(self.snapshot(),before)
                self.assertEqual(run.read_bytes(),b'owned service script')

    def test_quiet_gateway_trees_and_unrelated_files_remain_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);helper=self.s6_runtime(root)
            slots=[helper.gateway_scandir()/'gateway-default',helper.STATIC_SCANDIR/'gateway-legacy']
            for slot in slots:
                slot.mkdir(parents=True);(slot/'run').write_bytes(b'owned service script')
            other=helper.STATIC_SCANDIR/'devkit-notifier';other.mkdir()
            (other/'run').write_bytes(b'owned notifier script')
            (root/'notes.txt').write_bytes(b'keep unrelated file')
            before={p.relative_to(root):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            with patch.dict(sys.modules,{'devkit_s6_runtime':helper}), \
                 patch.object(m.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'false\n','')) as probe:
                m.assert_boot_quiet()
            self.assertEqual([call.args[0][-1] for call in probe.call_args_list],[str(slot) for slot in slots])
            self.assertEqual({p.relative_to(root):p.read_bytes() for p in root.rglob('*') if p.is_file()},before)

    def test_legacy_shared_scandir_is_checked_once(self):
        with tempfile.TemporaryDirectory() as temp:
            helper=self.s6_runtime(Path(temp),shared_scandir=True)
            slot=helper.STATIC_SCANDIR/'gateway-default';slot.mkdir(parents=True)
            with patch.dict(sys.modules,{'devkit_s6_runtime':helper}), \
                 patch.object(m.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'false\n','')) as probe:
                m.assert_boot_quiet()
            self.assertEqual(probe.call_count,1)

    def test_unresolved_gateway_scandir_blocks_without_probing_or_writes(self):
        helper=self.s6_runtime(self.root/'runtime');before=self.snapshot()
        with patch.dict(sys.modules,{'devkit_s6_runtime':helper}), \
             patch.object(helper,'gateway_scandir',side_effect=RuntimeError('Unable to resolve gateway scandir')), \
             patch.object(m.subprocess,'run') as probe:
            with self.assertRaisesRegex(RuntimeError,'Unable to resolve gateway scandir'):
                m.assert_boot_quiet()
        probe.assert_not_called()
        self.assertEqual(self.snapshot(),before)

    def test_plan_and_status_from_stdin_do_not_require_s6_helper(self):
        before=self.snapshot();source=Path(m.__file__).read_text()
        for action,expected in (('plan',0),('status',1)):
            with self.subTest(action=action):
                proc=subprocess.run([sys.executable,'-I','-',action,'--data-root',str(self.root)],
                                    input=source,cwd=self.root,capture_output=True,text=True)
                self.assertEqual(proc.returncode,expected,proc.stderr)
                self.assertEqual(proc.stderr,'')
                result=json.loads(proc.stdout)
                if action=='plan':self.assertEqual(result['status'],'planned')
                else:self.assertFalse(result['ready'])
                self.assertEqual(self.snapshot(),before)

    def test_status_reports_actual_configuration_not_only_marker(self):
        self.assertFalse(m.status(self.root)['ready'])
        m.apply(self.root)
        self.assertTrue(m.status(self.root)['ready'])
        self.save(self.doc)
        self.assertFalse(m.status(self.root)['ready'])

if __name__=='__main__':unittest.main(verbosity=2)
