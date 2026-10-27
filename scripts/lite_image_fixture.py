"""Executed ONLY inside disposable integration containers by smoke_lite_image.py."""
from pathlib import Path
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
FILES=('auth.json','memories/MEMORY.md','state.db','sessions/history.txt','skills/custom-note/SKILL.md')

def seed(kind):
    if kind=='fresh':return
    original={'model':{'provider':'openai-codex'},'custom':{'keep':['user-setting']},
              'skills':{'external_dirs':['/opt/custom-skills/coder'],'auto_load':['dev-implement-plan']}}
    for rel in FILES:
        p=ROOT/rel;p.parent.mkdir(parents=True,exist_ok=True)
        if rel=='state.db':
            with sqlite3.connect(p) as c:c.execute('CREATE TABLE keep(value TEXT)');c.execute("INSERT INTO keep VALUES ('session-preserved')")
        elif rel=='auth.json':p.write_text('{"lite_ci_only":true}')
        else:p.write_text('unchanged CI data: '+rel)
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
        conn=connect()
        path=Path(conn.execute('PRAGMA database_list').fetchone()[2])
        info=conn.execute('PRAGMA table_info(tasks)').fetchall()
        values={'id':'t_lite_ci','title':'preserved note','body':'manual record','status':'ready'}
        for col in info:
            _,name,typ,notnull,default,pk=col
            if notnull and default is None and name not in values:values[name]=0 if 'INT' in typ.upper() or 'REAL' in typ.upper() else ''
        names=list(values)
        conn.execute('INSERT INTO tasks ('+','.join('"'+n+'"' for n in names)+') VALUES ('+','.join('?' for _ in names)+')',[values[n] for n in names])
        conn.commit();conn.close()
    elif kind=='active':
        with sqlite3.connect(ROOT/'kanban.db') as c:
            c.execute('CREATE TABLE tasks(status TEXT)');c.execute("INSERT INTO tasks VALUES ('running')")
    elif kind=='collision':(ROOT/'devkit-lite/legacy-profiles/coder').mkdir(parents=True)
    (ROOT/'config.yaml').write_text(yaml.safe_dump(original))
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
    config=yaml.safe_load((ROOT/'config.yaml').read_text())
    if blocked:
        assert config==data['original'];assert (ROOT/'profiles/coder/SOUL.md').is_file()
        assert not (ROOT/'devkit-lite/transition.json').exists()
        return
    assert config['custom']==data['original']['custom']
    for role in ('orchestrator','coder','reviewer'):
        assert not (ROOT/'profiles'/role).exists()
        assert (ROOT/'devkit-lite/legacy-profiles'/role/'SOUL.md').read_text()=='Legacy role instruction preserved'
    from hermes_cli.kanban_db_connect import connect
    conn=connect();row=conn.execute("SELECT status,body FROM tasks WHERE id='t_lite_ci'").fetchone();conn.close()
    assert tuple(row)==('ready','manual record'),row
    print('[PASS] synthetic OAuth/memory/sessions/custom-skill bytes and Kanban card preserved')
if sys.argv[1]=='seed':seed(sys.argv[2])
else:verify(sys.argv[1]=='verify-blocked')
