#!/usr/bin/env python3
"""Stage 2 real actions via a supplied transport, plus optional live Chromium tests."""
import os
from pathlib import Path
import tempfile
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import unittest
from ui_runtime.browser import BrowserPage,Locator,origin
from ui_runtime.capture import TimeBudget
from ui_runtime.diagnostics import Diagnostics
from ui_runtime.suite import EnvironmentBlocked

HTML=b'''<!doctype html><meta name="viewport" content="width=device-width, initial-scale=1">
<label for="name">Name</label><input id="name"><button id="save">Save</button><p id="result"></p>
<label><input id="check" type="checkbox">Active</label>
<label for="choice">Choice</label><select id="choice"><option value="a">A</option><option value="b">B</option></select>
<button id="route">Route</button><button id="confirm">Confirm</button>
<script>window.answer=null;window.inputs=0;window.trusted=false;
nameInput=document.querySelector('#name');nameInput.addEventListener('input',()=>window.inputs++);
document.querySelector('#save').onclick=e=>{window.trusted=e.isTrusted;setTimeout(()=>document.querySelector('#result').textContent=nameInput.value,100)};
document.querySelector('#route').onclick=()=>history.pushState({},'', '/route');
document.querySelector('#confirm').onclick=()=>window.answer=confirm('Test');</script>'''

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(HTML)
    def log_message(self,*args):pass


class Transport:
    def __init__(self):self.calls=[]
    def call(self,method,params,**kw):
        self.calls.append((method,params,kw))
        if method=='Runtime.evaluate':return {'result':{'value':'http://127.0.0.1:3107/'}}
        return {}

class BrowserUnitTests(unittest.TestCase):
    def test_explicit_session_and_outer_budget(self):
        t=Transport();p=BrowserPage(t,'T','S',allowed_origins=['http://127.0.0.1:3107'])
        p.call('Page.captureScreenshot',{},timeout=60)
        self.assertEqual(t.calls[-1][2],{'session':'S','timeout':60,'outer_timeout':75.0})
    def test_activate_owned_target_not_default(self):
        t=Transport();p=BrowserPage(t,'T','S',allowed_origins=['http://127.0.0.1:3107']);p.activate()
        self.assertEqual(t.calls[1][1],{'targetId':'T'});self.assertIsNone(t.calls[1][2]['session'])
        self.assertEqual(t.calls[2][2]['session'],'S')
    def test_external_navigation_refused(self):
        t=Transport();p=BrowserPage(t,'T','S',allowed_origins=['http://127.0.0.1:3107'])
        with self.assertRaises(EnvironmentBlocked):p.navigate('https://example.invalid/',ready='true')
        self.assertEqual(t.calls,[])
    def test_viewport_distinguishes_mobile_from_width(self):
        t=Transport();p=BrowserPage(t,'T','S',allowed_origins=['http://127.0.0.1:3107'])
        self.assertEqual(p.viewport(390,844)['scope'],'layout-viewport')
        self.assertEqual(p.viewport(390,844,mobile=True,touch=True)['scope'],'mobile-emulation')
    def test_locator_escapes_text_and_has_no_click_shim(self):
        expression=Locator(label='Name";alert(1)').expression()
        self.assertIn('Name\\"',expression)
        self.assertNotIn('.click()',Path(__file__).with_name('ui_runtime').joinpath('browser.py').read_text())
    def test_scoped_diagnostics_do_not_capture_secrets(self):
        d=Diagnostics('S',limit=2)
        for i in range(4):d.feed({'sessionId':'S','method':'Runtime.exceptionThrown','params':{'exceptionDetails':{'text':'secret'}}})
        d.feed({'sessionId':'OTHER','method':'Network.loadingFailed','params':{}})
        self.assertEqual(d.snapshot()['dropped'],2)
        self.assertNotIn('secret',str(d.snapshot()))
    def test_http_statuses_are_diagnostics_not_automatic_fail(self):
        d=Diagnostics('S');d.feed({'sessionId':'S','method':'Network.responseReceived','params':{'response':{'status':404,'url':'secret'}}})
        self.assertEqual(d.snapshot()['events'][0]['http_status'],404)
        self.assertNotIn('secret',str(d.snapshot()))


@unittest.skipUnless(os.environ.get('DEVKIT_TEST_CHROME'),'existing Chromium opt-in required')
class LiveBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ui_runtime.testing import TestBrowser
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.server.server_port}'
        cls.browser=TestBrowser(os.environ['DEVKIT_TEST_CHROME'],allowed_origins=[cls.url],budget=TimeBudget(action=3,navigation=5,capture=8))
    @classmethod
    def tearDownClass(cls):
        cls.cleanup=cls.browser.close();cls.server.shutdown();cls.server.server_close();cls.thread.join(2)
        if cls.cleanup['status']!='PASS':raise AssertionError(cls.cleanup)
    def setUp(self):
        if os.environ.get('DEVKIT_TEST_MEMORY')=='1':
            self.page=self.browser.open_memory(HTML.decode())
        else:
            self.page=self.browser.open(self.url+'/',ready='!!document.querySelector("#save")')
    def tearDown(self):self.page.close()
    def test_real_input_and_trusted_pointer(self):
        p=self.page;p.fill(Locator(label='Name'),'SAMPLE');p.click(Locator(role='button',name='Save'))
        p.wait("document.querySelector('#result').textContent==='SAMPLE'")
        self.assertTrue(p.evaluate('window.trusted'));self.assertGreater(p.evaluate('window.inputs'),0)
    def test_spa_route_does_not_require_document_replacement(self):
        if os.environ.get('DEVKIT_TEST_MEMORY')=='1':self.skipTest('HTTP history route is not a memory-DOM test')
        p=self.page;before=p.evaluate('performance.timeOrigin');p.click(Locator(selector='#route'));p.wait_route('/route')
        self.assertEqual(p.evaluate('performance.timeOrigin'),before)
    def test_checkbox_select_and_keyboard(self):
        p=self.page;p.checked(Locator(selector='#check'),True);p.select(Locator(label='Choice'),'b')
        self.assertEqual(p.evaluate("document.querySelector('#choice').value"),'b')
        p.click(Locator(label='Name'));p.press('Tab');self.assertTrue(p.focused(Locator(selector='#save')))
        p.press('Enter');p.wait('window.trusted===true')
    def test_capture_after_viewport_and_accessibility(self):
        p=self.page;p.viewport(390,844)
        with tempfile.TemporaryDirectory() as tmp:
            r=p.screenshot(Path(tmp));self.assertEqual(r['status'],'PASS',r)
            self.assertEqual(r['width'],390);self.assertEqual(r['height'],844)
        self.assertTrue(p.accessibility_snapshot()['nodes'])
    def test_explicit_dialog_development_path(self):
        p=self.page;watch=self.browser.prepare_dialog(p);p.schedule("window.answer=confirm('Test')")
        r=self.browser.respond_dialog(watch,action='dismiss',kind='confirm')
        p.wait('window.answer===false');self.assertEqual(r['response_owner'],'cdp-test')



class HermesTransportTests(unittest.TestCase):
    def browser(self, temp, execute):
        import threading
        from ui_runtime.hermes import HermesBrowser
        b=HermesBrowser.__new__(HermesBrowser)
        b.exchange=temp;b.lock=threading.RLock();b.closed=False;b.execute=execute
        b.session='owned-session';b.task_id='owned-task';b.budget=TimeBudget()
        return b
    def test_large_response_uses_file_not_truncated_stdout(self):
        seen={}
        def execute(**kw):
            seen.update(kw)
            namespace={'cdp':lambda *a,**k:{'data':'X'*100000}}
            exec(kw['code'],namespace)
            return {'success':True,'output':'TRUNCATED'}
        with tempfile.TemporaryDirectory() as temp:
            class Exchange:name=temp
            b=self.browser(Exchange(),execute)
            self.assertEqual(len(b.call('Page.captureScreenshot',{},session='S',timeout=60)['data']),100000)
            self.assertEqual(seen['timeout_s'],75)
            self.assertEqual(list(Path(temp).iterdir()),[])
    def test_failed_command_does_not_reuse_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            class Exchange:name=temp
            b=self.browser(Exchange(),lambda **kw:{'success':False})
            with self.assertRaises(EnvironmentBlocked):b.call('Page.enable',{})
    def test_explicit_session_and_parameters_preserved(self):
        seen=[]
        def execute(**kw):
            def cdp(*args,**params):seen.append((args,params));return {}
            exec(kw['code'],{'cdp':cdp})
            return {'success':True}
        with tempfile.TemporaryDirectory() as temp:
            class Exchange:name=temp
            b=self.browser(Exchange(),execute);b.call('Runtime.evaluate',{'expression':'"quoted"'},session='owned')
            self.assertEqual(seen[0][1]['session_id'],'owned')
            self.assertEqual(seen[0][1]['expression'],'"quoted"')

if __name__=='__main__':unittest.main(verbosity=2)
