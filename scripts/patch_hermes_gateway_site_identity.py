#!/usr/bin/env python3
"""Recognize Hermes' site-based Python -c launcher as a live Gateway process.

Upstream status_inline_source currently knows the older os,re,sys bootstrap,
but the current Hermes venv launcher uses os,site,sys + site.addsitedir.
Only exact source patterns may be considered identity (never arbitrary -c).
"""
from __future__ import annotations
import argparse
import ast
from pathlib import Path
import tempfile

MARKER = "DEVKIT_HERMES_SITE_INLINE_GATEWAY_IDENTITY_V1"
ANCHOR = '    # hermes_cli._launchers._write_cmd_launcher: the launcher script, base64-encoded\n'
ADDITION = (
    '    # ' + MARKER + ': recognize the venv in-process bootstrap only.\n'
    '    ("entry", re.compile(\n'
    '        r"""import os, site, sys; sys\.argv\[0\]=[\\x27\\x22]hermes[\\x27\\x22]; '
    'site\.addsitedir\(os\.environ\[[\\x27\\x22]HERMES_SITE[\\x27\\x22]\]\); '
    'from (?P<target>hermes_cli\.main) import (?P<func>main); '
    'sys\.exit\((?P=func)\(\)\)""", re.DOTALL)),\n'
)

def patch(source: str) -> str:
    if MARKER in source:
        return source
    count = source.count(ANCHOR)
    if count != 1:
        raise RuntimeError(f"gateway inline bootstrap marker expected once, found {count}")
    updated = source.replace(ANCHOR, ADDITION + ANCHOR, 1)
    ast.parse(updated)
    return updated

def smoke(module_path: Path) -> None:
    import importlib.util
    spec = importlib.util.spec_from_file_location("devkit_gateway_inline_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    command = [
        "/opt/hermes/.venv/bin/python", "-P", "-c",
        "import os, site, sys; sys.argv[0]='hermes'; site.addsitedir(os.environ['HERMES_SITE']); from hermes_cli.main import main; sys.exit(main())",
        "gateway", "run", "--replace",
    ]
    actual = module.inline_bootstrap_argv(command)
    assert actual == [command[0], "-m", "hermes_cli.main", "gateway", "run", "--replace"], actual
    # Unknown inline code cannot borrow a gateway argv to impersonate its PID.
    unsafe = [command[0], "-c", "print('hello')", "gateway", "run"]
    assert module.inline_bootstrap_argv(unsafe) is None
    # Near matches and an unrelated module must not be adopted.
    near = list(command)
    near[3] = near[3].replace("hermes_cli.main", "malicious.main")
    assert module.inline_bootstrap_argv(near) is None
    # Exercise the real upstream identity matcher on the Docker process cmdline.
    from gateway.status import looks_like_gateway_runtime_command_line
    assert looks_like_gateway_runtime_command_line(" ".join(command))
    assert not looks_like_gateway_runtime_command_line(" ".join(unsafe))
    print("PASS: site-based Hermes Gateway identity and negative fixtures")

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--hermes-root", default="/opt/hermes")
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--check-only", action="store_true")
    args = p.parse_args()
    path = Path(args.hermes_root) / "gateway/status_inline_source.py"
    if args.self_test:
        with tempfile.TemporaryDirectory() as tmp:
            # The original module imports only re; fixture mirrors real bootstrap table.
            baseline = (
                "import re\n_Q = r'''['\\\"]?'''\n"
                "_BOOTSTRAPS = (\n"
                + ANCHOR
                + ")\n"
            )
            modified = patch(baseline)
            assert patch(modified) == modified
            assert MARKER in modified
        print("PASS: site Gateway identity patch anchors/idempotency")
        return
    source = path.read_text(encoding="utf-8")
    updated = patch(source)
    if not args.check_only and updated != source:
        path.write_text(updated, encoding="utf-8")
    if MARKER not in (source if args.check_only else updated):
        raise RuntimeError("Gateway identity patch not applied")
    if not args.check_only:
        smoke(path)
    print("PASS: Hermes site based Gateway identity patch")

if __name__ == "__main__":
    main()
