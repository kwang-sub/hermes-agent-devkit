#!/usr/bin/env python3
"""Run real Hermes rendering methods with a model-free console/skin fixture.

Compare the brief byte-for-byte with native final replies in classic/modern
layouts and all Markdown modes. Agent/model/terminal IO are not started.
"""
from __future__ import annotations
import argparse
import ast
import importlib.util
import io
from pathlib import Path
import re
import shutil
import sys
import textwrap
import types
import unittest
from unittest.mock import patch
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich import box
import devkit_approval_presentation as display
import patch_hermes_approval_presentation as installer

ROOT = None
BRIEF = '# 구현 계획\n\n변경 대상: /workspace/sample\n1. 설정을 검증합니다.\n\n# 사용 스킬\n- `dev-java-guidelines`\n'


def extract(path, names, namespace):
    tree=ast.parse(path.read_text(encoding='utf-8'))
    nodes=[n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names]
    if {n.name for n in nodes}!=set(names): raise AssertionError('Native methods missing: '+str(path))
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),namespace)
    return namespace


class NativePresentationTests(unittest.TestCase):
    def setUp(self):
        self.console_buffer=io.StringIO()
        self.console=Console(file=self.console_buffer,force_terminal=True,color_system='truecolor',width=88)
        self.palette={'response_border':'#D89B04','banner_text':'#FFF8DC','ui_accent':'#FFBF00'}
        skin=types.SimpleNamespace(get_color=lambda key,default='':self.palette.get(key,default),
                                   get_branding=lambda key,default='':'☤ Test Hermes')
        self.facade=types.ModuleType('cli')
        self.facade.ChatConsole=lambda:self.console
        self.facade._cprint=lambda text:self.console.print(Text.from_ansi(text),soft_wrap=True)
        self.facade._maybe_remap_for_light_mode=lambda value:value
        self.facade._accent_hex=lambda:self.palette['ui_accent']
        self.facade._ACCENT='';self.facade._RST=''
        self.facade._terminal_columns=lambda:88
        self.facade._WINDOWS_PATH_WITH_DOT_SEGMENT_RE=re.compile(r'(?i)(?:\b[a-z]:\\|\\\\)[^\s`]*\\\.[^\s`]*')
        self.facade.realign_markdown_tables=lambda text,width:text  # no tables in these fixtures
        ns={'re':re,'shutil':shutil,'textwrap':textwrap,'_RichText':Text}
        names=['_rich_text_from_ansi','_strip_markdown_syntax','_preserve_windows_dot_segments_for_markdown',
               '_render_final_assistant_content','_post_stream_transform_output','_panel_box_width',
               '_wrap_panel_text','_append_panel_line','_append_blank_panel_line']
        extract(ROOT/'hermes_cli/cli_render.py',names,ns)
        for name in names: setattr(self.facade,name,ns[name])
        extract(ROOT/'hermes_cli/cli_panel.py',['_Panel'],ns)
        self.panel=ns['_Panel']
        engine=types.ModuleType('hermes_cli.skin_engine');engine.get_active_skin=lambda:skin
        modern=types.ModuleType('hermes_cli.cli_modern_layout')
        modern_ns={'_RST':'\x1b[0m','_BOLD':'\x1b[1m','_DIM':'\x1b[2m',
                   '_SEPARATOR_WIDTH':40,'_GAP_PENDING':False}
        modern_names=['_skin_hex','_fg','_brand_glyph','separator','closing_separator','answer_label']
        extract(ROOT/'hermes_cli/cli_modern_layout.py',modern_names,modern_ns)
        for name in modern_names:setattr(modern,name,modern_ns[name])
        modules={'cli':self.facade,'hermes_cli.skin_engine':engine,
                 'hermes_cli.cli_modern_layout':modern,'hermes_cli.devkit_approval_presentation':display}
        self.mods=patch.dict(sys.modules,modules);self.mods.start();self.addCleanup(self.mods.stop)
        self.cli=types.SimpleNamespace(final_response_markdown='strip',_modern_layout=False,
            _last_turn_interrupted=False,_stream_started=False,_stream_box_opened=False,
            _streamed_text_this_turn='',streaming_enabled=False,_scrollback_box_width=lambda:88,
            _agent_status_print=lambda value:self.facade._cprint(value))
        self.turn=types.SimpleNamespace(result=None,use_streaming_tts=False,box_opened=False)
        final_ns={'Panel':Panel,'rich_box':box}
        extract(ROOT/'hermes_cli/cli_chat_turn_mixin.py',['_chat_print_response_panel'],final_ns)
        self.native=final_ns['_chat_print_response_panel']

    def capture(self, callback):
        self.console_buffer.seek(0);self.console_buffer.truncate(0)
        callback()
        return self.console_buffer.getvalue()

    def test_brief_matches_native_reply_in_both_layouts_and_all_modes(self):
        for modern in (False,True):
            for mode in ('strip','raw','render'):
                with self.subTest(modern=modern,mode=mode):
                    self.cli._modern_layout=modern;self.cli.final_response_markdown=mode
                    expected=self.capture(lambda:self.native(self.cli,self.turn,BRIEF))
                    actual=self.capture(lambda:display.render_interim(self.cli,BRIEF))
                    self.assertEqual(actual,expected)
                    self.assertIn('Test Hermes',actual)
                    self.assertIn('구현 계획',actual)

    def test_runtime_theme_change_and_light_mode_match_native(self):
        self.palette.update(response_border='#123456',banner_text='#AABBCC',ui_accent='#123456')
        self.facade._maybe_remap_for_light_mode=lambda color:'#112233' if color=='#AABBCC' else color
        expected=self.capture(lambda:self.native(self.cli,self.turn,BRIEF))
        actual=self.capture(lambda:display.render_interim(self.cli,BRIEF))
        self.assertEqual(actual,expected)
        self.assertIn('17;34;51',actual)

    def test_partial_skin_uses_the_same_native_fallbacks(self):
        self.palette.pop('response_border');self.palette.pop('banner_text')
        self.assertEqual(self.capture(lambda:display.render_interim(self.cli,BRIEF)),
                         self.capture(lambda:self.native(self.cli,self.turn,BRIEF)))

    def test_no_color_console_matches_native(self):
        self.console=Console(file=self.console_buffer,force_terminal=False,color_system=None,width=88)
        self.assertEqual(self.capture(lambda:display.render_interim(self.cli,BRIEF)),
                         self.capture(lambda:self.native(self.cli,self.turn,BRIEF)))

    def test_streamed_brief_is_not_printed_twice(self):
        self.cli.streaming_enabled=True
        self.assertEqual(self.capture(lambda:display.render_interim(self.cli,BRIEF,already_streamed=True)),'')

    def test_remote_stream_flag_without_local_stream_still_displays_plan(self):
        self.assertIn('Test Hermes',self.capture(lambda:display.render_interim(self.cli,BRIEF,already_streamed=True)))

    def test_progress_messages_still_use_status_path(self):
        text='필요한 소스를 읽습니다.'
        self.assertEqual(self.capture(lambda:display.render_interim(self.cli,text)),
                         self.capture(lambda:self.cli._agent_status_print(text)))

    def test_real_setup_callback_is_wired_and_headless_unchanged(self):
        tree=ast.parse((ROOT/'hermes_cli/cli_agent_setup_mixin.py').read_text())
        keywords=[n for n in ast.walk(tree) if isinstance(n,ast.keyword) and n.arg=='interim_assistant_callback']
        self.assertEqual(len(keywords),1)
        expression=compile(ast.Expression(keywords[0].value),'<native-setup>','eval')
        ns={'single_query_mode':False,'self':self.cli,'_devkit_render_interim':display.render_interim}
        callback=eval(expression,ns)
        self.assertIn('Test Hermes',self.capture(lambda:callback(BRIEF)))
        ns['single_query_mode']=True
        self.assertIsNone(eval(expression,ns))

    def test_real_clarify_renderer_uses_theme_without_changing_rows(self):
        helper_path=ROOT/'tools/devkit_approval_ui.py'
        if helper_path.is_file():
            spec=importlib.util.spec_from_file_location('approval_adapter_fixture',helper_path)
            adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
        else:
            adapter=None
        ns={'_Panel':self.panel,'_devkit_approval':adapter,'_agent_name':lambda:'Hermes',
            '_PANEL_RESERVED_BELOW':6,'_term_rows':lambda:50,'_num_prefix':lambda i:str(i+1),
            '_tn':lambda key,count:str(count),'t':lambda key,**kw:key}
        extract(ROOT/'hermes_cli/cli_tui_mixin.py',['_get_clarify_display_fragments'],ns)
        renderer=ns['_get_clarify_display_fragments']
        entry={'qid':'q0','question':'제시한 계획을 어떻게 진행할까요?',
               'choices':['작업 진행','작업 보류'],'multi_select':False,'devkit_approval':True}
        state={'questions':[entry],'active':0,'choices':entry['choices'],'selected':0,'answers':{}}
        cli=types.SimpleNamespace(_clarify_state=state,_clarify_freetext=False)
        rows=renderer(cli)
        combined=''.join(row[1] for row in rows)
        self.assertIn('1. 작업 진행',combined);self.assertIn('2. 작업 보류',combined)
        if adapter is not None:self.assertIn('3. 추가 요구사항',combined)
        self.assertNotIn('4.',combined)
        self.assertTrue(any(s==self.palette['response_border'] for s,_ in rows))
        self.assertTrue(any(s==self.palette['banner_text']+' bold' for s,_ in rows))
        self.assertEqual(state['answers'],{})
        entry['devkit_approval']=False
        generic=renderer(cli)
        self.assertTrue(any(s=='class:clarify-question' for s,_ in generic))

    def test_installer_check_only_and_idempotence(self):
        installer.patch_root(ROOT,check_only=True)
        before=(ROOT/'hermes_cli/cli_agent_setup_mixin.py').read_bytes()
        installer.patch_root(ROOT)
        self.assertEqual(before,(ROOT/'hermes_cli/cli_agent_setup_mixin.py').read_bytes())


def main():
    global ROOT
    parser=argparse.ArgumentParser();parser.add_argument('--hermes-root',type=Path,required=True)
    args=parser.parse_args();ROOT=args.hermes_root
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(NativePresentationTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    return not result.wasSuccessful()


if __name__=='__main__':raise SystemExit(main())
