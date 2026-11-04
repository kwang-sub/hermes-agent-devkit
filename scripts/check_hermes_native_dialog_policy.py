#!/usr/bin/env python3
"""Verify the direct-Chromium replacement for the retired agent-browser layer.

Check the installed call path and exercise its real dialog handlers with an
in-memory CDP transport. No browser, network, model, or user configuration is used.
"""
from __future__ import annotations

import ast
import asyncio
import logging
from pathlib import Path
import sys
import threading
import types
from unittest.mock import patch


def function(tree: ast.AST, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    matches = [node for node in ast.walk(tree)
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name]
    if len(matches) != 1:
        raise RuntimeError(f"native browser function is missing or ambiguous: {name}")
    return matches[0]


def require_call(node: ast.AST, name: str) -> ast.Call:
    matches = [child for child in ast.walk(node) if isinstance(child, ast.Call)
               and ast.unparse(child.func) == name]
    if len(matches) != 1:
        raise RuntimeError(f"native browser call is missing or ambiguous: {name}")
    return matches[0]


def require_keyword(call: ast.Call, name: str, expression: str) -> None:
    values = [item.value for item in call.keywords if item.arg == name]
    expected = ast.parse(expression, mode="eval").body
    if len(values) != 1 or ast.dump(values[0]) != ast.dump(expected):
        raise RuntimeError(f"native dialog argument forwarding changed: {name}")


def isolated_function(node: ast.FunctionDef, globals_: dict | None = None):
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
                             node], type_ignores=[])
    namespace = {"logger": logging.getLogger(__name__), **(globals_ or {})}
    exec(compile(ast.fix_missing_locations(module), "<installed-hermes-function>", "exec"), namespace)
    return namespace[node.name]


def verify_config_forwarding(cdp: ast.AST, cli: ast.AST, dialogs: types.ModuleType) -> None:
    """Run the installed config reader and attach function, replacing only their I/O."""
    read_policy = isolated_function(function(cdp, "get_dialog_policy_config"))
    attach = isolated_function(function(cli, "_attach_vault_supervisor"))
    config = {}
    calls = []
    cloud = types.ModuleType("tools.browser_session_cloud")
    cloud.browser_cfg = lambda key, default: config.get(key, default)
    cdp_module = types.ModuleType("tools.browser_session_cdp")
    cdp_module.get_dialog_policy_config = read_policy
    cdp_module.resolve_cdp_override = lambda value: value
    supervisor = types.ModuleType("tools.browser_supervisor")
    supervisor.SUPERVISOR_REGISTRY = types.SimpleNamespace(get_or_start=lambda **kwargs: calls.append(kwargs))
    modules = {"tools": types.ModuleType("tools"), "tools.browser_session_cloud": cloud,
               "tools.browser_session_cdp": cdp_module, "tools.browser_supervisor": supervisor,
               "tools.browser_supervisor_dialogs": dialogs}
    with patch.dict(sys.modules, modules):
        for requested in (None, "invalid", "must_respond", "auto_dismiss", "auto_accept"):
            config.clear()
            if requested is not None:
                config["dialog_policy"] = requested
            config["dialog_timeout_s"] = 17
            expected = requested if requested in ("must_respond", "auto_dismiss", "auto_accept") else "must_respond"
            calls.clear()
            attach({"BU_CDP_WS": "ws://127.0.0.1/devkit-contract"}, "devkit-contract")
            if calls != [{"task_id": "devkit-contract", "cdp_url": "ws://127.0.0.1/devkit-contract",
                          "dialog_policy": expected, "dialog_timeout_s": 17.0}]:
                raise RuntimeError("native browser dialog policy is not forwarded to its supervisor")


def supervisor_class(tree: ast.AST) -> ast.ClassDef:
    matches = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "CDPSupervisor"
               and any(ast.unparse(base) == "DialogSupervisionMixin" for base in node.bases)]
    if len(matches) != 1:
        raise RuntimeError("native supervisor no longer uses the verified dialog handlers")
    return matches[0]


def supervisor_globals(dialogs: types.ModuleType) -> dict:
    return {"threading": threading, "_VALID_POLICIES": dialogs._VALID_POLICIES,
            "DEFAULT_DIALOG_POLICY": dialogs.DEFAULT_DIALOG_POLICY,
            "DEFAULT_DIALOG_TIMEOUT_S": dialogs.DEFAULT_DIALOG_TIMEOUT_S}


def verify_supervisor_wiring(tree: ast.AST, dialogs: types.ModuleType) -> None:
    cls = supervisor_class(tree)
    bindings = [node.value for node in cls.body if isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name) and node.target.id == "_EVENT_HANDLERS"]
    bindings += [node.value for node in cls.body if isinstance(node, ast.Assign)
                 and any(isinstance(target, ast.Name) and target.id == "_EVENT_HANDLERS" for target in node.targets)]
    expected = ast.parse("{**DialogSupervisionMixin.EVENT_HANDLERS, **FrameTrackingMixin.EVENT_HANDLERS}", mode="eval").body
    if len(bindings) != 1 or ast.dump(bindings[0]) != ast.dump(expected):
        raise RuntimeError("native supervisor dialog event wiring changed")
    for event, method in (("Page.javascriptDialogOpening", "_on_dialog_opening"),
                          ("Page.javascriptDialogClosed", "_on_dialog_closed")):
        if dialogs.DialogSupervisionMixin.EVENT_HANDLERS.get(event) is not getattr(dialogs.DialogSupervisionMixin, method):
            raise RuntimeError("native supervisor dialog event wiring changed")

    calls = []

    class RecordingSupervisor:
        def __init__(self, **kwargs):
            calls.append(kwargs)

        def start(self, timeout):
            pass  # The installed registry is exercised without starting a browser/socket.

    create = isolated_function(function(tree, "get_or_start"),
                               {**supervisor_globals(dialogs), "CDPSupervisor": RecordingSupervisor})
    constants = types.ModuleType("hermes_constants")
    constants.hermes_home_key = lambda: "devkit-contract-home"
    with patch.dict(sys.modules, {"hermes_constants": constants}):
        for policy in ("must_respond", "auto_dismiss", "auto_accept"):
            calls.clear()
            registry = types.SimpleNamespace(_lock=threading.Lock(), _by_task={}, _home_by_task={})
            create(registry, "devkit-contract", "ws://127.0.0.1/devkit-contract",
                   dialog_policy=policy, dialog_timeout_s=17.0)
            if calls != [{"task_id": "devkit-contract", "cdp_url": "ws://127.0.0.1/devkit-contract",
                          "dialog_policy": policy, "dialog_timeout_s": 17.0}]:
                raise RuntimeError("native registry does not forward the dialog policy to its supervisor")


async def verify_responses(dialogs: types.ModuleType, supervisor: ast.AST) -> None:
    """Use the installed mixin; record native responses instead of opening a socket."""
    if dialogs.DEFAULT_DIALOG_POLICY != "must_respond":
        raise RuntimeError("native browser default no longer requires an explicit response")

    class Probe(dialogs.DialogSupervisionMixin):
        async def _cdp(self, method, params, *, session_id, timeout):
            self.calls.append((method, params, session_id))

    Probe.__init__ = isolated_function(function(supervisor_class(supervisor), "__init__"), supervisor_globals(dialogs))
    for kind in ("beforeunload", "confirm"):
        for policy, accept in (("must_respond", False), ("must_respond", True),
                               ("auto_dismiss", False), ("auto_accept", True)):
            probe = Probe("devkit-contract", "ws://127.0.0.1/devkit-contract", dialog_policy=policy)
            probe.calls = []
            try:
                await probe._on_dialog_opening({"type": kind}, "devkit-session")
                await asyncio.sleep(0)
                if policy == "must_respond":
                    if probe.calls or len(probe._pending_dialogs) != 1:
                        raise RuntimeError("native dialog was answered before an explicit response")
                    dialog = next(iter(probe._pending_dialogs.values()))
                    await probe._handle_dialog_cdp(dialog, accept=accept, prompt_text="")
                expected = [("Page.handleJavaScriptDialog", {"accept": accept}, "devkit-session")]
                if probe.calls != expected or probe._pending_dialogs:
                    raise RuntimeError("native accept/dismiss behavior changed")
            finally:
                for handle in probe._dialog_watchdogs.values():
                    handle.cancel()


def check(root: Path) -> None:
    files = {name: root / "tools" / (name + ".py") for name in (
        "browser_session", "browser_launcher", "browser_session_cdp", "browser_use_cli",
        "browser_supervisor", "browser_supervisor_dialogs", "browser_dialog_tool")}
    trees = {name: ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
             for name, path in files.items()}
    # A missing legacy file alone is never evidence that the replacement is safe.
    require_call(function(trees["browser_session"], "_create_chromium_session"), "launch_chromium")
    require_call(function(trees["browser_launcher"], "launch_chromium"), "_launch_owned")
    require_call(function(trees["browser_launcher"], "_launch_owned"), "_spawn")
    require_call(function(trees["browser_launcher"], "_spawn"), "subprocess.Popen")
    dispatch = function(trees["browser_use_cli"], "dispatch")
    attach = require_call(dispatch, "_attach_vault_supervisor")
    execute = require_call(dispatch, "_run_cli_killing_process_group")
    if attach.lineno >= execute.lineno:
        raise RuntimeError("native supervisor must attach before browser code executes")
    supervisor_class(trees["browser_supervisor"])
    response = require_call(function(trees["browser_dialog_tool"], "browser_dialog"), "supervisor.respond_to_dialog")
    require_keyword(response, "action", "action")
    response = require_call(function(trees["browser_supervisor"], "respond_to_dialog"), "self._handle_dialog_cdp")
    require_keyword(response, "accept", "action == 'accept'")

    name = "_devkit_installed_dialog_contract"
    module = types.ModuleType(name)
    module.__file__ = str(files["browser_supervisor_dialogs"])
    with patch.dict(sys.modules, {name: module}):
        exec(compile(trees["browser_supervisor_dialogs"], module.__file__, "exec"), module.__dict__)
        verify_supervisor_wiring(trees["browser_supervisor"], module)
        verify_config_forwarding(trees["browser_session_cdp"], trees["browser_use_cli"], module)
        asyncio.run(verify_responses(module, trees["browser_supervisor"]))
