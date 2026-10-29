#!/usr/bin/env python3
"""Offline recognition/installation checks, not a live-model or native UI test."""
from pathlib import Path
import tempfile
import unittest
import devkit_approval_render as render
import patch_hermes_approval_render as patcher

ROOT=Path(__file__).resolve().parents[1]
BRIEF='# 구현 계획\n변경 대상: sample\n# 사용 스킬\n- dev-java-guidelines'


class ApprovalRenderContractTests(unittest.TestCase):
    def test_ordered_real_headings(self):
        for prefix in ('','# ','## ','### '):
            self.assertTrue(render.is_approval_brief(prefix+'구현 계획\n내용\n'+prefix+'사용 스킬\n설명'))
        self.assertTrue(render.is_approval_brief('**구현 계획**\n내용\n**사용 스킬**'))

    def test_quoted_fenced_or_missing_headings_are_not_briefs(self):
        for text in (None,'사용 스킬\n구현 계획','구현 계획',
                     '"구현 계획"과 "사용 스킬"을 설명합니다.',
                     '```markdown\n'+BRIEF+'\n```','~~~\n'+BRIEF+'\n~~~',
                     '> 구현 계획\n> 사용 스킬','    구현 계획\n    사용 스킬',
                     '# 구현 계획\n# 사용 스킬\n# 사용 스킬'):
            self.assertFalse(render.is_approval_brief(text),text)

    def test_view_never_mutates_live_state(self):
        cli=type('CLI',(),{})();cli._stream_started=True;cli.final_response_markdown='raw'
        view=render._MessageView(cli)
        self.assertFalse(view._stream_started);self.assertEqual(view.final_response_markdown,'raw')
        with self.assertRaises(AttributeError):view.final_response_markdown='render'
        self.assertTrue(cli._stream_started);self.assertEqual(cli.final_response_markdown,'raw')

    def test_patcher_idempotence(self):
        source='"""Fixture."""\nfrom __future__ import annotations\n\ndef setup(self, single_query_mode):\n    agent=Agent(\n'+patcher.ANCHOR+'    )\n'
        result=patcher.transform(source)
        self.assertEqual(patcher.transform(result),result)
        self.assertIn('None if single_query_mode',result)

    def test_changed_or_partial_layout_rejected(self):
        for source in ('pass\n',patcher.MARKER+'\npass\n',patcher.ANCHOR*2):
            with self.assertRaises((RuntimeError,SyntaxError)):patcher.transform(source)

    def test_no_fixed_palette_or_renderer_fork(self):
        source=(ROOT/'scripts/devkit_approval_render.py').read_text()
        self.assertIn('type(cli)._chat_print_response_panel',source)
        for forbidden in ('#FFFFFF','get_color(',"Panel(",'approve=True','write_text','conversation_history.append'):
            self.assertNotIn(forbidden,source)

    def test_policy_keeps_two_chapters_and_real_choice_ui(self):
        skill=(ROOT/'custom-skills/lite/dev-lite-session/SKILL.md').read_text()
        for term in ('하나의 일반 assistant Markdown 메시지','기존 Hermes 답변 렌더러','clarify','devkit_approval','approval.approved=true'):
            self.assertIn(term,skill)
        self.assertIn('기존 native Clarify UI',skill)

    def test_image_installs_and_verifies_native_renderer(self):
        docker=(ROOT/'Dockerfile').read_text()
        for term in ('patch_hermes_approval_render.py --hermes-root /opt/hermes',
                     'patch_hermes_approval_render.py --hermes-root /opt/hermes --check-only',
                     'check_hermes_approval_render.py --hermes-root /opt/hermes'):
            self.assertIn(term,docker)


if __name__=='__main__':unittest.main()
