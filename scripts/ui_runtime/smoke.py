"""Opt-in, model-free UI smoke on an isolated HTTP fixture, never product acceptance."""
from __future__ import annotations
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from .artifacts import atomic_json
from .browser import Locator
from .extensions import OptionalOperations
from .suite import Suite

HTML = b'''<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DevKit UI smoke</title><style>body{font:18px sans-serif;margin:24px}input,button,select{padding:8px;max-width:90%}iframe{width:260px;height:120px}</style>
<h1>UI fixture</h1><label for="name">Name</label><input id="name"><button id="save">Save</button>
<p role="status" id="result"></p><label><input type="checkbox" id="active">Active</label>
<label for="choice">Choice</label><select id="choice"><option value="a">A</option><option value="b">B</option></select>
<button id="route">Route</button><button id="confirm">Confirm</button><button id="popup">Popup</button>
<input type="file" id="upload"><a id="download" href="/download">Download</a><iframe id="frame" src="/frame"></iframe>
<script>
window.answer=null;window.trusted=false;window.dirty=false;
document.querySelector('#name').addEventListener('input',()=>window.dirty=true);
document.querySelector('#save').onclick=e=>{window.trusted=e.isTrusted;setTimeout(()=>document.querySelector('#result').textContent=document.querySelector('#name').value,100)};
document.querySelector('#route').onclick=()=>history.pushState({},'', '/route');
document.querySelector('#confirm').onclick=()=>window.answer=confirm('Fixture dialog');
document.querySelector('#popup').onclick=()=>window.open('/popup');
window.addEventListener('beforeunload',e=>{if(window.dirty){e.preventDefault();e.returnValue=''}});
</script>'''
PAYLOAD = b'DevKit approved sample export\n'
FRAME = b'<!doctype html><label for="child">Child</label><input id="child"><button id="child-button">Child button</button>'


class Fixture(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split('?',1)[0]
        data = PAYLOAD if path == '/download' else FRAME if path == '/frame' else b'<!doctype html><h1 id="popup-ready">Popup</h1>' if path == '/popup' else HTML
        self.send_response(200)
        self.send_header('Content-Type', 'application/octet-stream' if path == '/download' else 'text/html; charset=utf-8')
        if path == '/download': self.send_header('Content-Disposition','attachment; filename="sample.txt"')
        self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
    def log_message(self,*args): pass


def probe(args):
    core = ['browser','navigate','input','keyboard','select','dialog','viewport','screenshot','spa']
    enabled = set(args.features.split(',')) if args.features else set()
    if not enabled.issubset({'upload','download','popup','frame','clipboard'}):
        raise ValueError('unknown optional feature')
    suite = Suite(args.output.parent/'checks',task_id='ui-smoke',required=core+sorted(enabled),
                  provider='browser_exec' if args.mode=='hermes' else 'cdp-test',
                  scope='DevKit HTTP fixture ONLY; not product UI acceptance',
                  environment={'mode':args.mode,'runtime_source':hashlib.sha256(b''.join(p.name.encode()+p.read_bytes() for p in sorted(Path(__file__).parent.glob('*.py')))).hexdigest()})
    state = {}
    def start():
        if args.mode == 'hermes':
            sys.path.insert(0,args.hermes_root)
            from .hermes import HermesBrowser
            state['browser'] = HermesBrowser(task_id='ui-smoke',allowed_origins=[args.origin])
        else:
            from .testing import TestBrowser
            state['browser'] = TestBrowser(args.chrome,allowed_origins=[args.origin])
            state['browser'].disposable = True
        return {'status':'PASS','evidence':'Approved browser transport started','mode':args.mode}
    def navigate():
        state['page'] = state['browser'].open(args.origin+'/',ready='!!document.querySelector("#save")',
                                             isolated_context=bool(enabled & {'download','clipboard'}))
        state['optional'] = OptionalOperations(state['page'],enabled=enabled,owner=state['browser'])
        suite.report['environment']['browser_version'] = state['page'].call('Browser.getVersion').get('product')
        return True
    def input_check():
        p=state['page'];p.fill(Locator(label='Name'),'SAMPLE');p.click(Locator(role='button',name='Save'))
        p.wait("document.querySelector('#result').textContent==='SAMPLE'")
        return p.evaluate('window.trusted===true')
    def keyboard():
        p=state['page'];p.click(Locator(label='Name'));p.press('Tab')
        return p.focused(Locator(selector='#save'))
    def select():
        p=state['page'];p.checked(Locator(selector='#active'),True);p.select(Locator(label='Choice'),'b')
        return p.evaluate("document.querySelector('#choice').value==='b'")
    def dialog():
        browser,p=state['browser'],state['page'];watch=browser.prepare_dialog(p)
        p.schedule("window.answer=confirm('Fixture dialog')")
        response=browser.respond_dialog(watch,action='dismiss',kind='confirm')
        p.wait('window.answer===false')
        response['evidence']='Explicit dialog dismissal and final value confirmed; '+response['response_owner']
        return response
    def viewport():
        p=state['page'];p.viewport(390,844,mobile=False,touch=False)
        return p.layout_observation()['width']==390
    def screenshot():return state['page'].screenshot(suite.directory)
    def spa():
        p=state['page'];before=p.evaluate('performance.timeOrigin')
        p.click(Locator(selector='#route'));p.wait_route('/route',ready='!!document.querySelector("#save")')
        return p.evaluate('performance.timeOrigin')==before
    def upload():
        path=suite.directory/'sample.txt';path.write_bytes(PAYLOAD)
        return state['optional'].upload(Locator(selector='#upload'),[path],approved_root=suite.directory)
    def download():
        state['optional'].prepare_downloads(suite.directory/'downloads')
        state['page'].click(Locator(selector='#download'))
        return state['optional'].wait_download('sample.txt',expected_sha256=hashlib.sha256(PAYLOAD).hexdigest())
    def popup():
        p=state['page'];p.click(Locator(selector='#popup'))
        child=state['optional'].popup(args.origin+'/popup',ready='!!document.querySelector("#popup-ready")')
        child.close();p.activate();return True
    def frame():
        child=state['optional'].frame(Locator(selector='#frame'));child.fill(Locator(label='Child'),'FRAME')
        return child.evaluate("document.querySelector('#child').value==='FRAME'")
    def clipboard():return state['optional'].clipboard_roundtrip('DevKit owned clipboard sample')
    operations = {'browser':start,'navigate':navigate,'input':input_check,'keyboard':keyboard,'select':select,
                  'dialog':dialog,'viewport':viewport,'screenshot':screenshot,'spa':spa,
                  'upload':upload,'download':download,'popup':popup,'frame':frame,'clipboard':clipboard}
    kinds={'screenshot':'visual','viewport':'responsive','keyboard':'accessibility','browser':'capability','navigate':'capability'}
    try:
        for key in core+sorted(enabled):
            depends=[] if key=='browser' else ['browser'] if key=='navigate' else ['navigate']
            suite.check(key,kinds.get(key,'functional'),operations[key],depends=depends,
                        observe=(lambda: state['page'].collect_diagnostics()) if 'page' in state else None)
            atomic_json(args.output,suite.report)
    finally:
        cleanup=state['browser'].close() if 'browser' in state else {'status':'PASS','errors':[]}
        report=suite.finish(cleanup)
        atomic_json(args.output,report)
    return 0 if report['verification_final'] else 2


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='operation',required=True)
    server=sub.add_parser('serve');server.add_argument('--port',type=int,required=True)
    p=sub.add_parser('probe');p.add_argument('--origin',required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=['hermes','cdp-test'],default='hermes');p.add_argument('--chrome')
    p.add_argument('--hermes-root',default='/opt/hermes');p.add_argument('--features',default='')
    args=parser.parse_args()
    if args.operation=='serve':
        with ThreadingHTTPServer(('127.0.0.1',args.port),Fixture) as http: http.serve_forever()
        return 0
    return probe(args)


if __name__=='__main__':raise SystemExit(main())
