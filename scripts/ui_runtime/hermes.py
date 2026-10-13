"""Installed Hermes transport: all browser commands go through browser_exec.

Responses travel through per-call files, not truncated/base64 tool stdout. The
same Python process owns the task-scoped Supervisor and official browser_dialog.
"""
from __future__ import annotations
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import uuid
from .browser import BrowserPage, origin
from .capture import TimeBudget
from .suite import EnvironmentBlocked


class HermesBrowser:
    def __init__(self, *, task_id: str, allowed_origins: list[str], budget=None):
        from tools.browser_use_cli import browser_exec
        from tools.browser_dialog_tool import browser_dialog
        from tools.browser_supervisor import SUPERVISOR_REGISTRY
        from hermes_cli.config import read_raw_config
        from tools.browser_tool_cloud import _get_cloud_provider
        from tools.browser_tool_install import _find_agent_browser
        executable = _find_agent_browser(validate=False)
        if not executable or not Path(executable).is_file():
            raise EnvironmentBlocked('installed agent-browser is required; no automatic dependency install')
        cfg = (read_raw_config() or {}).get('browser', {}) or {}
        overrides = ('BU_CDP_URL', 'BU_CDP_WS', 'BROWSER_CDP_URL', 'BU_AUTOSPAWN', 'CAMOFOX_URL')
        if (any(os.environ.get(k) for k in overrides) or _get_cloud_provider() is not None
                or cfg.get('cdp_url') or cfg.get('use_real_profile') or cfg.get('use_gateway')
                or cfg.get('backend') not in (None, '', 'browser-use')
                or cfg.get('engine') not in (None, '', 'auto', 'chromium', 'chrome')):
            raise EnvironmentBlocked('use the approved project runner for a non-managed browser')
        self.execute, self.dialog, self.registry = browser_exec, browser_dialog, SUPERVISOR_REGISTRY
        self.session = 'ui-' + uuid.uuid4().hex[:20]
        self.task_id = task_id + '-' + self.session
        self.allowed_origins = list(allowed_origins)
        self.budget = budget or TimeBudget()
        self.exchange = tempfile.TemporaryDirectory(prefix='devkit-ui-exchange-')
        self.lock = threading.RLock()
        self.pages = []
        self.context_ids = []
        self.closed = False

    def _expression(self, expression: str, outer_timeout: float):
        if self.closed:
            raise EnvironmentBlocked('browser transport is closed')
        request = uuid.uuid4().hex
        path = Path(self.exchange.name) / (request + '.json')
        code = ('# Execute scoped UI verification command\nimport json\nfrom pathlib import Path\n'
                '_value = ' + expression + '\nPath(' + repr(str(path)) + ').write_text('
                'json.dumps({"request":' + repr(request) + ',"result":_value}), encoding="utf-8")\n'
                'print("UI_COMMAND_COMPLETED")')
        with self.lock:
            try:
                response = self.execute(code=code, session=self.session, task_id=self.task_id,
                                        timeout_s=math.ceil(outer_timeout))
                response = json.loads(response) if isinstance(response, str) else response
                if not isinstance(response, dict) or response.get('success') is not True:
                    raise EnvironmentBlocked('Hermes browser command failed')
                if not path.is_file():
                    raise EnvironmentBlocked('browser response artifact missing')
                value = json.loads(path.read_text(encoding='utf-8'))
                if value.get('request') != request:
                    raise EnvironmentBlocked('browser response request mismatch')
                return value['result']
            finally:
                path.unlink(missing_ok=True)

    def call(self, method, params, *, session=None, timeout=10, outer_timeout=None):
        expression = ('cdp(' + repr(method) + ', session_id=' + repr(session) +
                      ', _response_timeout=' + repr(float(timeout)) + ', **' + repr(params) + ')')
        return self._expression(expression, outer_timeout or self.budget.outer(timeout))

    def open(self, url: str, *, ready: str, isolated_context=False):
        if origin(url) not in {origin(x) for x in self.allowed_origins}:
            raise EnvironmentBlocked('target is outside the approved origin')
        # A URL literal establishes Hermes's normal local/private routing first.
        self._expression((repr(url) if isolated_context else 'new_tab(' + repr(url) + ')'),
                         self.budget.outer(self.budget.navigation))
        info = self._expression('current_tab()', self.budget.outer(self.budget.action))
        target = info.get('targetId') or info.get('target_id')
        # Optional downloads/popups can use an isolated context, never global permissions.
        if isolated_context:
            context = self.call('Target.createBrowserContext', {}).get('browserContextId')
            if not context:
                raise EnvironmentBlocked('isolated browser context was not created')
            self.context_ids.append(context)
            target = self.call('Target.createTarget', {'url': url, 'browserContextId': context})['targetId']
        session = self.call('Target.attachToTarget', {'targetId': target, 'flatten': True})['sessionId']
        page = BrowserPage(self, target, session, allowed_origins=self.allowed_origins, budget=self.budget)
        page.context_id = self.context_ids[-1] if isolated_context else None
        self.pages.append(page)
        page.call('Page.enable')
        page.call('Runtime.enable')
        page.start_diagnostics()
        page.wait('Boolean(' + ready + ')')
        page.require_origin()
        return page

    def prepare_dialog(self, page: BrowserPage):
        """Focus exactly one owned page before triggering a blocking native dialog."""
        page.require_origin()
        url = page.evaluate('location.href')
        targets = self.call('Target.getTargets', {})['targetInfos']
        matches = [t for t in targets if t.get('type') == 'page' and t.get('url') == url]
        if len(matches) != 1 or matches[0].get('targetId') != page.target_id:
            raise EnvironmentBlocked('dialog response page is ambiguous')
        supervisor = self.registry.get(self.task_id)
        if supervisor is None:
            raise EnvironmentBlocked('task supervisor is missing')
        parsed = origin(url)
        base = f'{parsed[0]}://{parsed[1]}' + (':' + str(parsed[2]) if parsed[2] not in (80,443) else '')
        focused = supervisor.focus_page(base, accept='location.href===' + json.dumps(url), timeout=self.budget.action)
        if focused.get('ok') is not True:
            raise EnvironmentBlocked('dialog owner could not be focused')
        frame = page.call('Page.getFrameTree')['frameTree']['frame']['id']
        return supervisor, frame

    def respond_dialog(self, watch, *, action: str, kind: str, timeout=10):
        if action not in ('accept', 'dismiss'):
            raise ValueError('unsupported dialog action')
        supervisor, frame = watch
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            dialogs = [d for d in supervisor.snapshot().pending_dialogs if d.type == kind
                       and (getattr(d, 'frame_id', None) in (None, frame))]
            if len(dialogs) > 1:
                raise EnvironmentBlocked('ambiguous pending dialog')
            if dialogs:
                dialog = dialogs[0]
                sent = time.monotonic()
                response = self.dialog(action=action, dialog_id=dialog.id, task_id=self.task_id)
                response = json.loads(response) if isinstance(response, str) else response
                if response.get('success') is not True:
                    raise EnvironmentBlocked('official dialog response failed')
                return {'status': 'PASS', 'evidence': 'Official response accepted for pending dialog',
                        'response_owner': 'hermes.browser_dialog', 'dialog_id': dialog.id,
                        'action': action, 'sent_at': sent}
            time.sleep(.03)
        raise TimeoutError('no pending owned dialog')

    def drain_events(self):
        return self._expression('drain_events()', self.budget.outer(self.budget.action))

    def close(self):
        if self.closed:
            return self.cleanup
        errors = []
        for page in reversed(self.pages):
            try: page.close()
            except Exception as exc: errors.append('TAB_' + type(exc).__name__)
        for context in reversed(self.context_ids):
            try: self.call('Target.disposeBrowserContext', {'browserContextId': context})
            except Exception as exc: errors.append('CONTEXT_' + type(exc).__name__)
        supervisor = self.registry.get(self.task_id)
        if supervisor is not None:
            try: supervisor.stop()
            except Exception as exc: errors.append('SUPERVISOR_' + type(exc).__name__)
        try:
            from tools import browser_use_cli as cli
            command = cli._find_cli()
            names = {self.session}
            resolver = getattr(cli, '_sidecar_daemon_name', None)
            if callable(resolver): names.add(resolver(self.session))
            for name in names:
                env = dict(os.environ, BU_NAME=name)
                try:
                    done = subprocess.run([*command, '--reload'], env=env, timeout=12,
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    if done.returncode: errors.append('HARNESS_RELOAD_NONZERO')
                except Exception as exc:
                    errors.append('HARNESS_' + type(exc).__name__)
            from tools.browser_tool_lifecycle import cleanup_browser
            cleanup_browser(self.task_id)  # Exact task only, never all browser sessions.
            from tools import browser_tool
            sessions = getattr(browser_tool, '_active_sessions', None)
            if sessions is None or any(k in sessions for k in (self.task_id, self.task_id+'::local')):
                errors.append('BROWSER_SESSION_CLEANUP_UNCONFIRMED')
        except Exception as exc:
            errors.append('BROWSER_CLEANUP_' + type(exc).__name__)
        self.closed = True
        try: self.exchange.cleanup()
        except OSError as exc: errors.append('EXCHANGE_' + type(exc).__name__)
        self.cleanup = {'status': 'WARNING' if errors else 'PASS', 'errors': errors}
        return self.cleanup
