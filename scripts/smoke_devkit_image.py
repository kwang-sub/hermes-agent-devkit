#!/usr/bin/env python3
"""Real s6 boot tests using only per-run UUID-labelled resources; no user volumes."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import tempfile
import time
import uuid
ROOT=Path(__file__).resolve().parents[1]
PYTHON='/opt/hermes/.venv/bin/python'


def mount_snapshot(raw):
    """Compare mount identity and every inspect field, not JSON/list ordering."""
    mounts = json.loads(raw)
    if not isinstance(mounts, list):
        raise ValueError('Docker mounts must be a JSON list')
    result = {}
    for mount in mounts:
        if not isinstance(mount, dict):
            raise ValueError('Invalid Docker mount entry')
        destination = mount.get('Destination')
        if not isinstance(destination, str) or not destination:
            raise ValueError('Docker mount destination is missing')
        if destination in result:
            raise ValueError('Duplicate Docker mount destination: ' + destination)
        result[destination] = mount
    return result


def assert_mounts_preserved(before, after):
    old, new = mount_snapshot(before), mount_snapshot(after)
    changed = sorted(key for key in old.keys() | new.keys() if old.get(key) != new.get(key))
    if changed:
        # These are disposable CI mounts, never a user's Docker configuration.
        details = {key: {'before': old.get(key), 'after': new.get(key)} for key in changed}
        raise AssertionError('Docker mounts changed across restart: ' + json.dumps(details, sort_keys=True))
    if before != after:
        print('[PASS] Mount JSON ordering changed; all mount fields are unchanged', flush=True)


def assert_plan_result(kind, result):
    if kind in ('legacy', 'previous-default'):
        assert result.returncode == 0, 'Read-only upgrade preflight failed: ' + result.stderr
    else:
        expected = {'active': 'Active Kanban tasks', 'interrupted': 'Interrupted migration',
                    'collision': 'Active/archive profile conflict', 'old-collision': 'Active/archive profile conflict'}[kind]
        assert result.returncode != 0 and expected in result.stderr, result.stdout + result.stderr


def run(args,*,code=None,check=True,timeout=180):
    p=subprocess.run(['docker',*args],input=code,text=True,capture_output=True,timeout=timeout)
    if check and p.returncode:
        raise RuntimeError('Docker fixture command failed (exit '+str(p.returncode)+'): '+str(args[:3])+'\n'+p.stdout[-3000:]+p.stderr[-5000:])
    return p


def diagnostics(name):
    # These are synthetic fixtures only. Never inspect a user's credentials/config.
    for args in (['inspect','--format','{{json .State}}',name], ['logs','--tail','120',name]):
        result=run(args,check=False,timeout=20)
        print('[BOOT_DIAGNOSTIC] '+name+' '+args[0],flush=True)
        print(result.stdout[-12000:]+result.stderr[-12000:],flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--image',required=True);a=parser.parse_args()
    tag='devkit-test-'+uuid.uuid4().hex[:12]
    created_containers=[];created_volumes=[];created_binds=[]
    fixture=(ROOT/'scripts/devkit_image_fixture.py').read_text()
    def exec_python(name,source): return run(['exec','-i','--user','hermes',name,PYTHON,'-'],code=source)
    with tempfile.TemporaryDirectory(prefix='devkit-boot-') as temp:
        temp=Path(temp); (temp/'workspace').mkdir();(temp/'external').mkdir()
        (temp/'external/sentinel').write_text('readonly-external-data')
        try:
            for index,kind in enumerate(('fresh','legacy','previous-default','active','collision','old-collision','interrupted')):
                name=f'{tag}-{kind}';volume=f'{name}-data'
                print('[BOOT_SCENARIO] '+kind,flush=True)
                if kind=='legacy':
                    data=temp/'legacy-data';data.mkdir();created_binds.append(data)
                    data_mount=f'type=bind,source={data},target=/opt/data'
                else:
                    run(['volume','create','--label','io.devkit.test='+tag,volume]);created_volumes.append(volume)
                    data_mount=f'type=volume,source={volume},target=/opt/data'
                mounts=['--mount',data_mount,'--mount',f'type=bind,source={ROOT}/custom-skills,target=/opt/custom-skills,readonly',
                        '--mount',f'type=bind,source={ROOT}/shared,target=/opt/data/shared,readonly',
                        '--mount',f'type=bind,source={temp}/workspace,target=/workspace',
                        '--mount',f'type=bind,source={temp}/external,target=/external,readonly']
                if kind!='fresh':
                    run(['run','--rm','-i','--entrypoint',PYTHON,'--mount',data_mount,a.image,'-','seed',kind],code=fixture)
                    plan=run(['run','--rm','-i','--read-only','--network','none','--user','hermes',
                              '--mount',data_mount+',readonly','-e','PYTHONDONTWRITEBYTECODE=1',
                              '--entrypoint',PYTHON,a.image,'-','plan'],
                             code=(ROOT/'scripts/devkit_default_profile.py').read_text(),check=False)
                    assert_plan_result(kind, plan)
                    if kind=='legacy':
                        print('[PASS] Read-only migration plan in the actual image',flush=True)
                run(['run','-d','--name',name,'--label','io.devkit.test='+tag,*mounts,
                     '-e','HERMES_KANBAN_DISPATCH_IN_GATEWAY=false','-e','HERMES_KANBAN_NOTIFY_ENABLED=false',
                     '-e','GATEWAY_MULTIPLEX_PROFILES=true',
                     '-e','HERMES_DASHBOARD=0','-e','HERMES_GATEWAY_BOOTSTRAP_STATE=running',
                     a.image,'gateway','run']);created_containers.append(name)
                if kind in ('active','collision','old-collision','interrupted'):
                    deadline=time.monotonic()+60
                    while time.monotonic()<deadline:
                        state=json.loads(run(['inspect','--format','{{json .State}}',name]).stdout)
                        if not state['Running']:break
                        time.sleep(.5)
                    assert not state['Running'] and state['ExitCode']!=0, 'Unsafe boot did not fail closed: '+kind
                    run(['run','--rm','-i','--entrypoint',PYTHON,'--mount',data_mount,a.image,'-','verify-blocked'],code=fixture)
                    logs=run(['logs',name],check=False)
                    bootlog=logs.stdout+logs.stderr
                    assert 'Reconciliation refused before successful migration' in bootlog
                    assert 'Reconciliation enabled after successful migration' not in bootlog
                    print('[PASS] Boot refused unsafe migration before gateways:',kind,flush=True)
                    continue
                deadline=time.monotonic()+120
                while True:
                    state=json.loads(run(['inspect','--format','{{json .State}}',name]).stdout)
                    if not state['Running']:
                        raise RuntimeError('Boot stopped early: '+kind+' '+json.dumps(state))
                    probe=run(['exec','--user','hermes',name,PYTHON,'/opt/devkit/bin/devkit_default_profile.py','status'],check=False)
                    if probe.returncode==0:break
                    if time.monotonic()>deadline:raise RuntimeError('Boot status timeout: '+kind)
                    time.sleep(1)
                run(['exec','--user','hermes',name,PYTHON,'/opt/devkit/bin/devkit_gateway_readiness.py','--wait-seconds','90'])
                exec_python(name,"import os\nfrom gateway.kanban_watchers import GatewayKanbanWatchersMixin\nassert os.environ['HERMES_KANBAN_DISPATCH_IN_GATEWAY']=='false'\nassert GatewayKanbanWatchersMixin()._kanban_dispatcher_boot() is None\n")
                run(['exec','-i','--user','hermes',name,PYTHON,'-','verify'],code=fixture)
                before=run(['inspect','--format','{{json .Mounts}}',name]).stdout
                run(['restart',name])
                run(['exec','--user','hermes',name,PYTHON,'/opt/devkit/bin/devkit_gateway_readiness.py','--wait-seconds','90'])
                run(['exec','-i','--user','hermes',name,PYTHON,'-','verify'],code=fixture)
                assert_mounts_preserved(before, run(['inspect','--format','{{json .Mounts}}',name]).stdout)
                assert (temp/'external/sentinel').read_text()=='readonly-external-data'
                print('[PASS] Real boot, restart, no dispatcher, profile archive and data/mount retention:',kind,flush=True)
            print('[PASS] DevKit image fresh/legacy/previous-default/active/collision/old-collision/interrupted scenarios')
        except Exception:
            for name in created_containers:
                try:diagnostics(name)
                except (subprocess.TimeoutExpired,RuntimeError):pass
            raise
        finally:
            for name in reversed(created_containers):run(['rm','-f',name],check=False)
            for name in reversed(created_volumes):run(['volume','rm',name],check=False)
            # ONLY restore ownership of UUID-scoped CI bind fixtures for cleanup.
            # This is not production boot or the updater.
            for data in created_binds:
                assert data.parent==temp and data.name=='legacy-data'
                run(['run','--rm','--network','none','--user','root',
                     '--mount',f'type=bind,source={data},target=/fixture',
                     '--entrypoint','/bin/chown',a.image,'-R',
                     f'{os.getuid()}:{os.getgid()}','/fixture'],check=False)
if __name__=='__main__':main()
