#!/usr/bin/env python3
"""Synthetic CI data only. Called through stdin in a newly created isolated volume."""
from pathlib import Path
import hashlib
import json
import os
import pwd
import sqlite3
import sys
ROOT=Path('/opt/data')
MARKER=ROOT/'lite-ci-fixture.json'

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def seed(kind):
    assert not MARKER.exists(), 'Do not overwrite an existing fixture'
    ROOT.mkdir(exist_ok=True)
    if kind=='fresh': return
    config={'custom_lite_ci': {'preserve': True}, 'skills': {'external_dirs':['/opt/custom-skills/coder'], 'auto_load':[]},
            'kanban':{'dispatch_in_gateway':True,'notify_in_gateway':False}}
    (ROOT/'config.yaml').write_text(json.dumps(config))  # JSON is valid YAML
    files={}
    for relative,content in {
        'auth.json':'{"lite_ci_only":true}',
        'memories/lite-ci.txt':'memory must survive',
        'sessions/lite-ci.txt':'session must survive',
        'profiles/coder/SOUL.md':'# archived coder fixture',
        'profiles/coder/auth.json':'{"preserved_fixture":"coder"}',
        'profiles/orchestrator/SOUL.md':'# archived orchestrator fixture',
        'profiles/reviewer/SOUL.md':'# archived reviewer fixture',
    }.items():
        p=ROOT/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
        files[relative]=digest(p)
    if kind=='active':
        with sqlite3.connect(ROOT/'kanban.db') as db:
            db.execute('CREATE TABLE tasks (id TEXT, status TEXT)')
            db.execute("INSERT INTO tasks VALUES ('fixture-running','running')")
    else:
        # Use the installed upstream schema, never emulate a production schema.
        from hermes_cli import kanban_db
        conn=kanban_db.connect()
        db_path=conn.execute('PRAGMA database_list').fetchone()[2]
        conn.execute('CREATE TABLE devkit_ci_preserved (id INTEGER PRIMARY KEY, value TEXT)')
        conn.execute("INSERT INTO devkit_ci_preserved VALUES (1,'keep-board-record')")
        conn.commit(); conn.close()
        config['ci_db_path']=db_path
    if kind=='collision':
        path=ROOT/'devkit-lite/legacy-profiles/coder';path.mkdir(parents=True)
        (path/'keep.txt').write_text('do not replace archive')
    MARKER.write_text(json.dumps({'kind':kind,'files':files,'database':config.get('ci_db_path')}))
    user=pwd.getpwnam('hermes')
    for base,dirs,names in os.walk(ROOT):
        os.chown(base,user.pw_uid,user.pw_gid)
        for name in names: os.chown(Path(base)/name,user.pw_uid,user.pw_gid)

def verify(success):
    if not MARKER.exists():
        assert success
        return
    m=json.loads(MARKER.read_text())
    for relative,sha in m['files'].items():
        p=ROOT/relative
        if success and relative.startswith('profiles/'):
            p=ROOT/'devkit-lite/legacy-profiles'/relative[len('profiles/'):]
        assert p.is_file() and digest(p)==sha,relative
    if success:
        import hermes_yaml as yaml
        cfg=yaml.safe_load((ROOT/'config.yaml').read_text())
        assert cfg['custom_lite_ci']=={'preserve':True}
        assert cfg['kanban']['dispatch_in_gateway'] is False
        assert all(not (ROOT/'profiles'/role).exists() for role in ('coder','orchestrator','reviewer'))
        with sqlite3.connect('file:'+m['database']+'?mode=ro',uri=True) as db:
            assert db.execute('SELECT value FROM devkit_ci_preserved WHERE id=1').fetchone()[0]=='keep-board-record'
    else:
        assert not (ROOT/'devkit-lite/migration-state.json').exists()
    print('[PASS] Fixture data and archive boundary:',m['kind'])

if __name__=='__main__':
    if sys.argv[1]=='seed': seed(sys.argv[2])
    else: verify(sys.argv[1]=='verify')
