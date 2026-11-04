"""Read-only browser preflight and owned cleanup for known Hermes runtimes.

New Hermes launches Chromium directly; the older runtime uses agent-browser.
Neither path installs a dependency or switches the configured browser provider.
"""
from __future__ import annotations

from importlib import import_module
import os
from pathlib import Path

from .suite import EnvironmentBlocked


class HermesRuntime:
    def __init__(self):
        try:
            self.session = import_module('tools.browser_session')
        except ModuleNotFoundError as exc:
            if exc.name != 'tools.browser_session':
                raise  # An installed module's broken dependency is not a legacy runtime.
            self.native = False
            self.session = import_module('tools.browser_tool_session')
        else:
            self.native = True
        prefix = 'tools.browser_session_' if self.native else 'tools.browser_tool_'
        self.cloud = import_module(prefix + 'cloud')
        self.cdp = import_module(prefix + 'cdp')
        self.cli = import_module('tools.browser_use_cli')

    def require_managed(self):
        if self.native:
            cfg = self.cloud.browser_section()
        else:
            from hermes_cli.config import read_raw_config
            cfg = (read_raw_config() or {}).get('browser', {}) or {}
        overrides = ('BU_CDP_URL', 'BU_CDP_WS', 'BROWSER_CDP_URL', 'BU_AUTOSPAWN',
                     'BROWSER_USE_API_KEY', 'BROWSERBASE_API_KEY', 'FIRECRAWL_API_KEY', 'CAMOFOX_URL')
        if (any(os.environ.get(key) for key in overrides)
                or cfg.get('cdp_url') or cfg.get('use_gateway') or cfg.get('use_real_profile')
                or cfg.get('user_data_dir')
                or cfg.get('backend') not in (None, '', 'browser-use')
                or cfg.get('engine') not in (None, '', 'auto', 'chromium', 'chrome')):
            raise EnvironmentBlocked('probe requires an isolated managed Chromium; keep external/shared browser settings unchanged')
        provider = self.cloud.get_cloud_provider if self.native else self.cloud._get_cloud_provider
        if provider() is not None:
            raise EnvironmentBlocked('cloud browser is configured; use the approved project runner')
        if self.native:
            if self.cdp.get_cdp_override_raw():
                raise EnvironmentBlocked('live CDP override is configured; no replacement browser will be started')
            desktop = import_module('tools.bot_desktop.runtime')
            if desktop.published_env().get('DISPLAY'):
                raise EnvironmentBlocked('Bot Desktop shares its browser profile; use an isolated probe environment')
            placement = import_module('tools.bot_desktop.placement')
            if placement.resolve().where != placement.GATEWAY:
                raise EnvironmentBlocked('browser placement is not the local host; use the approved project runner')
            if self.cloud.is_headed_mode() and desktop._should_auto_start(os.environ):
                raise EnvironmentBlocked('headed browser would start a shared Bot Desktop; use an isolated probe environment')
            launcher = import_module('tools.browser_launcher')
            executable = launcher._resolve_executable()  # chromium_ready() may auto-install.
            label = 'Chromium'
        else:
            install = import_module('tools.browser_tool_install')
            executable = install._find_agent_browser(validate=False)
            label = 'agent-browser'
        if not executable or not Path(executable).is_file():
            raise EnvironmentBlocked(f'installed {label} is required; no automatic dependency install')
        if not self.cli._find_cli():
            raise EnvironmentBlocked('installed browser-harness is required; no automatic dependency install')

    def dialog_policy_evidence(self, socket_dir):
        getter = self.cdp.get_dialog_policy_config if self.native else self.cdp._get_dialog_policy_config
        policy, _ = getter()
        if policy != 'must_respond':
            raise EnvironmentBlocked('explicit dialog probe requires browser.dialog_policy=must_respond')
        evidence = {'managed_dialog_backend': 'native-cdp' if self.native else 'legacy-agent-browser',
                    'configured_dialog_policy': policy}
        if not self.native:
            effective = self.session._agent_browser_command_env(str(socket_dir))
            value = effective.get('AGENT_BROWSER_NO_AUTO_DIALOG')
            if value != '1':
                raise EnvironmentBlocked('managed launch policy patch is absent; no retry of product task')
            evidence['effective_no_auto_dialog'] = value
        return evidence

    def cleanup_owned(self, task_id, session_name):
        """Clean only this generated task/session and verify its tracked owners are gone."""
        if not task_id or not session_name:
            raise ValueError('explicit task and named session are required for cleanup')
        if self.native:
            lifecycle = import_module('tools.browser_session_lifecycle')
            # browser_exec keys named browsers by session, not by task_id. The upstream
            # owner resolver also handles profile tags and the local sidecar suffix.
            key = self.cli._backend_cache_key(task_id, session_name)
            owners = {task_id, self.session.owner_task_id(key)}
            for owner in sorted(owners):
                lifecycle.cleanup_browser(owner)
            remaining = self.session._active_sessions.copy()
            return not any(self.session.owner_task_id(key) in owners for key in remaining)
        lifecycle = import_module('tools.browser_tool_lifecycle')
        lifecycle.cleanup_browser(task_id)
        sessions = getattr(import_module('tools.browser_tool'), '_active_sessions', None)
        return sessions is not None and not any(key in sessions for key in (task_id, task_id + '::local'))
