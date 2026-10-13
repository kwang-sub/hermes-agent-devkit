"""Small explicit-target browser operations, not a replacement test framework."""
from __future__ import annotations
from dataclasses import dataclass
import json
import math
import time
from urllib.parse import urlsplit
from .capture import TimeBudget, capture
from .suite import EnvironmentBlocked, Unsupported
from .diagnostics import Diagnostics


def origin(url: str) -> tuple:
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('only approved HTTP(S) origins are supported')
    return parsed.scheme, parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80)


@dataclass(frozen=True)
class Locator:
    selector: str = ''
    label: str = ''
    role: str = ''
    name: str = ''

    def expression(self) -> str:
        if sum(bool(v) for v in (self.selector, self.label, self.role)) != 1:
            raise ValueError('provide one selector, label, or role')
        q = json.dumps
        if self.selector:
            return 'Array.from(document.querySelectorAll(' + q(self.selector) + '))'
        if self.label:
            return ("Array.from(document.querySelectorAll('input,textarea,select')).filter(e=>"
                    "[e.getAttribute('aria-label'),...Array.from(e.labels||[]).map(l=>l.textContent.trim())]"
                    '.includes(' + q(self.label) + '))')
        native = {'button': 'button,input[type=button],input[type=submit]', 'link': 'a[href]',
                  'checkbox': 'input[type=checkbox]', 'textbox': 'input:not([type]),input[type=text],textarea',
                  'combobox': 'select', 'tab': '[role=tab]', 'menuitem': '[role=menuitem]'}
        if self.role not in native:
            raise Unsupported('use the project runner for this accessible role')
        selector = native[self.role] + ',[role=' + q(self.role) + ']'
        return ('Array.from(document.querySelectorAll(' + q(selector) + ')).filter(e=>'
                "(e.getAttribute('aria-label')||e.textContent||e.value||'').trim()===" + q(self.name) + ')')


class BrowserPage:
    def __init__(self, transport, target_id: str, session_id: str, *, allowed_origins: list[str],
                 budget: TimeBudget | None = None):
        if not target_id or not session_id or not allowed_origins:
            raise ValueError('explicit owned target, session and origin scope are required')
        self.transport, self.target_id, self.session_id = transport, target_id, session_id
        self.allowed_origins = {origin(url) for url in allowed_origins}
        self.budget = budget or TimeBudget()
        self.viewport_state = {}
        self.closed = False

    def call(self, method: str, params=None, *, timeout=None):
        if self.closed:
            raise EnvironmentBlocked('owned page is closed')
        seconds = self.budget.action if timeout is None else timeout
        session = None if method.startswith(('Target.', 'Browser.')) else self.session_id
        return self.transport.call(method, params or {}, session=session, timeout=seconds,
                                   outer_timeout=self.budget.outer(seconds))

    def evaluate(self, expression: str, *, timeout=None):
        result = self.call('Runtime.evaluate', {'expression': expression, 'returnByValue': True}, timeout=timeout)
        if result.get('exceptionDetails') or result.get('result', {}).get('subtype') == 'error':
            raise RuntimeError('page evaluation failed')
        return result.get('result', {}).get('value')

    def require_origin(self):
        url = self.evaluate('location.href')
        try:
            accepted = origin(url) in self.allowed_origins
        except (TypeError, ValueError):
            accepted = False
        if not accepted:
            raise EnvironmentBlocked('page left the approved origin scope')

    def healthy(self) -> bool:
        try:
            return self.evaluate('1', timeout=2) == 1
        except Exception:
            return False

    def wait(self, predicate, *, timeout=None):
        seconds = self.budget.navigation if timeout is None else timeout
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds <= 0:
            raise ValueError('finite positive wait budget required')
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            value = (self.evaluate(predicate, timeout=min(self.budget.action, remaining))
                     if isinstance(predicate, str) else predicate())
            if value:
                return value
            time.sleep(min(.05, max(0, deadline - time.monotonic())))
        raise TimeoutError('expected UI condition did not become true')

    def activate(self):
        self.require_origin()
        self.call('Target.activateTarget', {'targetId': self.target_id})
        self.call('Page.bringToFront')

    def navigate(self, url: str, *, ready: str):
        if origin(url) not in self.allowed_origins:
            raise EnvironmentBlocked('navigation is outside the approved scope')
        # For dirty forms/dialogs, pre-arm dialog handling and use schedule() instead.
        result = self.call('Page.navigate', {'url': url}, timeout=self.budget.navigation)
        if result.get('errorText'):
            raise EnvironmentBlocked('navigation failed')
        expected = json.dumps(urlsplit(url).path or '/')
        self.wait('location.pathname===' + expected + ' && Boolean(' + ready + ')')
        self.require_origin()

    def schedule(self, expression: str):
        self.require_origin()
        # No synchronous wait for a dialog-blocked navigation. Caller owns response.
        return self.evaluate('setTimeout(()=>{' + expression + '},100); true')

    def wait_route(self, path: str, *, ready='true'):
        self.wait('location.pathname===' + json.dumps(path) + ' && Boolean(' + ready + ')')
        self.require_origin()

    def _element(self, locator: Locator, body: str):
        return self.evaluate('(()=>{const a=' + locator.expression() +
                             ';if(a.length!==1)return null;const e=a[0];' + body + '})()')

    def _point(self, locator: Locator):
        self.require_origin()
        self.activate()
        def ready():
            return self._element(locator, """
                e.scrollIntoView({block:'center',inline:'center'});
                const r=e.getBoundingClientRect(),s=getComputedStyle(e);
                if(e.disabled||e.getAttribute('aria-disabled')==='true'||s.visibility==='hidden'||
                   s.display==='none'||r.width<=0||r.height<=0)return null;
                const x=r.left+r.width/2,y=r.top+r.height/2,hit=document.elementFromPoint(x,y);
                if(!hit||!(e===hit||e.contains(hit)))return null;
                return {x,y};
            """)
        return self.wait(ready, timeout=self.budget.action)

    def click(self, locator: Locator, *, touch=False):
        point = self._point(locator)
        if touch:
            self.call('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [point]})
            self.call('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
        else:
            for kind in ('mousePressed', 'mouseReleased'):
                self.call('Input.dispatchMouseEvent', dict(point, type=kind, button='left', clickCount=1))
        # Never automatically retry the click: it may submit or delete data.

    def press(self, key: str, *, ctrl=False, shift=False):
        self.require_origin()
        keys = {'Tab': 9, 'Enter': 13, 'Escape': 27, 'Backspace': 8, ' ': 32,
                'Home': 36, 'End': 35, 'ArrowLeft': 37, 'ArrowUp': 38, 'ArrowRight': 39, 'ArrowDown': 40}
        if key not in keys and len(key) != 1:
            raise Unsupported('unsupported keyboard key')
        vk = keys.get(key, ord(key.upper()) if len(key) == 1 else 0)
        code = ('Space' if key == ' ' else 'Key'+key.upper() if len(key)==1 and key.isalpha() else key)
        params = {'key': key, 'code': code, 'windowsVirtualKeyCode': vk,
                  'modifiers': (2 if ctrl else 0) | (8 if shift else 0)}
        down = dict(params, type='keyDown')
        if key == 'Enter': down['text'] = '\r'
        self.call('Input.dispatchKeyEvent', down)
        if len(key) == 1 and not ctrl:
            self.call('Input.dispatchKeyEvent', dict(params, type='char', text=key))
        self.call('Input.dispatchKeyEvent', dict(params, type='keyUp'))

    def fill(self, locator: Locator, text: str):
        self.click(locator)
        self.press('a', ctrl=True)
        self.press('Backspace')
        self.call('Input.insertText', {'text': text})
        self.wait(lambda: self._element(locator, 'return e.value;') == text, timeout=self.budget.action)

    def select(self, locator: Locator, value: str):
        """Native select via actual keyboard input; custom menus use click/press."""
        options = self._element(locator, "return e.tagName==='SELECT'?Array.from(e.options).map(o=>({value:o.value,disabled:o.disabled})):null;")
        if options is None:
            raise Unsupported('custom select requires project-specific interaction')
        matches = [i for i, option in enumerate(options) if option['value'] == value and not option['disabled']]
        if len(matches) != 1:
            raise ValueError('select option is missing or ambiguous')
        self._point(locator)
        self._element(locator, 'e.focus();return true;')
        self.press('Home')
        # ArrowDown skips disabled options in native Chromium selects.
        enabled_before = sum(not o['disabled'] for o in options[:matches[0]])
        for _ in range(enabled_before):
            self.press('ArrowDown')
        self.wait(lambda: self._element(locator, 'return e.value;') == value, timeout=self.budget.action)

    def checked(self, locator: Locator, desired: bool):
        current = self._element(locator, 'return e.checked;')
        if type(current) is not bool:
            raise Unsupported('not a native checkbox')
        if current != desired:
            self.click(locator)
        self.wait(lambda: self._element(locator, 'return e.checked;') is desired, timeout=self.budget.action)

    def focused(self, locator: Locator) -> bool:
        return self._element(locator, 'return document.activeElement===e;') is True

    def viewport(self, width: int, height: int, *, mobile=False, touch=False, scale=1):
        if type(width) is not int or type(height) is not int or width <= 0 or height <= 0:
            raise ValueError('positive viewport dimensions required')
        if type(mobile) is not bool or type(touch) is not bool or not math.isfinite(scale) or scale <= 0:
            raise ValueError('invalid viewport mode')
        self.call('Emulation.setDeviceMetricsOverride', {'width': width, 'height': height,
                   'deviceScaleFactor': scale, 'mobile': mobile})
        self.call('Emulation.setTouchEmulationEnabled', {'enabled': touch, 'maxTouchPoints': 1})
        self.viewport_state = {'width': width, 'height': height, 'device_scale_factor': scale,
                               'mobile': mobile, 'touch': touch,
                               'scope': 'mobile-emulation' if mobile or touch else 'layout-viewport'}
        return self.viewport_state

    def screenshot(self, directory, **kwargs):
        return capture(self, directory, **kwargs)

    def accessibility_snapshot(self):
        self.require_origin()
        return self.call('Accessibility.getFullAXTree')

    def layout_observation(self):
        return self.evaluate("({width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,scrollHeight:document.documentElement.scrollHeight})")

    def timing_observation(self):
        return self.evaluate("(()=>{const n=performance.getEntriesByType('navigation')[0];return n?{dom_ms:n.domContentLoadedEventEnd,load_ms:n.loadEventEnd,response_ms:n.responseEnd}:null})()")

    def start_diagnostics(self):
        self._diagnostics = Diagnostics(self.session_id)
        self._diagnostic_errors = []
        for method in ('Network.enable', 'Log.enable'):
            try: self.call(method)
            except Exception as exc: self._diagnostic_errors.append(type(exc).__name__)

    def collect_diagnostics(self):
        if not hasattr(self, '_diagnostics'):
            return {'status': 'NOT_RUN'}
        try:
            for event in self.transport.drain_events(): self._diagnostics.feed(event)
        except Exception as exc:
            self._diagnostic_errors.append(type(exc).__name__)
        result = self._diagnostics.snapshot()
        result['collector_errors'] = list(self._diagnostic_errors)
        self._diagnostics.records.clear(); self._diagnostics.dropped = 0
        self._diagnostic_errors.clear()
        return result

    def wait_visual(self, *, fonts=False, images_selector=None):
        # Opt-in only; do not make irrelevant resources a global readiness gate.
        if fonts: self.wait("!document.fonts || document.fonts.status==='loaded'")
        if images_selector:
            self.wait('Array.from(document.querySelectorAll('+json.dumps(images_selector)+')).every(e=>e.complete && e.naturalWidth>0)')

    def close(self):
        if not self.closed:
            result = self.call('Target.closeTarget', {'targetId': self.target_id})
            if result.get('success') is not True:
                raise EnvironmentBlocked('owned tab close was not confirmed')
            self.closed = True
