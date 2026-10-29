#!/usr/bin/env python3
"""Compare approval briefs to the REAL upstream assistant renderer (model-free).

Gateway methods, final-response renderer, Markdown formatter and modern layout
functions are compiled from the supplied upstream source. Only app/skin/config,
logging and terminal IO are fixtures; Rich rendering itself is real.
"""
from __future__ import annotations
import argparse
import ast
import io
import logging
from pathlib import Path
import re
import sys
import types
import unittest
from unittest.mock import patch

from rich import box as rich_box
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
import devkit_approval_render as adapter
import patch_hermes_approval_render as installer

ROOT = None
BRIEF = '# 구현 계획\n\n변경 대상: sample\n1. **기존 설정**을 유지합니다.\n\n# 사용 스킬\n\n- `dev-java-guidelines`: Java 규칙\n'


def functions(path, names, namespace, *, class_name=None):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    nodes = tree.body
    if class_name:
        nodes = next(n for n in nodes if isinstance(n, ast.ClassDef) and n.name == class_name).body
    selected = [n for n in nodes if isinstance(n, ast.FunctionDef) and n.name in names]
    if {n.name for n in selected} != set(names):
        raise AssertionError('Native methods missing: ' + str(path))
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), namespace)
    return {name: namespace[name] for name in names}


class NativeRenderingTests(unittest.TestCase):
    def setUp(self):
        self.output = io.StringIO()
        self.width = 80
        self.light = False
        self.console = Console(file=self.output, force_terminal=True, color_system='truecolor', width=self.width)
        self.cli_module = types.ModuleType('cli')
        cli = self.cli_module
        cli.ChatConsole = lambda: self.console
        cli._ACCENT = '\x1b[33m'; cli._RST = '\x1b[0m'
        cli._cprint = lambda text: self.output.write(str(text) + '\n')
        cli._maybe_remap_for_light_mode = lambda color: '#223344' if self.light else color
        cli._post_stream_transform_output = lambda *args: ''
        cli._terminal_columns = lambda: self.width
        cli.realign_markdown_tables = lambda text, width: text  # no table in this focused fixture
        cli._WINDOWS_PATH_WITH_DOT_SEGMENT_RE = re.compile(r'(?i)(?:\b[a-z]:\\|\\\\)[^\s`]*\\\.[^\s`]*')
        namespace = {'_RichText': Text, 're': re}
        names = ['_render_final_assistant_content', '_rich_text_from_ansi',
                 '_strip_markdown_syntax', '_preserve_windows_dot_segments_for_markdown']
        for name, fn in functions(ROOT/'hermes_cli/cli_render.py', names, namespace).items():
            setattr(cli, name, fn)
        hermes = types.ModuleType('hermes_cli'); hermes.__path__ = []
        skin_module = types.ModuleType('hermes_cli.skin_engine')
        self.colors = {'response_border':'#125678', 'banner_text':'#78ABCD', 'ui_accent':'#AB5623'}
        skin = types.SimpleNamespace(get_color=lambda key, default:self.colors.get(key, default),
                                     get_branding=lambda key, default:'☤ Test Hermes')
        skin_module.get_active_skin = lambda: skin
        modern = types.ModuleType('hermes_cli.cli_modern_layout')
        modern.__dict__.update(_RST='\x1b[0m', _BOLD='\x1b[1m', _DIM='\x1b[2m', _SEPARATOR_WIDTH=40, _GAP_PENDING=False)
        functions(ROOT/'hermes_cli/cli_modern_layout.py',
                  ['_skin_hex','_fg','_brand_glyph','separator','closing_separator','answer_label'], modern.__dict__)
        self.modules = {'cli':cli, 'hermes_cli':hermes, 'hermes_cli.skin_engine':skin_module,
                        'hermes_cli.cli_modern_layout':modern}
        native = functions(ROOT/'hermes_cli/cli_chat_turn_mixin.py', ['_chat_print_response_panel'],
                           {'Panel':Panel, 'rich_box':rich_box, 'logging':logging}, class_name='CLIChatTurnMixin')
        native['_agent_status_print'] = lambda owner,text:owner.logs.append(text)
        native['_flush_stream'] = lambda owner:owner.flushes.append(True)
        native['_scrollback_box_width'] = lambda owner:self.width
        self.CLI = type('NativeCLI', (), native)
        gateway = functions(ROOT/'hermes_cli/gateway_agent.py', ['_on_interim','_close_segment'], {}, class_name='GatewayAgent')
        self.Gateway = type('NativeGateway', (), gateway)

    def cli(self, modern=False, mode='render', *, live_flags=False):
        cli = self.CLI()
        cli._modern_layout=modern;cli.final_response_markdown=mode
        cli._stream_started=live_flags;cli._stream_box_opened=live_flags
        cli._last_turn_interrupted=live_flags;cli._streamed_text_this_turn=''
        cli.logs=[];cli.flushes=[];cli.session_id='untouched-session'
        return cli

    def reset_output(self):
        self.output.seek(0);self.output.truncate(0)

    def test_actual_renderer_matches_byte_for_byte_across_layout_theme_and_markdown(self):
        for modern in (False,True):
            for mode in ('render','raw','strip'):
                for light in (False,True):
                    for width in (42,100):
                        with self.subTest(modern=modern,mode=mode,light=light,width=width), patch.dict(sys.modules,self.modules):
                            self.width=width;self.console.width=width;self.light=light
                            self.reset_output()
                            turn=types.SimpleNamespace(result={},use_streaming_tts=False,box_opened=False)
                            self.cli(modern,mode)._chat_print_response_panel(turn,BRIEF)
                            expected=self.output.getvalue();self.reset_output()
                            actual_cli=self.cli(modern,mode,live_flags=True)
                            before=dict(vars(actual_cli))
                            adapter.render_interim(actual_cli,BRIEF)
                            self.assertEqual(self.output.getvalue(),expected)
                            self.assertIn('Test Hermes',expected)
                            self.assertEqual(vars(actual_cli),before)
                            self.assertEqual(actual_cli.flushes,[True])
                            self.assertEqual(actual_cli.logs,[])

    def test_actual_gateway_pre_patch_reproduces_plain_status_output(self):
        cli=self.cli();gateway=self.Gateway()
        gateway._turn=types.SimpleNamespace(seen=set(),_shown=[],close_segment=lambda:None)
        gateway.stream_delta_callback=None;gateway.interim_assistant_callback=None
        gateway._emit_print=cli._agent_status_print
        gateway._on_interim({'text':BRIEF},None,{})
        self.assertEqual(cli.logs,[BRIEF]);self.assertEqual(self.output.getvalue(),'')

    def test_actual_gateway_callback_renders_before_native_clarify(self):
        cli=self.cli();gateway=self.Gateway()
        gateway._turn=types.SimpleNamespace(seen=set(),_shown=[],close_segment=lambda:None)
        gateway.stream_delta_callback=None;gateway.interim_assistant_callback=adapter.make_callback(cli)
        with patch.dict(sys.modules,self.modules):gateway._on_interim({'text':BRIEF},None,{})
        self.assertIn('Test Hermes',self.output.getvalue());self.assertEqual(cli.logs,[])
        self.assertIn(BRIEF.strip(),gateway._turn.seen)

    def test_actual_setup_expression_disables_callback_in_headless_mode(self):
        source=(ROOT/'hermes_cli/cli_agent_setup_mixin.py').read_text(encoding='utf-8')
        tree=ast.parse(source)
        values=[n.value for n in ast.walk(tree) if isinstance(n,ast.keyword) and n.arg=='interim_assistant_callback']
        self.assertEqual(len(values),1)
        code=compile(ast.Expression(values[0]),'<actual setup keyword>','eval')
        namespace={'self':self.cli(),'_devkit_approval_render_callback':adapter.make_callback}
        self.assertIsNone(eval(code,namespace|{'single_query_mode':True}))
        self.assertTrue(callable(eval(code,namespace|{'single_query_mode':False})))

    def test_already_streamed_brief_is_not_rendered_twice(self):
        cli=self.cli();cli._streamed_text_this_turn=BRIEF
        adapter.render_interim(cli,BRIEF,already_streamed=True)
        self.assertEqual(self.output.getvalue(),'');self.assertEqual(cli.flushes,[])

    def test_remote_stream_flag_does_not_hide_unseen_brief(self):
        cli=self.cli()
        with patch.dict(sys.modules,self.modules):adapter.render_interim(cli,BRIEF,already_streamed=True)
        self.assertIn('Test Hermes',self.output.getvalue())

    def test_ordinary_progress_and_quoted_examples_are_unchanged(self):
        cli=self.cli()
        for text in ('파일을 확인합니다.', '```markdown\n'+BRIEF+'```', '> 구현 계획\n> 사용 스킬'):
            adapter.render_interim(cli,text)
        self.assertEqual(len(cli.logs),3);self.assertEqual(self.output.getvalue(),'')

    def test_repeated_new_brief_is_not_globally_deduplicated(self):
        cli=self.cli()
        with patch.dict(sys.modules,self.modules):
            adapter.render_interim(cli,BRIEF); first=self.output.getvalue()
            adapter.render_interim(cli,BRIEF)
        self.assertEqual(self.output.getvalue(),first+first)

    def test_blank_and_non_text_messages_are_ignored(self):
        cli=self.cli()
        for value in (None,'','  ',[]):adapter.render_interim(cli,value)
        self.assertEqual(cli.logs,[]);self.assertEqual(cli.flushes,[])


def main():
    global ROOT
    parser=argparse.ArgumentParser()
    parser.add_argument('--hermes-root',type=Path,required=True)
    ROOT=parser.parse_args().hermes_root
    installer.patch_root(ROOT,check_only=True)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NativeRenderingTests))
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
