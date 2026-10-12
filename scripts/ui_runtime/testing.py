"""Explicit development-only Chromium transport. Never a fallback for Hermes."""
from __future__ import annotations
from collections import deque
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import time
from .browser import BrowserPage
from .capture import TimeBudget
from .process import stop_owned
from .suite import EnvironmentBlocked, Unsupported


class SocketTransport:
    def __init__(self, endpoint):
        from websockets.sync.client import connect
        self.socket = connect(endpoint, open_timeout=8, max_size=64*1024*1024, proxy=None)
        self.pending, self.sequence, self.records = {}, 0, deque(maxlen=500)
        self.lock = threading.RLock()
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _read(self):
        try:
            for text in self.socket:
                event = json.loads(text)
                with self.lock:
                    if 'id' in event and event['id'] in self.pending:
                        holder = self.pending[event['id']]
                        holder['result'] = event
                        holder['ready'].set()
                    elif 'method' in event:
                        event['observed_at'] = time.monotonic()
                        self.records.append(event)
        except Exception:
            with self.lock:
                for holder in self.pending.values():
                    holder['result'] = {'error': {'code': 'TRANSPORT_CLOSED'}}
                    holder['ready'].set()

    def call(self, method, params, *, session=None, timeout=10, outer_timeout=None):
        with self.lock:
            self.sequence += 1
            key = self.sequence
            holder = {'ready': threading.Event()}
            self.pending[key] = holder
        packet = {'id': key, 'method': method, 'params': params}
        if session: packet['sessionId'] = session
        try:
            self.socket.send(json.dumps(packet))
            if not holder['ready'].wait(timeout):
                raise TimeoutError('CDP operation budget exhausted')
            result = holder['result']
            if 'error' in result:
                if result['error'].get('code') == -32601: raise Unsupported('CDP method unavailable')
                raise EnvironmentBlocked('CDP operation failed')
            return result.get('result', {})
        finally:
            with self.lock: self.pending.pop(key, None)

    def drain_events(self):
        with self.lock:
            result = list(self.records)
            self.records.clear()
            return result

    def close(self):
        self.socket.close()
        self.thread.join(timeout=2)


class TestBrowser:
    """Starts only the supplied installed binary; no downloads or version changes."""
    def __init__(self, chrome: str, *, allowed_origins: list[str], budget=None):
        if not Path(chrome).is_file():
            raise FileNotFoundError('existing Chromium binary required')
        self.profile = tempfile.TemporaryDirectory(prefix='devkit-ui-chrome-')
        self.log = (Path(self.profile.name)/'chrome.log').open('wb')
        self.proc = subprocess.Popen([chrome, '--headless=new', '--no-sandbox', '--disable-dev-shm-usage',
                    '--no-first-run', '--no-default-browser-check', '--remote-debugging-port=0',
                    '--user-data-dir='+self.profile.name, 'about:blank'],
                    stdout=self.log, stderr=self.log, start_new_session=True)
        self.allowed_origins, self.pages = allowed_origins, []
        self.budget = budget or TimeBudget()
        self.closed = False
        try:
            port = Path(self.profile.name)/'DevToolsActivePort'
            deadline = time.monotonic()+12
            while not port.exists():
                if self.proc.poll() is not None or time.monotonic()>deadline:
                    raise EnvironmentBlocked('Chromium startup failed')
                time.sleep(.05)
            lines = port.read_text().splitlines()
            self.transport = SocketTransport('ws://127.0.0.1:'+lines[0]+lines[1])
        except BaseException:
            stop_owned(self.proc); self.log.close(); self.profile.cleanup()
            raise

    def open(self, url, *, ready, isolated_context=False):
        params = {'url': url}
        context = None
        if isolated_context:
            context = self.transport.call('Target.createBrowserContext', {})['browserContextId']
            params['browserContextId'] = context
        target = self.transport.call('Target.createTarget', params)['targetId']
        sid = self.transport.call('Target.attachToTarget', {'targetId':target,'flatten':True})['sessionId']
        page = BrowserPage(self.transport,target,sid,allowed_origins=self.allowed_origins,budget=self.budget)
        page.context_id = context
        self.pages.append(page)
        page.call('Page.enable'); page.call('Runtime.enable')
        page.wait(ready);page.require_origin()
        return page

    def open_memory(self, html: str):
        """Explicit DOM-only experiment; does not weaken HTTP origin checks."""
        target = self.transport.call('Target.createTarget', {'url':'about:blank'})['targetId']
        sid = self.transport.call('Target.attachToTarget', {'targetId':target,'flatten':True})['sessionId']
        class MemoryPage(BrowserPage):
            def require_origin(self):
                if not self.evaluate("location.href.startsWith('about:blank')"):
                    raise EnvironmentBlocked('memory test left its owned document')
        page = MemoryPage(self.transport,target,sid,allowed_origins=self.allowed_origins,budget=self.budget)
        self.pages.append(page)
        page.call('Page.enable');page.call('Runtime.enable')
        frame = page.call('Page.getFrameTree')['frameTree']['frame']['id']
        page.call('Page.setDocumentContent',{'frameId':frame,'html':html})
        page.context_id = None
        return page

    def prepare_dialog(self, page):
        page.call('Page.enable')
        self.transport.drain_events()
        return page

    def respond_dialog(self, watch, *, action, kind, timeout=10):
        # This is deliberately labeled raw CDP TEST, never official browser_dialog.
        deadline = time.monotonic()+timeout
        while time.monotonic()<deadline:
            events = self.transport.drain_events()
            matched = any(e.get('method')=='Page.javascriptDialogOpening' and
                          e.get('sessionId')==watch.session_id and e.get('params',{}).get('type')==kind for e in events)
            if matched:
                sent=time.monotonic()
                watch.call('Page.handleJavaScriptDialog',{'accept':action=='accept'})
                return {'status':'PASS','evidence':'Raw CDP development test response',
                        'response_owner':'cdp-test','action':action,'sent_at':sent}
            time.sleep(.02)
        raise TimeoutError('test dialog did not open')

    def close(self):
        if self.closed:return self.cleanup
        errors=[]
        for page in reversed(self.pages):
            try:page.close()
            except Exception as exc:errors.append('TAB_'+type(exc).__name__)
        try:self.transport.close()
        except Exception as exc:errors.append('TRANSPORT_'+type(exc).__name__)
        errors.extend(stop_owned(self.proc));self.log.close()
        try:self.profile.cleanup()
        except OSError:errors.append('PROFILE_CLEANUP_UNCONFIRMED')
        self.closed=True
        self.cleanup={'status':'WARNING' if errors else 'PASS','errors':errors}
        return self.cleanup
