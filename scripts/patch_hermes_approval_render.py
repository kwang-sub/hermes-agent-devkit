#!/usr/bin/env python3
"""Install a scoped native-rendering callback; prevalidate before any write."""
from __future__ import annotations

import argparse
import ast
from pathlib import Path

MARKER = 'DEVKIT_APPROVAL_RENDER_V1'
IMPORT = 'from hermes_cli.devkit_approval_render import make_callback as _devkit_approval_render_callback'
ANCHOR = '                stream_delta_callback=self._stream_delta if self.streaming_enabled else None,\n'
CALLBACK = '                interim_assistant_callback=None if single_query_mode else _devkit_approval_render_callback(self),\n'


def transform(source: str) -> str:
    if MARKER in source:
        if source.count(IMPORT) != 1 or source.count(CALLBACK) != 1 or source.count(ANCHOR) != 1:
            raise RuntimeError('Partial native approval rendering patch')
        ast.parse(source)
        return source
    if source.count(ANCHOR) != 1 or 'interim_assistant_callback=' in source:
        raise RuntimeError('Hermes interim callback layout changed; review before patching')
    tree = ast.parse(source)
    nodes = tree.body
    index = 0
    while index < len(nodes) and (
        isinstance(nodes[index], ast.Expr) and isinstance(nodes[index].value, ast.Constant)
        and isinstance(nodes[index].value.value, str)
        or isinstance(nodes[index], ast.ImportFrom) and nodes[index].module == '__future__'
    ):
        index += 1
    lines = source.replace(ANCHOR, ANCHOR + CALLBACK).splitlines(keepends=True)
    lines.insert(nodes[index].lineno - 1, f'# {MARKER}\n{IMPORT}\n\n')
    result = ''.join(lines)
    ast.parse(result)
    return result


def patch_root(root: Path, *, check_only: bool = False) -> None:
    source_path = root / 'hermes_cli/cli_agent_setup_mixin.py'
    render_path = root / 'hermes_cli/cli_chat_turn_mixin.py'
    gateway_path = root / 'hermes_cli/gateway_agent.py'
    helper_path = root / 'hermes_cli/devkit_approval_render.py'
    helper = Path(__file__).with_name('devkit_approval_render.py').read_text(encoding='utf-8')
    ast.parse(helper)
    render_tree = ast.parse(render_path.read_text(encoding='utf-8'))
    renderers = [n for n in ast.walk(render_tree)
                 if isinstance(n, ast.FunctionDef) and n.name == '_chat_print_response_panel']
    if len(renderers) != 1 or [a.arg for a in renderers[0].args.args] != ['self', 'turn', 'response']:
        raise RuntimeError('Native Hermes response renderer contract changed')
    gateway = gateway_path.read_text(encoding='utf-8')
    ast.parse(gateway)
    if 'self.interim_assistant_callback(text, already_streamed=' not in gateway:
        raise RuntimeError('Native interim delivery callback contract changed')
    before = source_path.read_text(encoding='utf-8')
    after = transform(before)
    if check_only:
        if (before != after or not helper_path.is_file()
                or helper_path.read_text(encoding='utf-8') != helper):
            raise RuntimeError('Native approval rendering installation missing or stale')
        return
    source_path.write_text(after, encoding='utf-8')
    helper_path.write_text(helper, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--hermes-root', type=Path, required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    patch_root(args.hermes_root, check_only=args.check_only)
    print('[PASS] Native approval brief rendering installed')


if __name__ == '__main__':
    main()
