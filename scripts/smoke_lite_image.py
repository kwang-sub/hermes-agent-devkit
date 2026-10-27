#!/usr/bin/env python3
"""Real s6 boot tests using only per-run UUID-labelled resources; no user volumes."""
from pathlib import Path
import argparse
import json
import subprocess
import tempfile
import time
import uuid
ROOT=Path(__file__).resolve().parents[1]
PYTHON='/opt/hermes/.venv/bin/python'

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
    tag='devkit-lite-test-'+uuid.uuid4().hex[:12]
    created_containers=[];created_volumes=[]
    fixture=(ROOT/'scripts/lite_image_fixture.py').read_text()
    def exec_python(name,source): return run(['exec','-i','--user','hermes',name,PYTHON,'-'],code=source)
    with tempfile.TemporaryDirectory(prefix='devkit-lite-boot-') as temp:
        temp=Path(temp); (temp/'workspace').mkdir();(temp/'external').mkdir()
        (temp/'external/sentinel').write_text('readonly-external-data')
        try:
            for index,kind in enumerate(('fresh','legacy','active','collision')):
                name=f'{tag}-{kind}';volume=f'{name}-data'
                print('[BOOT_SCENARIO] '+kind,flush=True)
                if kind=='legacy':
                    data=temp/'legacy-data';data.mkdir()
                    data_mount=f'type=bind,source={data},target=/opt/data'
                else:
                    run(['volume','create','--label','io.devkit.test='+tag,volume]);created_volumes.append(volume)
                    data_mount=f'type=volume,source={volume},target=/opt/data'
                mounts=['--mount',data_mount,'--mount',f'type=bind,source={ROOT}/custom-skills,target=/opt/custom-skills,readonly',
                        '--mount',f'type=bind,source={ROOT}/shared,target=/opt/data/shared,readonly',
                        '--mount',f'type=bind,source={temp}/workspace,target=/workspace',
                        '--mount',f'type=bind,source={temp}/external,target=/external,readonly']
                # Leave fresh data untouched until the actual s6 bootstrap.
                if kind!='fresh':
                    run(['run','--rm','-i','--entrypoint',PYTHON,'--mount',data_mount,a.image,'-','seed',kind],code=fixture)
                run(['run','-d','--name',name,'--label','io.devkit.test='+tag,*mounts,
                     '-e','HERMES_KANBAN_DISPATCH_IN_GATEWAY=false','-e','HERMES_KANBAN_NOTIFY_ENABLED=false',
                     '-e','HERMES_DASHBOARD=0','-e','HERMES_GATEWAY_BOOTSTRAP_STATE=running',
                     a.image,'gateway','run']);created_containers.append(name)
                if kind in ('active','collision'):
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
                    probe=run(['exec','--user','hermes',name,PYTHON,'/opt/devkit/bin/lite_default_profile.py','status'],check=False)
                    if probe.returncode==0:break
                    if time.monotonic()>deadline:
                        raise RuntimeError('Boot status timeout: '+kind)
                    time.sleep(1)
                run(['exec','--user','hermes',name,PYTHON,'/opt/devkit/bin/devkit_gateway_readiness.py','--wait-seconds','90'])
                exec_python(name,"import os\nfrom gateway.kanban_watchers import GatewayKanbanWatchersMixin\nassert os.environ['HERMES_KANBAN_DISPATCH_IN_GATEWAY']=='false'\nassert GatewayKanbanWatchersMixin()._kanban_dispatcher_boot() is None\n")
                run(['exec','-i','--user','hermes',name,PYTHON,'-','verify'],code=fixture)
                before=run(['inspect','--format','{{json .Mounts}}',name]).stdout
                run(['restart',name])
                run(['exec','--user','hermes',name,PYTHON,'/opt/devkit/bin/devkit_gateway_readiness.py','--wait-seconds','90'])
                run(['exec','-i','--user','hermes',name,PYTHON,'-','verify'],code=fixture)
                assert before==run(['inspect','--format','{{json .Mounts}}',name]).stdout
                assert (temp/'external/sentinel').read_text()=='readonly-external-data'
                print('[PASS] Real boot, restart, no dispatcher, profile archive and data/mount retention:',kind,flush=True)
            print('[PASS] Lite image fresh/legacy/active/collision scenarios')
        except Exception:
            for name in created_containers:
                try: diagnostics(name)
                except (subprocess.TimeoutExpired,RuntimeError): pass
            raise
        finally:
            for name in reversed(created_containers):run(['rm','-f',name],check=False)
            for name in reversed(created_volumes):run(['volume','rm',name],check=False)
if __name__=='__main__':main()
