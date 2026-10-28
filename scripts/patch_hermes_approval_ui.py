#!/usr/bin/env python3
"""Install an opt-in Lite approval adapter on the native Clarify CLI.

All upstream anchors and syntax are checked before any source write. A new or
partially changed upstream layout fails the image build rather than silently
falling back to text-based consent. No user config, DB or profiles are touched.
"""
from __future__ import annotations
import argparse
import ast
from pathlib import Path

MARKER = 'DEVKIT_APPROVAL_UI_V1'
IMPORT = '\nfrom tools import devkit_approval_ui as _devkit_approval\n'
CORE = '''# DEVKIT_APPROVAL_UI_V1: the normal Clarify contract remains the default.
from tools.devkit_approval_ui import install_core as _install_devkit_approval
_install_devkit_approval(globals())

'''


def replace_exact(source, old, new, count=1):
    if source.count(old) != count:
        raise RuntimeError(f'Approval UI upstream anchor mismatch: expected {count} of {old[:90]!r}')
    return source.replace(old, new)


def transform(source: str, kind: str) -> str:
    edits = {
        'core': [('registry.register(', CORE + 'registry.register(', 1)],
        'modal': [
            ('        entry = state["questions"][state["active"]]\n        state["answers"][entry["qid"]] = answer',
             '        if not _devkit_approval.allow_lock(state, answer, meta):\n            return\n        entry = state["questions"][state["active"]]\n        state["answers"][entry["qid"]] = answer', 1),
            ('return {"answers": dict(state["answers"]), "outcome": outcome}',
             'return _devkit_approval.callback_reply(state, outcome)', 1),
            ('return {"answers": partial, "outcome": "timed_out"}',
             'return _devkit_approval.callback_reply(state, "timed_out")', 1),
        ],
        'tui': [
            ("                         or self._connection_state))\n        kb.add('escape', filter=_modal_prompt_active",
             "                         or self._connection_state or _devkit_approval.is_approval(_devkit_approval.active_entry(self._clarify_state))))\n        kb.add('escape', filter=_modal_prompt_active", 1),
            ('        """ESC cancels active secret/sudo/connection/slash-confirm prompts."""\n',
             '        """ESC cancels active secret/sudo/connection/slash-confirm prompts."""\n        if _devkit_approval.is_approval(_devkit_approval.active_entry(self._clarify_state)):\n            self._clarify_state["response_queue"].put(None)\n            self._clarify_teardown()\n            event.app.current_buffer.reset()\n            event.app.invalidate()\n            return\n', 1),
            ('t("cli.tui.clarify_other_type_below")',
             '_devkit_approval.other_label(state, t("cli.tui.clarify_other_type_below"))', 1),
            ('t("cli.tui.clarify_other_type_answer")',
             '_devkit_approval.other_label(state, t("cli.tui.clarify_other_type_answer"))', 2),
            ('return t("cli.tui.placeholder_answer")',
             'return ("추가 요구사항을 입력해주세요." if _devkit_approval.is_approval(_devkit_approval.active_entry(self._clarify_state)) else t("cli.tui.placeholder_answer"))', 1),
            ('        base = getattr(self, \'_clarify_multi_base\', None)\n        if not text:',
             '        base = getattr(self, \'_clarify_multi_base\', None)\n        if _devkit_approval.is_approval(_devkit_approval.active_entry(state)):\n            text = self._expand_paste_references(text).strip()\n            if not text:\n                event.app.invalidate()\n                return\n        if not text:', 1),
        ],
        'client': [
            ('"multi_select": bool(q.get("multi_select"))}',
             '"multi_select": bool(q.get("multi_select")), **_devkit_approval.question_metadata(q)}', 1),
            ('    out = {"answers": answers}\n',
             '    out = {"answers": answers, **_devkit_approval.reply_metadata(questions, reply)}\n', 1),
        ],
        'server': [
            ('"multi_select": bool(e["multi_select"])}',
             '"multi_select": bool(e["multi_select"]), **_devkit_approval.question_metadata(e)}', 1),
        ],
        'session': [
            ('wire = [{key: entry.get(key) for key in _QUESTION_KEYS if entry.get(key) is not None} for entry in questions]',
             'wire = [{**{key: entry.get(key) for key in _QUESTION_KEYS if entry.get(key) is not None}, **_devkit_approval.question_metadata(entry)} for entry in questions]', 1),
            ('return {"answers": clean, "outcome": outcome}',
             'return {"answers": clean, "outcome": outcome, **_devkit_approval.reply_metadata(questions, result)}', 1),
        ],
        'contract': [
            ('    choices: list[str] | None = None\n    multi_select: bool = False\n',
             '    choices: list[str] | None = None\n    multi_select: bool = False\n    devkit_approval: bool = False\n', 1),
            ('    outcome: Literal["submitted", "timed_out", "cancelled"] | None = None\n',
             '    outcome: Literal["submitted", "timed_out", "cancelled"] | None = None\n    devkit_approval: Literal["lite_change_approval_v1"] | None = None\n    answer_meta: dict[str, dict[str, JsonValue]] | None = None\n', 1),
        ],
    }[kind]
    if MARKER in source:
        for _, new, count in edits:
            if source.count(new) != count:
                raise RuntimeError('Incomplete approval UI patch: ' + kind)
        if kind not in ('core', 'contract') and IMPORT not in source:
            raise RuntimeError('Missing approval UI helper import: ' + kind)
        ast.parse(source)
        return source
    result = source
    for old, new, count in edits:
        result = replace_exact(result, old, new, count)
    if kind not in ('core', 'contract'):
        nodes = ast.parse(result).body
        index = 0
        while index < len(nodes) and (
            isinstance(nodes[index], ast.Expr) and isinstance(nodes[index].value, ast.Constant) and isinstance(nodes[index].value.value, str)
            or isinstance(nodes[index], ast.ImportFrom) and nodes[index].module == '__future__'
        ):
            index += 1
        lines = result.splitlines(keepends=True)
        offset = nodes[index].lineno - 1
        lines.insert(offset, '# ' + MARKER + IMPORT)
        result = ''.join(lines)
    elif kind == 'contract':
        result = replace_exact(result, 'class ClarifyQuestion(Params):',
                               '# ' + MARKER + ': additive, opt-in wire fields.\nclass ClarifyQuestion(Params):')
    ast.parse(result)
    return result


def resolve_targets(root: Path) -> dict:
    targets = {'core': root / 'tools/clarify_tool.py',
               'modal': root / 'hermes_cli/cli_modal_mixin.py',
               'tui': root / 'hermes_cli/cli_tui_mixin.py',
               'client': root / 'hermes_cli/gateway_agent.py',
               'server': root / 'tui_gateway/server.py',
               'session': root / 'gateway/session_clarify_batch.py',
               'contract': root / 'tui_gateway/contracts/server_requests.py'}
    missing = [str(p) for p in targets.values() if not p.is_file()]
    if missing:
        raise RuntimeError('Approval UI upstream sources missing: ' + ', '.join(missing))
    return targets


def patch_root(root: Path, check_only: bool = False) -> None:
    helper = Path(__file__).with_name('devkit_approval_ui.py').read_text(encoding='utf-8')
    ast.parse(helper)
    targets = resolve_targets(root)
    before = {kind: path.read_text(encoding='utf-8') for kind, path in targets.items()}
    # Do not partly patch a root when the last upstream anchor no longer matches.
    after = {kind: transform(source, kind) for kind, source in before.items()}
    installed = root / 'tools/devkit_approval_ui.py'
    if check_only:
        if before != after or not installed.is_file() or installed.read_text(encoding='utf-8') != helper:
            raise RuntimeError('Approval UI installation is missing, partial or stale')
        return
    for kind, path in targets.items():
        if before[kind] != after[kind]:
            path.write_text(after[kind], encoding='utf-8')
    installed.write_text(helper, encoding='utf-8')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--hermes-root', type=Path, required=True)
    p.add_argument('--check-only', action='store_true')
    args = p.parse_args()
    patch_root(args.hermes_root, args.check_only)
    print('[PASS] Native Clarify Lite approval UI contract')


if __name__ == '__main__':
    main()
