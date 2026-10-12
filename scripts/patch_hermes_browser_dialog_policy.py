#!/usr/bin/env python3
"""Align managed agent-browser dialogs with Hermes's explicit-response policy.

Patches only the managed launch environment after PM environment preparation.
Does not replace native dialogs, modify an existing browser, or install software.
"""
from __future__ import annotations

import argparse
import ast
from pathlib import Path
import tempfile

MARKER = "DEVKIT_MANAGED_DIALOG_POLICY_V1"
FUNCTION = "_agent_browser_command_env"
ANCHOR = '    env["AGENT_BROWSER_SOCKET_DIR"] = socket_dir\n'
INSERT = '''    # DEVKIT_MANAGED_DIALOG_POLICY_V1: the supervisor owns explicit responses.
    from tools.browser_tool_cdp import _get_dialog_policy_config
    _devkit_dialog_policy, _ = _get_dialog_policy_config()
    if _devkit_dialog_policy in ("must_respond", "auto_dismiss"):
        env["AGENT_BROWSER_NO_AUTO_DIALOG"] = "1"
'''


def patch_source(source: str) -> str:
    """Patch one verified function; reject drift instead of guessing an anchor."""
    tree = ast.parse(source)
    funcs = [node for node in tree.body if isinstance(node, ast.FunctionDef)
             and node.name == FUNCTION]
    if len(funcs) != 1:
        raise RuntimeError("managed browser launch function is missing or ambiguous")
    func = funcs[0]
    lines = source.splitlines(keepends=True)
    body = "".join(lines[func.lineno - 1:func.end_lineno])
    if MARKER in source:
        if body.count(INSERT.rstrip()) != 1 or source.count(MARKER) != 1:
            raise RuntimeError("existing dialog policy patch is partial or changed")
        return source
    if "AGENT_BROWSER_NO_AUTO_DIALOG" in body:
        raise RuntimeError("upstream already defines a managed dialog policy; review compatibility")
    if body.count(ANCHOR) != 1:
        raise RuntimeError("managed browser environment anchor changed")
    replaced = body.replace(ANCHOR, ANCHOR + INSERT, 1)
    lines[func.lineno - 1:func.end_lineno] = [replaced]
    updated = "".join(lines)
    ast.parse(updated)
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hermes-root", type=Path, default=Path("/opt/hermes"))
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    path = args.hermes_root / "tools/browser_tool_session.py"
    try:
        source = path.read_text(encoding="utf-8")
        updated = patch_source(source)
        if args.check_only:
            if updated != source:
                raise RuntimeError("managed dialog policy patch is not installed")
        elif updated != source:
            # Keep the original permission bits; replace only this source file.
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                             prefix=".dialog-policy-", delete=False) as out:
                tmp = Path(out.name)
                out.write(updated)
            try:
                tmp.chmod(path.stat().st_mode & 0o777)
                tmp.replace(path)
            finally:
                tmp.unlink(missing_ok=True)
        print("BROWSER_DIALOG_POLICY_PATCH=PASS")
        return 0
    except (OSError, SyntaxError, RuntimeError) as exc:
        print(f"BROWSER_DIALOG_POLICY_PATCH=BLOCKED: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
