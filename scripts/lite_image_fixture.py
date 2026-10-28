"""Executed ONLY inside disposable integration containers by smoke_lite_image.py."""
from pathlib import Path
from contextlib import closing
import hashlib
import json
import os
import pwd
import sqlite3
import sys
try: import hermes_yaml as yaml
except ImportError: import yaml
ROOT=Path('/opt/data')
MARKER=ROOT/'devkit-ci-fixture.json'
FILES=('auth.json','memories/MEMORY.md','sessions/history.txt','skills/custom-note/SKILL.md')
SESSION_ROWS=[('session-preserved',)]


def verify_session_data(root):
    """Allow upstream schema/WAL maintenance, never lost or changed fixture rows."""
    uri=(root/'state.db').resolve().as_uri()+'?mode=ro'
    with closing(sqlite3.connect(uri, uri=True, timeout=3)) as conn:
        assert conn.execute('PRAGMA integrity_check').fetchall()==[('ok',)], 'Session DB integrity failed'
        rows=conn.execute('SELECT value FROM keep ORDER BY value').fetchall()
        assert rows==SESSION_ROWS, 'Session data changed: '+repr(rows)


def upstream_config_baseline():
    """Normalize synthetic config before measuring the DevKit cutover boundary."""
    from hermes_cli.config import get_config_path, migrate_config
    config_path=ROOT/'config.yaml'
    assert Path(get_config_path()).resolve()==config_path.resolve(), 'Unexpected fixture config root'
    original=yaml.safe_load(config_path.read_text())
    # The real image performs this migration in 01-hermes-setup, BEFORE the
    # DevKit boot guard. Execute that supported migration once during seeding,
    # rather than confusing its version stamp with a refused DevKit write.
    migrate_config(interactive=False, quiet=True)
    baseline=yaml.safe_load(config_path.read_text())
    for key,value in original.items():
        assert baseline.get(key)==value, 'Fixture setting changed during upstream normalization: '+key
    return baseline


def seed(kind):
    if kind=='fresh':return
    original={'model':{'provider':'openai-codex'},'custom':{'keep':['user-setting']},
              'skills':{'external_dirs':['/opt/custom-skills/coder'],'auto_load':['dev-implement-plan']}}
    for rel in FILES:
        p=ROOT/rel;p.parent.mkdir(parents=True,exist_ok=True)
        if rel=='auth.json':p.write_text('{"lite_ci_only":true}')
        else:p.write_text('unchanged CI data: '+rel)
    with closing(sqlite3.connect(ROOT/'state.db')) as conn:
        conn.execute('CREATE TABLE keep(value TEXT)')
        conn.executemany('INSERT INTO keep VALUES (?)', SESSION_ROWS)
        conn.commit()
    for role in ('orchestrator','coder','reviewer'):
        home=ROOT/'profiles'/role;home.mkdir(parents=True)
        (home/'SOUL.md').write_text('Legacy role instruction preserved')
        (home/'auth.json').write_text('{"ci_only":true}')
    if kind=='legacy':
        before={'dirs':original['skills']['external_dirs'],'autoload':original['skills']['auto_load'],'tools':None}
        applied={'dirs':['/opt/custom-skills/shared','/opt/custom-skills/lite'],
                 'autoload':['dev-implement-plan','dev-lite-session'],'tools':['hermes-cli','kanban']}
        original['skills']['external_dirs']=applied['dirs'];original['skills']['auto_load']=applied['autoload']
        original['toolsets']=applied['tools']
        p=ROOT/'devkit-lite/profile-state.json';p.parent.mkdir(parents=True)
        p.write_text(json.dumps({'schema':2,'phase':'applied','before':before,'applied':applied}))
        # Use the installed upstream connection module to create the real schema.
        from hermes_cli.kanban_db_connect import connect
        with closing(connect()) as conn:
            info=conn.execute('PRAGMA table_info(tasks)').fetchall()
            values={'id':'t_lite_ci','title':'preserved note','body':'manual record','status':'ready'}
            for col in info:
                _,name,typ,notnull,default,pk=col
                if notnull and default is None and name not in values:values[name]=0 if 'INT' in typ.upper() or 'REAL' in typ.upper() else ''
            names=list(values)
            conn.execute('INSERT INTO tasks ('+','.join('"'+n+'"' for n in names)+') VALUES ('+','.join('?' for _ in names)+')',[values[n] for n in names])
            conn.commit()
    elif kind=='active':
        with closing(sqlite3.connect(ROOT/'kanban.db')) as conn:
            conn.execute('CREATE TABLE tasks(status TEXT)');conn.execute("INSERT INTO tasks VALUES ('running')")
            conn.commit()
    elif kind=='collision':(ROOT/'devkit-lite/legacy-profiles/coder').mkdir(parents=True)
    (ROOT/'config.yaml').write_text(yaml.safe_dump(original))
    original=upstream_config_baseline()
    hashes={rel:hashlib.sha256((ROOT/rel).read_bytes()).hexdigest() for rel in FILES}
    MARKER.write_text(json.dumps({'hashes':hashes,'original':original,'kind':kind}))
    user=pwd.getpwnam('hermes')
    for base,dirs,files in os.walk(ROOT):
        os.chown(base,user.pw_uid,user.pw_gid)
        for name in files:os.chown(Path(base)/name,user.pw_uid,user.pw_gid)


def verify(blocked=False):
    if not MARKER.exists():return
    data=json.loads(MARKER.read_text())
    for rel,expected in data['hashes'].items():assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==expected,rel
    verify_session_data(ROOT)
    config=yaml.safe_load((ROOT/'config.yaml').read_text())
    journal=ROOT/'devkit-lite/migration-state.json'
    if blocked:
        assert config==data['original'], 'Blocked migration changed normalized config'
        assert (ROOT/'profiles/coder/SOUL.md').is_file()
        assert not journal.exists(), 'Blocked migration wrote its journal'
        return
    assert config['custom']==data['original']['custom']
    assert json.loads(journal.read_text())['phase']=='applied', 'Migration journal is not applied'
    for role in ('orchestrator','coder','reviewer'):
        assert not (ROOT/'profiles'/role).exists()
        assert (ROOT/'devkit-lite/legacy-profiles'/role/'SOUL.md').read_text()=='Legacy role instruction preserved'
    from hermes_cli.kanban_db_connect import connect
    with closing(connect()) as conn:
        row=conn.execute("SELECT status,body FROM tasks WHERE id='t_lite_ci'").fetchone()
    assert tuple(row)==('ready','manual record'),row
    print('[PASS] Synthetic auth/memory/history/custom-skill bytes, session rows and Kanban card preserved')


if __name__=='__main__':
    if sys.argv[1]=='seed':seed(sys.argv[2])
    else:verify(sys.argv[1]=='verify-blocked')
