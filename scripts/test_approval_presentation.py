#!/usr/bin/env python3
"""Pure presentation/patch contracts. Native renderer parity is checked separately."""
import ast
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import devkit_approval_presentation as display
import patch_hermes_approval_presentation as installer

BRIEF = '# 구현 계획\n\n변경 대상: sample\n1. 설정을 수정합니다.\n\n# 사용 스킬\n- dev-java-guidelines\n'


class PresentationTests(unittest.TestCase):
    def test_heading_forms(self):
        for text in (BRIEF, BRIEF.replace('# ', ''), BRIEF.replace('# 구현 계획', '**구현 계획**').replace('# 사용 스킬', '**사용 스킬**')):
            self.assertTrue(display.is_plan_brief(text))

    def test_partial_reversed_quoted_and_fenced_examples_are_not_briefs(self):
        for text in ('# 구현 계획', '# 사용 스킬\n# 구현 계획', '> # 구현 계획\n> # 사용 스킬',
                     '```markdown\n'+BRIEF+'```', '~~~\n'+BRIEF+'~~~', '구현 계획과 사용 스킬을 논의하자', None):
            self.assertFalse(display.is_plan_brief(text))

    def test_generic_progress_uses_existing_output(self):
        rows = []
        cli = types.SimpleNamespace(_agent_status_print=rows.append)
        display.render_interim(cli, '파일을 확인합니다.')
        self.assertEqual(rows, ['파일을 확인합니다.'])

    def test_blank_output_is_not_rendered(self):
        cli = types.SimpleNamespace(_agent_status_print=lambda _: self.fail('Unexpected output'))
        for text in (None, '', '  '): display.render_interim(cli, text)

    def test_streamed_brief_is_not_duplicated(self):
        cli = types.SimpleNamespace(streaming_enabled=True)
        display.render_interim(cli, BRIEF, already_streamed=True)

    def test_generic_clarify_preserves_identity(self):
        rows = [('class:clarify-question', 'Color?')]
        for state in (None, {}, {'devkit_approval': False}, {'questions': [{'question':'Color?'}], 'active':0}):
            self.assertIs(display.approval_fragments(state, rows), rows)

    def test_approval_theme_preserves_content_and_mouse_handler(self):
        handler = object()
        rows = [('class:clarify-question','제시한 계획'), ('class:clarify-selected','1. 작업 진행',handler),
                ('class:clarify-active-other','3. 추가 요구사항'), ('class:unknown','기타')]
        state = {'questions': [{'devkit_approval':True}], 'active':0, 'answers':{}}
        with patch.object(display,'response_style',return_value=('Hermes','#123456','#abcdef')):
            output = display.approval_fragments(state, rows)
        self.assertEqual(output, [('#abcdef bold','제시한 계획'),('#123456 bold','1. 작업 진행',handler),
                                  ('#abcdef italic','3. 추가 요구사항'),('class:unknown','기타')])
        self.assertEqual(state['answers'], {})
        self.assertEqual(rows[0][0], 'class:clarify-question')

    def test_inactive_approval_does_not_recolor_other_questions(self):
        rows = [('class:clarify-choice','보통 질문')]
        state = {'questions':[{'devkit_approval':True},{}], 'active':1}
        self.assertIs(display.approval_fragments(state,rows),rows)

    def test_skin_is_resolved_at_each_render(self):
        palette = {'response_border':'#123456','banner_text':'#abcdef'}
        skin = types.SimpleNamespace(get_color=lambda k,default='': palette.get(k,default), get_branding=lambda k,d:'테마 Hermes')
        cli = types.ModuleType('cli'); cli._accent_hex=lambda:'#456789'
        cli._maybe_remap_for_light_mode=lambda color: color
        engine = types.ModuleType('hermes_cli.skin_engine'); engine.get_active_skin=lambda:skin
        with patch.dict(sys.modules,{'cli':cli,'hermes_cli.skin_engine':engine}):
            self.assertEqual(display.response_style(), ('테마 Hermes','#123456','#abcdef'))
            palette['banner_text']='#654321'
            self.assertEqual(display.response_style()[2], '#654321')
            cli._maybe_remap_for_light_mode=lambda c: '#111111' if c=='#654321' else c
            self.assertEqual(display.response_style()[2], '#111111')

    def test_setup_patch_is_idempotent_and_single_query_keeps_headless_behavior(self):
        source = 'class Setup:\n    def create(self):\n' + installer.IMPORT_ANCHOR+'\n'+installer.SETUP_ANCHOR+'\n            )\n'
        patched = installer.transform(source,'setup')
        self.assertEqual(installer.transform(patched,'setup'),patched)
        self.assertIn('None if single_query_mode else',patched)
        self.assertEqual(patched.count('interim_assistant_callback='),1)

    def test_tui_patch_changes_only_the_clarify_footer(self):
        source='class Tui:\n    def _get_clarify_display_fragments(self):\n        return panel.close()\n\n    def other(self):\n        return panel.close()\n'
        patched=installer.transform(source,'tui')
        self.assertEqual(installer.transform(patched,'tui'),patched)
        self.assertIn('def other(self):\n        return panel.close()',patched)
        ast.parse(patched)

    def test_drift_and_partial_patch_fail(self):
        for source,kind in [('', 'setup'), ('# '+installer.MARKER,'setup'), ('', 'tui')]:
            with self.assertRaises(RuntimeError): installer.transform(source,kind)

    def test_validation_precedes_any_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'hermes_cli').mkdir()
            source='class Setup:\n    def create(self):\n'+installer.IMPORT_ANCHOR+'\n'+installer.SETUP_ANCHOR+'\n            )\n'
            setup=root/'hermes_cli/cli_agent_setup_mixin.py';setup.write_text(source)
            (root/'hermes_cli/cli_tui_mixin.py').write_text('def changed_upstream(): pass\n')
            (root/'hermes_cli/cli_chat_turn_mixin.py').write_text('_render_final_assistant_content response_border banner_text box=rich_box.HORIZONTALS soft_wrap=True closing_separator(True)')
            with self.assertRaises(RuntimeError): installer.patch_root(root)
            self.assertEqual(setup.read_text(),source)
            self.assertFalse((root/'hermes_cli/devkit_approval_presentation.py').exists())


if __name__=='__main__': unittest.main()
