#!/usr/bin/env python3
"""Model-free executable tests against installed Hermes Clarify methods.

The real schema, normalizer, result builder, renderers, native key handlers and
Gateway adapters are extracted from the selected source tree. Only unrelated
agent/model/notification infrastructure is stubbed. One test drives a real
prompt_toolkit input pipeline. This is not a live LLM compliance test.
"""
from __future__ import annotations
import argparse
import ast
import asyncio
import json
from pathlib import Path
import queue
import shutil
import sys
import textwrap
import threading
import time
import types
import unittest
from unittest.mock import patch
from typing import Callable, Dict, List, Optional
import devkit_approval_ui as adapter

ROOT = None
CORE = None
CLI = None
CLIENT = None
SERVER = None
SESSION = None
CLI_MODULE = None
MODULES = {}


def selected_source(path, names, namespace, class_name=None):
    """Compile actual method/function ASTs without importing the whole agent."""
    tree = ast.parse(path.read_text(encoding='utf-8'))
    nodes = tree.body
    if class_name:
        cls = next(n for n in nodes if isinstance(n, ast.ClassDef) and n.name == class_name)
        members = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
        if set(names) != {n.name for n in members}:
            raise AssertionError('Missing native methods in ' + str(path))
        cls.body = members; cls.bases = []; cls.decorator_list = []
        body = [cls]
    else:
        body = [n for n in nodes if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
        if set(names) != {n.name for n in body}:
            raise AssertionError('Missing native functions in ' + str(path))
    exec(compile(ast.Module(body=body, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace[class_name] if class_name else namespace


def translate(key, **kwargs):
    messages = {'cli.tui.clarify_title': 'Hermes — Clarify',
                'cli.tui.clarify_other_type_below': 'Other (type below)',
                'cli.tui.clarify_other_type_answer': 'Other (type your answer)',
                'cli.clarify.label': 'Clarify'}
    return messages.get(key, key).format(**kwargs)


def load(root):
    global CORE, CLI, CLIENT, SERVER, SESSION, CLI_MODULE, MODULES
    source = (root/'tools/clarify_tool.py').read_text(encoding='utf-8')
    if 'DEVKIT_APPROVAL_UI_V1' not in source:
        raise AssertionError('Install approval UI patch before running native tests')
    tree = ast.parse(source)
    body = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.Assign, ast.AnnAssign))]
    CORE = {'json': json, 'Callable': Callable, 'Dict': Dict, 'List': List, 'Optional': Optional}
    exec(compile(ast.Module(body=body, type_ignores=[]), str(root/'tools/clarify_tool.py'), 'exec'), CORE)
    adapter.install_core(CORE)
    render = {'shutil': shutil, 'textwrap': textwrap}
    selected_source(root/'hermes_cli/cli_render.py',
                    ['_panel_box_width', '_wrap_panel_text', '_append_panel_line', '_append_blank_panel_line'], render)
    selected_source(root/'hermes_cli/cli_panel.py', ['_Panel'], render)
    CLI_MODULE = types.ModuleType('cli')
    CLI_MODULE.CLI_CONFIG = {}; CLI_MODULE._DIM = ''; CLI_MODULE._RST = ''; CLI_MODULE._cprint = lambda *_: None
    CLI_MODULE._panel_box_width = render['_panel_box_width']; CLI_MODULE._wrap_panel_text = render['_wrap_panel_text']
    timeout = types.ModuleType('tools.clarify_gateway'); timeout.resolve_clarify_timeout = lambda _: 0; timeout.get_clarify_timeout = lambda: 0
    tools = types.ModuleType('tools'); tools.__path__ = []; tools.clarify_gateway = timeout
    gateway = types.ModuleType('tui_gateway'); gateway.__path__ = []
    sr = types.ModuleType('tui_gateway.server_requests'); gateway.server_requests = sr
    MODULES = {'cli': CLI_MODULE, 'tools': tools, 'tools.clarify_gateway': timeout,
               'tui_gateway': gateway, 'tui_gateway.server_requests': sr}
    owner = types.ModuleType('gateway'); owner.__path__ = []
    owner_requests = types.ModuleType('gateway.session_server_requests'); owner.session_server_requests = owner_requests
    MODULES.update({'gateway':owner, 'gateway.session_server_requests':owner_requests})
    globals_ = {'json': json, 'queue': queue, '_time': time, 'time': time, 't': translate,
                '_devkit_approval': adapter, '_TIMED_OUT': object(), 'shutil': shutil, 'Optional': Optional,
                '_Panel': render['_Panel'], '_agent_name': lambda: 'Hermes', '_PANEL_RESERVED_BELOW': 6,
                '_term_rows': lambda: 50, '_tn': lambda key, count: str(count),
                '_num_prefix': lambda i: str(i+1)}
    modal = selected_source(root/'hermes_cli/cli_modal_mixin.py',
        ['_clarify_callback', '_clarify_batch_set_active', '_clarify_batch_lock', '_clarify_batch_enter',
         '_clarify_teardown', '_poll_modal_queue'], globals_, 'CLIModalMixin')
    tui = selected_source(root/'hermes_cli/cli_tui_mixin.py',
        ['_get_clarify_display_fragments', '_tui_make_clarify_number_handler', '_tui_enter_clarify_freetext',
         '_tui_enter_clarify_choice', '_tui_clarify_up', '_tui_clarify_down', '_tui_handle_escape_modal'], globals_, 'CLITuiMixin')
    class Harness(modal, tui):
        def __init__(self):
            self._clarify_state = None; self._clarify_freetext = False; self._clarify_multi_base = None
            self._clarify_prefill = ''; self._clarify_deadline = None; self.summaries = []
            self._connection_state = self._secret_state = self._sudo_state = self._slash_confirm_state = None
        def _paint_now(self): pass
        def _ring_bell(self, **kwargs): pass
        def _persist_prompt_summary(self, *args): self.summaries.append(args)
        def _expand_paste_references(self, text): return text.replace('[fixture-paste]', '추가 요구사항\n한글 붙여넣기')
    CLI = Harness
    CLIENT = selected_source(root/'hermes_cli/gateway_agent.py', ['clarify_reply'], dict(globals_))['clarify_reply']
    SERVER = selected_source(root/'tui_gateway/server.py', ['_clarify_block'],
                             {**globals_, '_clarify_timeout_seconds': lambda: 5})['_clarify_block']
    SESSION = selected_source(root/'gateway/session_clarify_batch.py', ['ask_clarify_batch'],
                              {**globals_, '_QUESTION_KEYS':('qid','question','choices','multi_select')})['ask_clarify_batch']


def question(**extra):
    return {'question': '제시한 계획을 어떻게 진행할까요?', 'choices': adapter.CHOICES.copy(),
            'devkit_approval': True, **extra}


def normalized(q=None):
    qs, error = CORE['_normalize_questions']([q or question()])
    if error: raise AssertionError(error)
    return qs


class Buffer:
    def __init__(self, text=''): self.text = text; self.cursor_position = len(text)
    def reset(self, **kwargs): self.text = ''


def event(text=''):
    return types.SimpleNamespace(app=types.SimpleNamespace(current_buffer=Buffer(text), invalidate=lambda: None))


def start(cli, qs):
    result = {}
    def run():
        try: result['reply'] = cli._clarify_callback(qs)
        except BaseException as exc: result['error'] = exc
    thread = threading.Thread(target=run, daemon=True); thread.start()
    until = time.monotonic()+2
    while cli._clarify_state is None and thread.is_alive() and time.monotonic()<until: time.sleep(.005)
    if cli._clarify_state is None: raise AssertionError('Native panel did not open: ' + str(result))
    return thread, result


class NativeApprovalTests(unittest.TestCase):
    def setUp(self):
        self.mods = patch.dict(sys.modules, MODULES); self.mods.start(); self.addCleanup(self.mods.stop)
        self.cli = CLI(); self.qs = normalized(); self.thread, self.result = start(self.cli, self.qs)
        self.addCleanup(self.stop)
    def stop(self):
        if self.cli._clarify_state: self.cli._clarify_state['response_queue'].put(None)
        self.thread.join(2)
    def finish(self):
        self.thread.join(2); self.assertFalse(self.thread.is_alive(), 'Callback did not settle')
        return json.loads(CORE['_result'](self.qs, self.result['reply']))
    def render(self):
        return ''.join(t for _, t in self.cli._get_clarify_display_fragments())
    def test_exact_three_rows_and_native_style(self):
        text = self.render()
        for token in ('1. 작업 진행', '2. 작업 보류', '3. 추가 요구사항'): self.assertIn(token, text)
        self.assertNotIn('4.', text); self.assertNotIn('Other', text)
    def test_enter_proceeds(self):
        self.cli._tui_enter_clarify_choice(event())
        self.assertEqual(self.finish()['responses'][0]['approval']['action'], 'proceed')
    def test_number_one_proceeds(self):
        self.cli._tui_make_clarify_number_handler(0)(event())
        self.assertTrue(self.finish()['responses'][0]['approval']['approved'])
    def test_hold_via_number(self):
        self.cli._tui_make_clarify_number_handler(1)(event())
        self.assertEqual(self.finish()['responses'][0]['approval']['action'], 'hold')
    def test_hold_via_arrow(self):
        self.cli._tui_clarify_down(event()); self.cli._tui_enter_clarify_choice(event())
        self.assertFalse(self.finish()['responses'][0]['approval']['approved'])
    def test_third_option_enters_text_without_submitting(self):
        self.cli._tui_make_clarify_number_handler(2)(event())
        self.assertTrue(self.cli._clarify_freetext); self.assertTrue(self.thread.is_alive())
        self.assertEqual(self.cli._clarify_state['answers'], {})
        self.assertIn('3. 추가 요구사항', self.render())
    def test_third_option_via_arrows(self):
        self.cli._tui_clarify_down(event()); self.cli._tui_clarify_down(event())
        self.cli._tui_enter_clarify_choice(event())
        self.assertTrue(self.cli._clarify_freetext)
    def test_korean_multiline_paste(self):
        self.cli._tui_make_clarify_number_handler(2)(event())
        self.cli._tui_enter_clarify_freetext(event('[fixture-paste]'))
        value=self.finish()['responses'][0]['approval']
        self.assertEqual(value['requirements'], '추가 요구사항\n한글 붙여넣기'); self.assertFalse(value['approved'])
    def test_requirements_that_match_proceed_are_not_approval(self):
        self.cli._tui_make_clarify_number_handler(2)(event())
        self.cli._tui_enter_clarify_freetext(event('작업 진행'))
        value=self.finish()['responses'][0]['approval']
        self.assertEqual(value['action'], 'requirements'); self.assertFalse(value['approved'])
    def test_requirements_preserve_recommended_suffix(self):
        self.cli._tui_make_clarify_number_handler(2)(event())
        self.cli._tui_enter_clarify_freetext(event('추가 테스트 (Recommended)'))
        self.assertEqual(self.finish()['responses'][0]['user_response'], '추가 테스트 (Recommended)')
    def test_empty_requirements_keeps_input_open(self):
        self.cli._tui_make_clarify_number_handler(2)(event())
        self.cli._tui_enter_clarify_freetext(event('  '))
        self.assertTrue(self.cli._clarify_freetext); self.assertTrue(self.thread.is_alive())
        self.assertEqual(self.cli._clarify_state['answers'], {})
    def test_escape_cancels(self):
        self.cli._tui_make_clarify_number_handler(2)(event())
        self.cli._tui_handle_escape_modal(event('unsubmitted draft'))
        data=self.finish(); self.assertEqual(data['outcome'], 'cancelled')
        self.assertFalse(data['responses'][0]['approval']['approved'])
    def test_timeout_never_approves(self):
        self.cli._clarify_deadline = time.monotonic() - 1
        self.assertFalse(self.finish()['responses'][0]['approval']['approved'])
    def test_late_reply_cannot_change_cancelled_result(self):
        old=self.cli._clarify_state; self.cli._tui_handle_escape_modal(event())
        data=self.finish()
        self.cli._clarify_batch_lock(old, self.qs[0]['choices'][0], {'kind':'choice'})
        self.assertEqual(data['outcome'],'cancelled'); self.assertFalse(data['responses'][0]['approval']['approved'])


class ProtocolTests(unittest.TestCase):
    def test_schema_opt_in_and_bad_shape_rejected(self):
        prop=CORE['CLARIFY_SCHEMA']['parameters']['properties']['questions']['items']['properties']
        self.assertEqual(prop['devkit_approval']['type'], 'boolean')
        for q in (question(multi_select=True), question(choices=['작업 진행','작업 보류','추가 요구사항']), question(devkit_approval='true')):
            self.assertIsNotNone(CORE['_normalize_questions']([q])[1])
        self.assertIsNotNone(CORE['_normalize_questions']([question(), question()])[1])
    def test_normal_questions_and_results_unchanged(self):
        qs=normalized({'question':'Color?', 'choices':['Red','Blue']})
        self.assertNotIn('devkit_approval',qs[0])
        value=json.loads(CORE['_result'](qs,{'answers':{'q0':'Red (Recommended)'},'outcome':'submitted'}))
        self.assertEqual(value,{'responses':[{'question':'Color?', 'choices_offered':['Red','Blue'], 'status':'answered', 'user_response':'Red'}], 'outcome':'submitted'})
    def test_unsupported_client_cannot_approve_by_text(self):
        value=json.loads(CORE['_result'](normalized(),{'answers':{'q0':'작업 진행'},'outcome':'submitted'}))
        self.assertFalse(value['responses'][0]['approval']['approved'])
        self.assertEqual(value['responses'][0]['approval']['reason'], 'APPROVAL_UI_UNSUPPORTED')
    def test_transport_preserves_question_and_answer_origin(self):
        qs=normalized()
        def callback(questions):
            self.assertTrue(questions[0]['devkit_approval'])
            return {'answers':{'q0':questions[0]['choices'][0]}, 'outcome':'submitted',
                    'devkit_approval':adapter.PROTOCOL,'answer_meta':{'q0':{'kind':'choice'}}}
        def send(method,sid,params,**kwargs):
            self.assertEqual(method,'clarify')
            return CLIENT(callback,params)
        MODULES['tui_gateway.server_requests'].send=send
        with patch.dict(sys.modules,MODULES): reply=SERVER('fixture',qs)
        value=json.loads(CORE['_result'](qs,reply)); self.assertTrue(value['responses'][0]['approval']['approved'])
    def test_canonical_session_owner_preserves_choice_and_requirements_origin(self):
        qs=normalized(); live=types.SimpleNamespace(event_stream=object())
        turn=types.SimpleNamespace(_approval_owner=(types.SimpleNamespace(sessions={'fixture':live}), 'fixture', 1),
                                   _ctx=types.SimpleNamespace(agent_holder=[None]))
        for kind in ('choice','other'):
            with self.subTest(kind=kind):
                def callback(questions):
                    self.assertTrue(questions[0]['devkit_approval'])
                    return {'answers':{'q0':questions[0]['choices'][0]}, 'outcome':'submitted',
                            'devkit_approval':adapter.PROTOCOL,'answer_meta':{'q0':{'kind':kind}}}
                def ask(events,sid,method,params,**kwargs):
                    self.assertEqual(method,'clarify');return CLIENT(callback,params)
                MODULES['gateway.session_server_requests'].ask_viewer_result=ask
                with patch.dict(sys.modules,MODULES): reply=SESSION(turn,qs)
                decision=json.loads(CORE['_result'](qs,reply))['responses'][0]['approval']
                self.assertEqual(decision['action'],'proceed' if kind=='choice' else 'requirements')
                self.assertEqual(decision['approved'],kind=='choice')

    def test_cancelled_partial_choice_not_consent(self):
        qs=normalized()
        for outcome in ('cancelled','timed_out','undelivered','error'):
            reply={'answers':{'q0':qs[0]['choices'][0]},'outcome':outcome,
                   'devkit_approval':adapter.PROTOCOL,'answer_meta':{'q0':{'kind':'choice'}}}
            value=json.loads(CORE['_result'](qs,reply))
            self.assertFalse(value['responses'][0]['approval']['approved'])
    def test_generic_batch_callback_shape_is_unchanged(self):
        with patch.dict(sys.modules,MODULES):
            cli=CLI(); qs,error=CORE['_normalize_questions']([{'question':'A','choices':['yes','no']},{'question':'B'}])
            t,r=start(cli,qs)
            cli._tui_make_clarify_number_handler(0)(event()); self.assertTrue(cli._clarify_freetext)
            cli._tui_enter_clarify_freetext(event('typed')); t.join(2)
            self.assertEqual(set(r['reply']), {'answers','outcome'}); self.assertEqual(r['reply']['answers']['q1'], 'typed')
    def test_generic_other_label_not_changed(self):
        with patch.dict(sys.modules,MODULES):
            cli=CLI(); qs=normalized({'question':'Color?', 'choices':['Red','Blue']}); t,r=start(cli,qs)
            rendered=''.join(x for _,x in cli._get_clarify_display_fragments());self.assertIn('Other (type your answer)',rendered)
            cli._tui_make_clarify_number_handler(2)(event()); cli._tui_enter_clarify_freetext(event('')); t.join(2)
            self.assertEqual(r['reply']['answers']['q0'], None)
    def test_pydantic_wire_accepts_opt_in_fields(self):
        from pydantic import BaseModel, ConfigDict, JsonValue
        class Strict(BaseModel): model_config=ConfigDict(extra='forbid')
        scope={'Params':Strict, 'Result':Strict, 'JsonValue':JsonValue, 'Literal':__import__('typing').Literal}
        selected_source(ROOT/'tui_gateway/contracts/server_requests.py', ['ClarifyQuestion','ClarifyResult'], scope)
        scope['ClarifyQuestion'].model_rebuild(_types_namespace=scope)
        scope['ClarifyResult'].model_rebuild(_types_namespace=scope)
        q=scope['ClarifyQuestion'](qid='q0',question='Approval', choices=adapter.CHOICES,devkit_approval=True)
        self.assertTrue(q.devkit_approval)
        reply=scope['ClarifyResult'](answers={'q0':'작업 진행'},outcome='submitted',devkit_approval=adapter.PROTOCOL,answer_meta={'q0':{'kind':'choice'}})
        self.assertEqual(reply.answer_meta['q0']['kind'],'choice')
    def test_real_prompt_toolkit_key_input(self):
        from prompt_toolkit.application import Application
        from prompt_toolkit.input import create_pipe_input
        from prompt_toolkit.output import DummyOutput
        from prompt_toolkit.layout import Layout, HSplit, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.widgets import TextArea
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.filters import Condition
        async def run():
            with patch.dict(sys.modules,MODULES), create_pipe_input() as pipe:
                cli=CLI(); qs=normalized(); t,r=start(cli,qs); area=TextArea(); kb=KeyBindings()
                nav=Condition(lambda:bool(cli._clarify_state) and not cli._clarify_freetext)
                kb.add('3',filter=nav)(cli._tui_make_clarify_number_handler(2))
                @kb.add('enter')
                def submit(e):
                    cli._tui_enter_clarify_freetext(e) if cli._clarify_freetext else cli._tui_enter_clarify_choice(e)
                    if cli._clarify_state is None:e.app.exit()
                app=Application(layout=Layout(HSplit([Window(FormattedTextControl(cli._get_clarify_display_fragments)),area])),
                                key_bindings=kb,input=pipe,output=DummyOutput(),full_screen=True)
                async def feed():
                    await asyncio.sleep(.05);pipe.send_text('3');await asyncio.sleep(.05)
                    self.assertTrue(cli._clarify_freetext)
                    pipe.send_text('한글 추가 테스트');await asyncio.sleep(.05);pipe.send_text('\r')
                task=asyncio.create_task(feed())
                try: await asyncio.wait_for(app.run_async(),3); await task
                finally:
                    if cli._clarify_state:cli._clarify_state['response_queue'].put(None)
                    t.join(2)
                value=json.loads(CORE['_result'](qs,r['reply']))['responses'][0]['approval']
                self.assertEqual(value['requirements'],'한글 추가 테스트');self.assertFalse(value['approved'])
        asyncio.run(run())


def main():
    global ROOT
    p=argparse.ArgumentParser();p.add_argument('--hermes-root',type=Path,required=True);a=p.parse_args()
    ROOT=a.hermes_root;load(ROOT)
    suite=unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1

if __name__=='__main__':raise SystemExit(main())
