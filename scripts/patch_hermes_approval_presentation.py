#!/usr/bin/env python3
"""Connect approval briefs to native chat presentation; preserve consent logic."""
from __future__ import annotations
import argparse
import ast
from pathlib import Path

MARKER = 'DEVKIT_APPROVAL_PRESENTATION_V1'
IMPORT_ANCHOR = '            self.agent = AIAgent('
IMPORT_NEW = ('            from hermes_cli.devkit_approval_presentation import render_interim as _devkit_render_interim\n'
              + IMPORT_ANCHOR)
SETUP_ANCHOR = '                stream_delta_callback=self._stream_delta if self.streaming_enabled else None,'
SETUP_NEW = ('                # ' + MARKER + ': an interim plan is an assistant reply, not status stdout.\n'
             '                interim_assistant_callback=(None if single_query_mode else\n'
             '                    lambda text, already_streamed=False: _devkit_render_interim(\n'
             '                        self, text, already_streamed=already_streamed)),\n'
             + SETUP_ANCHOR)
RENDER_NEW = ('        # ' + MARKER + ': retain native rows and change approval colors only.\n'
              '        from hermes_cli.devkit_approval_presentation import approval_fragments\n'
              '        return approval_fragments(state, panel.close())')


def transform(source: str, kind: str) -> str:
    if kind == 'setup':
        if MARKER in source:
            if source.count(SETUP_NEW) != 1 or source.count(IMPORT_NEW) != 1:
                raise RuntimeError('Partial approval presentation callback patch')
            return source
        if (source.count(SETUP_ANCHOR) != 1 or source.count(IMPORT_ANCHOR) != 1
                or 'interim_assistant_callback=' in source):
            raise RuntimeError('Upstream interim callback changed; review required')
        result = source.replace(SETUP_ANCHOR, SETUP_NEW).replace(IMPORT_ANCHOR, IMPORT_NEW)
    elif kind == 'tui':
        methods = [n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef)
                   and n.name == '_get_clarify_display_fragments']
        if len(methods) != 1:
            raise RuntimeError('Native Clarify renderer is missing or ambiguous')
        node = methods[0]
        lines = source.splitlines(keepends=True)
        part = ''.join(lines[node.lineno-1:node.end_lineno])
        if MARKER in part:
            if part.count(RENDER_NEW) != 1:
                raise RuntimeError('Partial approval presentation renderer patch')
            return source
        old = '        return panel.close()'
        if part.count(old) != 1:
            raise RuntimeError('Native Clarify renderer footer changed')
        lines[node.lineno-1:node.end_lineno] = [part.replace(old, RENDER_NEW)]
        result = ''.join(lines)
    else:
        raise ValueError('Unknown source kind: ' + kind)
    ast.parse(result)
    return result


def patch_root(root: Path, check_only=False):
    targets = {'setup': root/'hermes_cli/cli_agent_setup_mixin.py',
               'tui': root/'hermes_cli/cli_tui_mixin.py'}
    # Verify the final-response renderer still uses the native APIs we reuse.
    final = (root/'hermes_cli/cli_chat_turn_mixin.py').read_text(encoding='utf-8')
    for token in ('_render_final_assistant_content', 'response_border', 'banner_text',
                  'box=rich_box.HORIZONTALS', 'soft_wrap=True', 'closing_separator(True)'):
        if token not in final:
            raise RuntimeError('Native response presentation contract changed: ' + token)
    helper = Path(__file__).with_name('devkit_approval_presentation.py').read_text(encoding='utf-8')
    ast.parse(helper)
    before = {k: p.read_text(encoding='utf-8') for k, p in targets.items()}
    after = {k: transform(s, k) for k, s in before.items()}
    installed = root/'hermes_cli/devkit_approval_presentation.py'
    if check_only:
        if before != after or not installed.is_file() or installed.read_text(encoding='utf-8') != helper:
            raise RuntimeError('Approval presentation installation missing, partial or stale')
        return
    # All source/anchor checks above run BEFORE any source write.
    for k, p in targets.items():
        if before[k] != after[k]:
            p.write_text(after[k], encoding='utf-8')
    installed.write_text(helper, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--hermes-root', type=Path, required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    patch_root(args.hermes_root, args.check_only)
    print('[PASS] Native approval presentation installation')


if __name__ == '__main__':
    main()
