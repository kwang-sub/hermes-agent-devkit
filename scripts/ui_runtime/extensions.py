"""Opt-in UI capabilities. No automatic dependency installs or global permissions."""
from __future__ import annotations
from pathlib import Path
import json
import time
from .artifacts import file_digest, inside
from .browser import BrowserPage, Locator, origin
from .suite import EnvironmentBlocked, Unsupported


class OptionalOperations:
    def __init__(self, page: BrowserPage, *, enabled=(), owner=None):
        self.page, self.enabled, self.owner = page, set(enabled), owner

    def require(self, feature):
        if feature not in self.enabled:
            raise Unsupported('capability was not requested in the approved test plan')
        self.page.require_origin()

    def upload(self, locator: Locator, files: list[Path], *, approved_root: Path):
        self.require('upload')
        paths = [inside(approved_root, p) for p in files]
        if not paths or any(not p.is_file() for p in paths):
            raise ValueError('approved upload files must exist')
        object_id = self._node(locator, file_input=True)
        try:
            self.page.call('DOM.setFileInputFiles', {'files': [str(p) for p in paths], 'objectId': object_id})
            self.page.wait(lambda: self.page._element(locator, 'return e.files.length;') == len(paths))
        finally:
            self.page.call('Runtime.releaseObject', {'objectId': object_id})
        return {'status': 'PASS', 'evidence': 'Native file input contains the expected file count', 'count': len(paths)}

    def _node(self, locator, *, file_input=False):
        expression = ('(()=>{const a=' + locator.expression() + ';if(a.length!==1)return null;'
                      'const e=a[0];' + ("if(e.type!=='file')return null;" if file_input else '') + 'return e;})()')
        result = self.page.call('Runtime.evaluate', {'expression': expression, 'returnByValue': False})
        object_id = result.get('result', {}).get('objectId')
        if not object_id:
            raise Unsupported('unique supported DOM input was not found')
        return object_id

    def prepare_downloads(self, directory: Path):
        self.require('download')
        context = getattr(self.page, 'context_id', None)
        if not context:
            raise Unsupported('download behavior requires an owned isolated browser context')
        directory = directory.resolve()
        directory.mkdir(parents=True, exist_ok=False)
        self.page.call('Browser.setDownloadBehavior', {'behavior': 'allow',
                       'browserContextId': context, 'downloadPath': str(directory), 'eventsEnabled': True})
        self.download_dir = directory
        return directory

    def wait_download(self, filename: str, *, expected_sha256: str | None = None, timeout=30):
        self.require('download')
        if not hasattr(self, 'download_dir'):
            raise Unsupported('download context has not been prepared')
        if expected_sha256 is not None and len(expected_sha256) != 64:
            raise ValueError('invalid expected checksum')
        path = inside(self.download_dir, self.download_dir / filename)
        deadline = time.monotonic() + timeout
        # Chrome completes by renaming .crdownload. Exact content is then checked.
        while time.monotonic() < deadline:
            if path.is_file() and not Path(str(path)+'.crdownload').exists():
                digest = file_digest(path)
                return {'status': 'PASS' if expected_sha256 is None or digest == expected_sha256 else 'FAIL',
                        'evidence': 'Completed download artifact verified',
                        'content_verification': ('NOT_RUN' if expected_sha256 is None else 'PASS' if digest == expected_sha256 else 'FAIL'),
                        'path': str(path), 'sha256': digest, 'size': path.stat().st_size}
            time.sleep(.05)
        raise TimeoutError('download did not complete within its budget')

    def popup(self, expected_url: str, *, ready='true') -> BrowserPage:
        self.require('popup')
        if self.owner is None or origin(expected_url) not in self.page.allowed_origins:
            raise Unsupported('popup needs an owned lifecycle and approved origin')
        def find():
            rows = self.page.call('Target.getTargets')['targetInfos']
            matches = [t for t in rows if t.get('type') == 'page' and t.get('openerId') == self.page.target_id
                       and t.get('url') == expected_url]
            if len(matches) > 1:
                raise EnvironmentBlocked('ambiguous owned popup')
            return matches[0] if matches else None
        target = self.page.wait(find)
        sid = self.page.call('Target.attachToTarget', {'targetId': target['targetId'], 'flatten': True})['sessionId']
        child = BrowserPage(self.page.transport, target['targetId'], sid,
                            allowed_origins=[expected_url], budget=self.page.budget)
        child.context_id = getattr(self.page, 'context_id', None)
        self.owner.pages.append(child)
        child.call('Page.enable'); child.wait(ready); child.require_origin()
        return child

    def frame(self, locator: Locator):
        self.require('frame')
        object_id = self._node(locator)
        try:
            node = self.page.call('DOM.describeNode', {'objectId': object_id})['node']
            frame_id = node.get('frameId')
            if not frame_id:
                raise Unsupported('locator is not a frame owner')
        finally:
            self.page.call('Runtime.releaseObject', {'objectId': object_id})
        tree = self.page.call('Page.getFrameTree')['frameTree']
        stack = [tree]; match = None
        while stack:
            current = stack.pop()
            if current['frame']['id'] == frame_id: match = current['frame']; break
            stack.extend(current.get('childFrames', []))
        if not match:
            raise Unsupported('out-of-process frame needs the project provider frame adapter')
        inherited = match.get('url') in ('about:srcdoc', 'about:blank')
        if not inherited and origin(match['url']) not in self.page.allowed_origins:
            raise EnvironmentBlocked('frame is outside the approved origin')
        world = self.page.call('Page.createIsolatedWorld', {'frameId': frame_id, 'worldName': 'devkit-ui-read'})
        return FrameView(self.page, locator, world['executionContextId'], inherited=inherited)

    def clipboard_roundtrip(self, sample: str):
        self.require('clipboard')
        context = getattr(self.page, 'context_id', None)
        if not context or not getattr(self.owner, 'disposable', False):
            raise Unsupported('clipboard requires a disposable browser and owned context')
        url = self.page.evaluate('location.origin')
        # Explicit opt-in only. Never read a pre-existing OS clipboard value.
        self.page.call('Browser.grantPermissions', {'origin': url, 'browserContextId': context,
                       'permissions': ['clipboardReadWrite', 'clipboardSanitizedWrite']})
        try:
            expression = ('(async()=>{await navigator.clipboard.writeText(' + json.dumps(sample) + ');'
                          'const ok=(await navigator.clipboard.readText())===' + json.dumps(sample) +
                          ';if(ok)await navigator.clipboard.writeText("");return ok;})()')
            result = self.page.call('Runtime.evaluate', {'expression': expression, 'awaitPromise': True, 'returnByValue': True})
            if result.get('exceptionDetails'):
                raise Unsupported('clipboard API is unavailable in this context')
            ok = result.get('result', {}).get('value') is True
            return {'status': 'PASS' if ok else 'FAIL', 'evidence': 'Owned sample clipboard roundtrip compared'}
        finally:
            self.page.call('Browser.resetPermissions', {'browserContextId': context})


class FrameView(BrowserPage):
    """A same-process frame, with explicit world and outer-page input coordinates."""
    def __init__(self, parent, locator, context, *, inherited=False):
        self.__dict__.update(parent.__dict__)
        self.parent, self.frame_locator, self.world = parent, locator, context
        self.inherited = inherited

    def evaluate(self, expression, *, timeout=None):
        result = self.call('Runtime.evaluate', {'expression': expression, 'contextId': self.world, 'returnByValue': True}, timeout=timeout)
        if result.get('exceptionDetails'):
            raise EnvironmentBlocked('frame changed or evaluation failed; re-resolve the frame')
        return result.get('result', {}).get('value')

    def require_origin(self):
        self.parent.require_origin()
        if not self.inherited:
            super().require_origin()

    def _point(self, locator):
        self.parent._point(self.frame_locator)
        point = super()._point(locator)
        offset = self.parent._element(self.frame_locator, 'const r=e.getBoundingClientRect();return {x:r.left+e.clientLeft,y:r.top+e.clientTop};')
        return {'x': point['x']+offset['x'], 'y': point['y']+offset['y']}

    def viewport(self, *args, **kwargs):
        raise Unsupported('viewport belongs to the parent page')

    def navigate(self, *args, **kwargs):
        raise Unsupported('navigate the frame through its approved UI and re-resolve its context')

    def screenshot(self, *args, **kwargs):
        raise Unsupported('capture the owned parent page or use the existing frame screenshot provider')

    def close(self):
        # It does not own the parent's tab. Contexts are released with the page.
        return None
