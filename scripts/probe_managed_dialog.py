#!/usr/bin/env python3
"""Native dialog probe with explicit controller provenance (no pytest required).

Default mode uses installed Hermes browser_exec + browser_dialog, without CDP
endpoint overrides. --mode agent-browser exercises the actual installed CLI.
--mode policy-model is for development only: a source-equivalent auto-response
controller, with real Chromium dialogs; it is NOT a Hermes/agent-browser E2E.
"""
from __future__ import annotations
import argparse
import asyncio
import contextlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener

HTML = b'''<!doctype html><meta charset="utf-8"><title>DevKit native dialog probe</title>
<button id="activate" style="width:220px;height:80px">Prepare test input</button>
<input id="name"><script>
window.docId=String(Math.random()); window.dirty=false; window.probeAnswer=null;
document.querySelector('#activate').onclick=()=>{
 window.dirty=true; document.querySelector('#name').value='SAMPLE';
};
window.addEventListener('beforeunload',e=>{
 if(window.dirty){e.preventDefault();e.returnValue='';}
});
</script>'''
STATE = "({path:location.pathname,input:document.querySelector('#name')?.value||'',docId:window.docId||'',activated:navigator.userActivation.hasBeenActive,dirty:window.dirty===true,answer:window.probeAnswer})"
CANCELLED=False

class ProbeInterrupted(Exception):
    pass

def stop_signal(signum, frame):
    global CANCELLED
    CANCELLED=True
    raise ProbeInterrupted('probe cancellation requested')

EVENTS = {'Page.javascriptDialogOpening','Page.javascriptDialogClosed','Page.frameNavigated'}

class FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        data = HTML if urlsplit(self.path).path == '/' else b'<!doctype html><title>Next</title>NEXT'
        self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8')
        self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
    def log_message(self,*args): pass


def atomic_json(path, data):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=path.parent,delete=False) as out:
        temp=Path(out.name); json.dump(data,out,ensure_ascii=False,indent=2,allow_nan=False); out.write('\n')
    try: temp.replace(path)
    finally: temp.unlink(missing_ok=True)


def stop_owned(proc):
    """Stop only a process group started here; don't report cleanup from parent rc."""
    if proc is None: return
    if os.name!='posix':
        if proc.poll() is None: proc.terminate(); proc.wait(timeout=5)
        return
    with contextlib.suppress(ProcessLookupError): os.killpg(proc.pid,signal.SIGTERM)
    with contextlib.suppress(subprocess.TimeoutExpired): proc.wait(timeout=3)
    # A launcher may already be dead while its descendants are still exiting.
    time.sleep(.1)
    with contextlib.suppress(ProcessLookupError): os.killpg(proc.pid,signal.SIGKILL)
    with contextlib.suppress(subprocess.TimeoutExpired): proc.wait(timeout=2)


async def command(argv, env=None, timeout=20):
    proc=await asyncio.create_subprocess_exec(*argv,env=env,stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,start_new_session=True)
    try:
        stdout,stderr=await asyncio.wait_for(proc.communicate(),timeout)
        if proc.returncode:
            # Avoid logging arbitrary browser URLs, cookies, or source text.
            raise RuntimeError(f'controller command failed (rc={proc.returncode})')
        return stdout.decode('utf-8',errors='replace')
    finally:
        if proc.returncode is None:
            with contextlib.suppress(ProcessLookupError): os.killpg(proc.pid,signal.SIGKILL)
            await proc.wait()


class CDP:
    def __init__(self, ws):
        self.ws=ws; self.sequence=0; self.pending={}; self.events=[]; self.requests=[]
        self.callback=None; self.background=set(); self.reader=asyncio.create_task(self._read())
    async def _read(self):
        try:
            async for text in self.ws:
                event=json.loads(text)
                if 'id' in event:
                    future=self.pending.pop(event['id'],None)
                    if future and not future.done(): future.set_result(event)
                else:
                    event['time']=time.monotonic()
                    if event.get('method') in EVENTS: self.events.append(event)
                    if self.callback:
                        task=asyncio.create_task(self.callback(event)); self.background.add(task)
                        task.add_done_callback(self.background.discard)
        except Exception as exc:
            for future in self.pending.values():
                if not future.done(): future.set_exception(exc)
    async def call(self, method, params=None, session=None, timeout=5):
        self.sequence+=1; seq=self.sequence
        future=asyncio.get_running_loop().create_future(); self.pending[seq]=future
        payload={'id':seq,'method':method,'params':params or {}}
        if session: payload['sessionId']=session
        if method=='Page.handleJavaScriptDialog':
            self.requests.append({'method':method,'sessionId':session,'accept':params['accept'],'sent_at':time.monotonic()})
        try:
            await self.ws.send(json.dumps(payload))
            result=await asyncio.wait_for(future,timeout)
            if 'error' in result: raise RuntimeError(f'CDP method failed: {method}')
            return result.get('result',{})
        finally: self.pending.pop(seq,None)
    async def js(self,text,session):
        result=await self.call('Runtime.evaluate',{'expression':text,'returnByValue':True},session)
        if 'exceptionDetails' in result: raise RuntimeError('fixture JavaScript evaluation failed')
        return result.get('result',{}).get('value')
    async def close(self):
        for task in list(self.background): task.cancel()
        self.reader.cancel()
        with contextlib.suppress(asyncio.CancelledError): await self.reader
        await self.ws.close()


async def wait_for(check, timeout=5):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        result=await check()
        if result: return result
        await asyncio.sleep(.03)
    raise TimeoutError('bounded condition wait expired')


def chrome_path(supplied):
    if supplied: return str(Path(supplied).resolve())
    with contextlib.suppress(ImportError):
        from hermes_cli.browser_runtime import chromium_executable
        result=chromium_executable()
        if result: return str(result)
    result=shutil.which('chromium') or shutil.which('google-chrome')
    if not result: raise FileNotFoundError('existing Chromium executable is required')
    return result


def agent_path(supplied):
    if supplied: return str(Path(supplied).resolve())
    with contextlib.suppress(ImportError):
        from tools.browser_tool_install import _find_agent_browser
        return _find_agent_browser(validate=False) # No implicit install.
    result=shutil.which('agent-browser')
    if not result: raise FileNotFoundError('installed agent-browser is required (no automatic install)')
    return result


async def launch_chrome(executable, profile):
    log=open(Path(profile)/'chrome.log','wb')
    proc=subprocess.Popen([executable,'--headless=new','--no-sandbox','--disable-dev-shm-usage',
          '--no-first-run','--no-default-browser-check','--remote-debugging-port=0',
          f'--user-data-dir={profile}','about:blank'],stdout=subprocess.DEVNULL,stderr=log,start_new_session=True)
    try:
        active=Path(profile)/'DevToolsActivePort'
        async def ready():
            if proc.poll() is not None: raise RuntimeError('Chromium exited before readiness')
            return active.exists() and len(active.read_text().splitlines())>=2
        await wait_for(ready,12)
        port,path=active.read_text().splitlines()[:2]
        return proc,log,f'ws://127.0.0.1:{port}{path}',f'http://127.0.0.1:{port}'
    except BaseException:
        stop_owned(proc); log.close(); raise


def hermes_imports():
    from tools.browser_use_cli import browser_exec
    from tools.browser_dialog_tool import browser_dialog
    from tools.browser_supervisor import SUPERVISOR_REGISTRY
    return browser_exec,browser_dialog,SUPERVISOR_REGISTRY


async def one_case(args, origin, scenario, action, automatic):
    import websockets
    name='dv-'+uuid.uuid4().hex[:16]
    report={'scenario':scenario,'action':action,'mode':args.mode,'automatic_control':automatic,
            'response_owner':None,'result':'BLOCKED','events':[],'cleanup':{'status':'NOT_RUN'}}
    root=Path(tempfile.mkdtemp(prefix='devkit-dialog-probe-'))
    proc=log=observer=controller=sup=registry=None
    ab=None; env=None; phase='prepare'; task='devkit-'+name
    try:
        if args.mode=='hermes':
            # No A-E-style raw Chrome/CDP launch bypass, cloud, or human profile.
            from hermes_cli.config import read_raw_config
            cfg=(read_raw_config() or {}).get('browser',{}) or {}
            if any(os.environ.get(k) for k in ('BU_CDP_URL','BU_CDP_WS','BROWSER_CDP_URL','BU_AUTOSPAWN',
                                             'BROWSER_USE_API_KEY','BROWSERBASE_API_KEY','FIRECRAWL_API_KEY','CAMOFOX_URL')):
                raise RuntimeError('external browser overrides are configured; refusing to replace provider')
            if cfg.get('backend') not in (None,'','browser-use'):
                raise RuntimeError('probe requires browser-use; refusing to switch the configured backend')
            if cfg.get('cdp_url') or cfg.get('use_gateway') or cfg.get('cloud_provider') or cfg.get('use_real_profile') or cfg.get('engine') not in (None,'','auto','chromium','chrome'):
                raise RuntimeError('probe requires the approved managed local Chromium configuration')
            from tools.browser_tool_cloud import _get_cloud_provider
            if _get_cloud_provider() is not None:
                raise RuntimeError('cloud provider is resolved; refusing automatic provider changes')
            from tools.browser_tool_session import _agent_browser_command_env
            effective=_agent_browser_command_env(str(root/'preflight'))
            report['effective_no_auto_dialog']=effective.get('AGENT_BROWSER_NO_AUTO_DIALOG')
            if effective.get('AGENT_BROWSER_NO_AUTO_DIALOG')!='1':
                raise RuntimeError('managed launch policy patch is absent; no retry of product task')
            browser_exec,browser_dialog,registry=hermes_imports()
            async def tool(code):
                response=await asyncio.to_thread(browser_exec,code=code,session=name,task_id=task,timeout_s=15)
                value=json.loads(response) if isinstance(response,str) else response
                if not isinstance(value,dict) or not value.get('success'):
                    raise RuntimeError('Hermes browser_exec failed; see task-scoped tool log')
                return value
            phase='managed_launch'
            await tool(f'# Open isolated native dialog fixture\nnew_tab({origin!r})\nprint(page_info())')
            sup=registry.get(task)
            if sup is None: raise RuntimeError('no task-scoped Supervisor attached to managed browser')
            if not callable(getattr(sup,'focus_page',None)):
                raise RuntimeError('installed Supervisor cannot explicitly focus the probe target')
            focused=await asyncio.to_thread(sup.focus_page,origin,timeout=8)
            if not focused.get('ok'): raise RuntimeError('Supervisor target ownership is unconfirmed')
            ws_url=sup.cdp_url
            if urlsplit(ws_url).hostname not in ('localhost','127.0.0.1','::1'):
                raise RuntimeError('non-loopback CDP endpoint is outside this probe scope')
        else:
            phase='chromium_launch'
            proc,log,ws_url,endpoint=await launch_chrome(chrome_path(args.chrome),root)
            if args.mode=='agent-browser':
                ab=agent_path(args.agent_browser)
                env=os.environ.copy()
                for key in ('AGENT_BROWSER_CDP','AGENT_BROWSER_PROVIDER','AGENT_BROWSER_PROFILE',
                            'AGENT_BROWSER_SESSION','AGENT_BROWSER_CONFIG','AGENT_BROWSER_NO_AUTO_DIALOG'):
                    env.pop(key,None)
                env['AGENT_BROWSER_SOCKET_DIR']=str(root/'ab-socket')
                env['AGENT_BROWSER_NO_AUTO_DIALOG']='0' if automatic else '1'
                env['AGENT_BROWSER_CONFIG']=str(root/'empty-config.json')
                (root/'empty-config.json').write_text('{}',encoding='utf-8')
                report['agent_browser_version']=(await command([ab,'--version'],env)).strip()
                phase='agent_browser_attach'
                await command([ab,'--session',name,'--cdp',endpoint,'--json','open',origin],env)
        observer=CDP(await websockets.connect(ws_url,open_timeout=8,max_size=4*1024*1024))
        version=await observer.call('Browser.getVersion')
        report['browser_version']=version.get('product')
        phase='target_match'
        targets=(await observer.call('Target.getTargets'))['targetInfos']
        pages=[t for t in targets if t['type']=='page' and t.get('url','').startswith(origin+'/')]
        if args.mode=='policy-model':
            blank=[t for t in targets if t['type']=='page']
            if len(blank)!=1: raise RuntimeError('ambiguous initial test target')
            target=blank[0]['targetId']
        else:
            if len(pages)!=1: raise RuntimeError('probe must own exactly one fixture page')
            target=pages[0]['targetId']
        sid=(await observer.call('Target.attachToTarget',{'targetId':target,'flatten':True}))['sessionId']
        await observer.call('Page.enable',session=sid)
        await observer.call('Runtime.enable',session=sid)
        report['target_id']=target; report['observer_session_id']=sid
        if args.mode=='policy-model':
            controller=CDP(await websockets.connect(ws_url,open_timeout=8))
            csid=(await controller.call('Target.attachToTarget',{'targetId':target,'flatten':True}))['sessionId']
            await controller.call('Page.enable',session=csid)
            async def autopolicy(event):
                if automatic and event.get('method')=='Page.javascriptDialogOpening' and event.get('params',{}).get('type') in ('beforeunload','alert'):
                    await controller.call('Page.handleJavaScriptDialog',{'accept':True},session=csid)
            controller.callback=autopolicy
            if args.offline_fixture:
                frame=(await observer.call('Page.getFrameTree',session=sid))['frameTree']['frame']['id']
                await observer.call('Page.setDocumentContent',{'frameId':frame,'html':HTML.decode()},session=sid)
                report['fixture_transport']='offline-in-memory-document'
            else:
                await observer.call('Page.navigate',{'url':origin+'/'},session=sid)
        async def loaded():
            return await observer.js('!!document.querySelector("#activate")',sid)
        await wait_for(loaded)
        if await observer.js('document.title',sid)!='DevKit native dialog probe':
            raise RuntimeError('refusing to operate on a non-fixture page')
        phase='activate'
        if args.mode=='hermes':
            await tool('# Prepare real user activation\nclick_at_xy(110,40)\nprint(page_info())')
        elif args.mode=='agent-browser':
            await command([ab,'--session',name,'--json','click','#activate'],env)
        else:
            for kind in ('mousePressed','mouseReleased'):
                await observer.call('Input.dispatchMouseEvent',{'type':kind,'x':110,'y':40,'button':'left','clickCount':1},sid)
        initial=await observer.js(STATE,sid)
        report['initial']=initial
        if not initial['activated'] or not initial['dirty'] or initial['input']!='SAMPLE':
            raise RuntimeError('real user activation or dirty input was not established')
        script={'reload':'setTimeout(()=>location.reload(),100); "scheduled"',
                'navigate':'setTimeout(()=>location.assign("/next"),100); "scheduled"',
                'confirm':'setTimeout(()=>{window.probeAnswer=confirm("DevKit probe")},100); "scheduled"'}[scenario]
        if args.offline_fixture and scenario=='navigate':
            script='setTimeout(()=>location.assign("about:blank?devkit=next"),100); "scheduled"'
        phase='trigger'
        if args.mode=='hermes':
            await tool(f'# Schedule native dialog\nprint(js({script!r}))')
        elif args.mode=='agent-browser':
            await command([ab,'--session',name,'--json','eval',script],env)
        else: await observer.js(script,sid)
        expected_type='confirm' if scenario=='confirm' else 'beforeunload'
        async def opened():
            return next((e for e in observer.events if e['method']=='Page.javascriptDialogOpening' and e.get('sessionId')==sid and e['params'].get('type')==expected_type),None)
        phase='opening'
        if args.mode=='hermes' and expected_type=='confirm':
            async def captured_confirm():
                native=await opened()
                if native: return native
                dialog=next((d for d in sup.snapshot().pending_dialogs if d.type=='confirm'),None)
                if dialog and getattr(dialog,'bridge_request_id',None):
                    return {'method':'Hermes.dialogPending','time':time.monotonic(),
                            'params':{'type':'confirm','dialog_id':dialog.id}}
                return None
            opening=await wait_for(captured_confirm,5)
        else:
            opening=await wait_for(opened,5)
        bridged=opening.get('method')=='Hermes.dialogPending'
        report['capture_kind']='hermes-bridge' if bridged else 'native-CDP'
        if bridged: observer.events.append(opening)
        # Prove a window for deliberate response, not a race won by rapid polling.
        await asyncio.sleep(.65)
        closed=[e for e in observer.events if e['method']=='Page.javascriptDialogClosed' and e.get('sessionId')==sid and e['time']>=opening['time']]
        report['closed_before_response']=bool(closed)
        phase='respond'
        if not closed:
            if args.mode=='hermes':
                async def pending():
                    snap=sup.snapshot()
                    return next((d for d in snap.pending_dialogs if d.type==expected_type),None)
                dialog=await wait_for(pending,3)
                # Only official browser_dialog sends a response in Hermes mode.
                report['response_owner']='hermes.browser_dialog'
                report['response']={'action':action,'sent_at':time.monotonic(),'dialog_id':dialog.id}
                value=await asyncio.to_thread(browser_dialog,action=action,dialog_id=dialog.id,task_id=task)
                value=json.loads(value) if isinstance(value,str) else value
                report['response']['success']=value.get('success') is True
            elif args.mode=='agent-browser':
                report['response_owner']='agent-browser.dialog'
                report['response']={'action':action,'sent_at':time.monotonic()}
                value=json.loads(await command([ab,'--session',name,'--json','dialog',action],env,8))
                report['response']['success']=value.get('success') is True
            else:
                report['response_owner']='source-policy-model.manual-CDP'
                report['response']={'action':action,'sent_at':time.monotonic()}
                await controller.call('Page.handleJavaScriptDialog',{'accept':action=='accept'},csid)
                report['response']['success']=True
        phase='closed'
        async def ended():
            return next((e for e in observer.events if e['method']=='Page.javascriptDialogClosed' and e.get('sessionId')==sid and e['time']>=opening['time']),None)
        if bridged:
            ending={'method':'Hermes.dialogResponded','time':time.monotonic(),
                    'params':{'result':action=='accept'}}
            observer.events.append(ending)
        else:
            ending=await wait_for(ended,5)
        await asyncio.sleep(.3)
        final=await observer.js(STATE,sid); report['final']=final
        report['dialog_result']=ending['params']['result']
        report['page_preserved']=initial['docId']==final['docId'] and initial['path']==final['path']
        report['input_preserved']=final['input']=='SAMPLE'
        if automatic and scenario!='confirm':
            good=report['closed_before_response'] and report['dialog_result'] is True and not report['page_preserved']
            report['result']='REPRODUCED_AUTO_ACCEPT' if good else 'NOT_REPRODUCED'
        else:
            explicit=report.get('response',{}).get('success') is True and not report['closed_before_response']
            expected=action=='accept'
            kept=report['page_preserved'] and report['input_preserved']
            if scenario=='confirm': good=explicit and final['answer'] is expected and kept
            else: good=explicit and report['dialog_result'] is expected and (not report['page_preserved'] if expected else kept)
            report['result']='PASS' if good else 'FAIL'
        if args.mode=='policy-model': report['model_response_commands']=controller.requests
    except Exception as exc:
        report.update(result='BLOCKED',failed_phase=phase,error=f'{type(exc).__name__}: {exc}')
        if observer and 'sid' in locals():
            with contextlib.suppress(Exception): report['failure_document']=await observer.js('({ready:document.readyState,fixturePresent:!!document.querySelector("#activate")})',sid)
    finally:
        if observer:
            report['events']=[{'method':e['method'],'sessionId':e.get('sessionId'),'time':e['time'],
                              'params':{k:v for k,v in e.get('params',{}).items() if k in ('type','frameId','hasBrowserHandler','result')}} for e in observer.events]
        errors=[]
        # Supervisor must stop before closing its browser endpoint.
        if sup:
            try: await asyncio.to_thread(sup.stop)
            except Exception as exc: errors.append('supervisor:'+type(exc).__name__)
        if args.mode=='hermes':
            try:
                from tools.browser_use_cli import _find_cli
                cli=_find_cli()
                if not cli: raise RuntimeError('harness CLI missing during cleanup')
                from tools import browser_use_cli as bu
                names={name}
                sidecar=getattr(bu,'_sidecar_daemon_name',None)
                if callable(sidecar): names.add(sidecar(name))
                for daemon_name in names:
                    private_env=os.environ.copy(); private_env['BU_NAME']=daemon_name
                    await command([*cli,'--reload'],private_env,8)
            except Exception as exc: errors.append('harness:'+type(exc).__name__)
        if controller:
            with contextlib.suppress(Exception): await controller.close()
        if observer:
            if args.mode=='hermes':
                # It was launched by this unique task. Close that owned browser only.
                try: await observer.call('Browser.close',timeout=2)
                except Exception: pass  # Browser.close may end the socket before its reply.
            with contextlib.suppress(Exception): await observer.close()
        if ab:
            try: await command([ab,'--session',name,'--json','close'],env,8)
            except Exception as exc: errors.append('agent-browser:'+type(exc).__name__)
        if proc:
            try: stop_owned(proc)
            except Exception as exc: errors.append('chromium:'+type(exc).__name__)
        if log: log.close()
        for attempt in range(4):
            try: shutil.rmtree(root); break
            except FileNotFoundError: break
            except OSError as exc:
                if attempt==3: errors.append('profile:'+type(exc).__name__)
                else: await asyncio.sleep(.2)
        report['cleanup']={'status':'WARNING' if errors else 'PASS','errors':errors}
        if errors and report['result']=='PASS': report['result']='INCONCLUSIVE'
    return report


async def run(args):
    server=thread=None
    if not args.origin:
        server=ThreadingHTTPServer(('127.0.0.1',0),FixtureHandler)
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    report={'schema':'managed_dialog_probe_v1','mode':args.mode,'provider':'browser_exec' if args.mode=='hermes' else args.mode,
            'scope':'Native fixture only; NOT product UI acceptance',
            'source_policy_model':args.mode=='policy-model','cases':[]}
    try:
        origin=args.origin or f'http://127.0.0.1:{server.server_port}'
        matrix=[]
        if args.mode!='hermes':
            matrix.extend([(s,'dismiss',True) for s in ('reload','navigate')])
            matrix.append(('confirm','dismiss',True))
        matrix.extend((s,a,False) for s in ('reload','navigate','confirm') for a in ('dismiss','accept'))
        total_expected=len(matrix)
        if args.case_limit: matrix=matrix[:args.case_limit]
        report['complete_matrix']=len(matrix)==total_expected
        for scenario,action,automatic in matrix:
            print(f'PROBE_CASE={scenario}/{action}/auto={automatic}',flush=True)
            entry=await one_case(args,origin,scenario,action,automatic)
            report['cases'].append(entry); atomic_json(args.output,report)
            print(f'PROBE_RESULT={entry["result"]}',flush=True)
            if CANCELLED or (args.mode=='hermes' and entry['result']!='PASS'):
                report['complete_matrix']=False
                break
        valid={'PASS','REPRODUCED_AUTO_ACCEPT'}
        report['result']=('PASS' if report['complete_matrix'] else 'PARTIAL') if all(c['result'] in valid for c in report['cases']) else 'BLOCKED'
    finally:
        if server:
            server.shutdown(); server.server_close(); thread.join(timeout=2)
        atomic_json(args.output,report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('hermes','agent-browser','policy-model'),default='hermes')
    parser.add_argument('--offline-fixture',action='store_true',help='Policy-model only: no HTTP navigation')
    parser.add_argument('--case-limit',type=int,default=0)
    parser.add_argument('--chrome'); parser.add_argument('--agent-browser')
    parser.add_argument('--origin',help='Approved isolated fixture origin, localhost HTTP only')
    parser.add_argument('--hermes-root',default='/opt/hermes')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    signal.signal(signal.SIGTERM,stop_signal)
    signal.signal(signal.SIGINT,stop_signal)
    if args.offline_fixture and args.mode!='policy-model': parser.error('offline fixture is only a development policy-model test')
    if args.origin:
        parsed=urlsplit(args.origin)
        if (parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost','::1')
                or not parsed.port or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in ('','/')):
            parser.error('--origin must be an explicit loopback HTTP origin without credentials')
        args.origin=args.origin.rstrip('/')
    root=Path(args.hermes_root)
    if root.is_dir(): sys.path.insert(0,str(root))
    try:
        report=asyncio.run(run(args))
        print(json.dumps({'result':report['result'],'mode':args.mode,'cases':len(report['cases'])}))
        return 0 if report['result']=='PASS' else 2
    except Exception as exc:
        report={'result':'BLOCKED','error':f'{type(exc).__name__}: {exc}'}
        atomic_json(args.output,report); print(json.dumps(report)); return 2


if __name__=='__main__': raise SystemExit(main())
