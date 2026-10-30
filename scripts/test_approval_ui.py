#!/usr/bin/env python3
"""Offline adapter/policy checks. Native UI execution is a separate installed-source suite."""
from copy import deepcopy
import json
import re
from pathlib import Path
import tempfile
import unittest
import devkit_approval_ui as ui
import patch_hermes_approval_ui as patcher

ROOT = Path(__file__).resolve().parents[1]


def entry():
    return {'qid':'q0', 'question':'Approval', 'devkit_approval':True,
            'choices':['작업 진행 (Recommended)','작업 보류']}


def reply(kind='choice', value='작업 진행 (Recommended)', outcome='submitted'):
    return {'answers':{'q0':value}, 'answer_meta':{'q0':{'kind':kind}},
            'outcome':outcome, 'devkit_approval':ui.PROTOCOL}


class ApprovalAdapterTests(unittest.TestCase):
    def decision(self, result):
        return ui.approval_result(entry(), result, {'status':'answered'})

    def test_only_explicit_opt_in(self):
        for value in (None,False,'true',1,{},[]):
            self.assertFalse(ui.is_approval({'devkit_approval':value}))
        self.assertTrue(ui.is_approval(entry()))

    def test_default_other_label_unchanged(self):
        self.assertEqual(ui.other_label({'choices':['A','B']},'Other'),'Other')
        self.assertEqual(ui.other_label({'questions':[entry()],'active':0},'Other'),'추가 요구사항')

    def test_proceed_only_from_native_choice(self):
        result=self.decision(reply())
        self.assertTrue(result['approved']); self.assertEqual(result['action'],'proceed')

    def test_hold_not_approval(self):
        result=self.decision(reply(value='작업 보류'))
        self.assertFalse(result['approved']); self.assertEqual(result['action'],'hold')

    def test_free_text_choice_name_remains_requirements(self):
        for text in ('작업 진행','작업 진행 (Recommended)','네','1','진행 전에 테스트 추가'):
            result=self.decision(reply('other',text))
            self.assertFalse(result['approved']); self.assertEqual(result['requirements'],text)

    def test_every_non_submission_fails_closed(self):
        for status in ('cancelled','timed_out','undelivered','error',None):
            self.assertFalse(self.decision(reply(outcome=status))['approved'])

    def test_no_text_aliases(self):
        for text in ('1','yes','네','작업 진행','작업 진행 후 배포',''):
            self.assertFalse(self.decision(reply(value=text))['approved'])

    def test_missing_or_unknown_origin_fails_closed(self):
        for changes in ({'answer_meta':{}},{'devkit_approval':None},{'answer_meta':{'q0':{'kind':'multi'}}}):
            r=reply(); r.update(changes);self.assertFalse(self.decision(r)['approved'])

    def test_empty_input_does_not_lock(self):
        state={'questions':[entry()],'choices':entry()['choices'],'active':0}
        for text in ('','  ',None):self.assertFalse(ui.allow_lock(state,text,{'kind':'other'}))
        self.assertTrue(ui.allow_lock(state,state['choices'][0],None))
        self.assertTrue(ui.allow_lock({},None,None))

    def test_generic_callback_and_wire_shape_unchanged(self):
        state={'questions':[{'qid':'q0'}],'answers':{'q0':'A'},'answer_meta':{'q0':{'kind':'choice'}}}
        self.assertEqual(ui.callback_reply(state,'submitted'),{'answers':{'q0':'A'},'outcome':'submitted'})
        self.assertEqual(ui.reply_metadata(state['questions'],reply()),{})
        self.assertEqual(ui.question_metadata(state['questions'][0]),{})

    def test_approval_callback_and_wire_keep_origin(self):
        state={'questions':[entry()],'answers':reply()['answers'],'answer_meta':reply()['answer_meta']}
        self.assertEqual(ui.callback_reply(state,'submitted'),reply())
        self.assertEqual(ui.question_metadata(entry()),{'devkit_approval':True})
        self.assertEqual(ui.reply_metadata([entry()],reply())['answer_meta'],reply()['answer_meta'])

    def test_schema_wrapper_is_idempotent_and_normal_result_is_exact(self):
        schema={'parameters':{'properties':{'questions':{'items':{'properties':{}}}}}}
        native='{"unchanged": true}'
        space={'CLARIFY_SCHEMA':schema,'_normalize_questions':lambda q:(deepcopy(q),None),
               '_result':lambda *args:native}
        ui.install_core(space);wrapped=space['_normalize_questions'];ui.install_core(space)
        self.assertIs(space['_normalize_questions'],wrapped)
        self.assertEqual(space['_result']([{'question':'normal'}],{}),native)
        self.assertEqual(schema['parameters']['properties']['questions']['items']['properties']['devkit_approval']['type'],'boolean')
        for q in ([{'question':'A','devkit_approval':'true'}],
                  [{'question':'A','choices':ui.CHOICES,'devkit_approval':True,'multi_select':True}],
                  [{'question':'A','choices':ui.CHOICES+['추가 요구사항'],'devkit_approval':True}]):
            self.assertIsNotNone(wrapped(q)[1])

    def test_partial_patch_rejected_and_core_patch_idempotent(self):
        source='"""fixture"""\nregistry.register(name="clarify")\n'
        result=patcher.transform(source,'core')
        self.assertEqual(patcher.transform(result,'core'),result)
        with self.assertRaises(RuntimeError):patcher.transform(result.replace('_install_devkit_approval(globals())',''), 'core')
        with self.assertRaises(RuntimeError):patcher.transform('def changed(): pass\n','core')

    def test_absent_upstream_fails_without_creating_files(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(RuntimeError):patcher.patch_root(Path(temp))
            self.assertEqual(list(Path(temp).rglob('*')),[])


class ApprovalPolicyTests(unittest.TestCase):
    def test_skill_calls_real_single_question_ui(self):
        text=(ROOT/'custom-skills/core/dev-session/SKILL.md').read_text()
        self.assertIn('requires_tools: [terminal, clarify]',text)
        example=json.loads(re.search(r'```json\n(.*?)\n```',text,re.S)[1])
        self.assertEqual(len(example['questions']),1)
        self.assertIs(example['questions'][0]['devkit_approval'],True)
        self.assertEqual(example['questions'][0]['choices'],ui.CHOICES)
        self.assertIn('approval.action=proceed',text)
        self.assertIn('approval.approved=true',text)
        self.assertIn('고정된 승인 포맷을 출력하거나 승인을 요구하지 않는다',text)
        self.assertIn('런타임 잠금은 아니다',text)

    def test_native_ui_test_is_installed_in_actual_image(self):
        docker=(ROOT/'Dockerfile').read_text()
        for name in ('devkit_approval_ui.py','patch_hermes_approval_ui.py','check_hermes_approval_ui.py'):
            self.assertIn(name,docker)
        self.assertIn('/tmp/check_hermes_approval_ui.py --hermes-root /opt/hermes',docker)
        workflow=(ROOT/'.github/workflows/approval-ui.yml').read_text()
        self.assertIn('bf0203a794a07aac3ff764972ab9087baa4e4f4e',workflow)
        self.assertIn('main',workflow)
        self.assertIn('check_hermes_approval_ui.py',workflow)
        self.assertNotIn('Capture exact source fixtures',workflow)

    def test_no_extra_root_entrypoint_or_approval_database(self):
        self.assertEqual(sorted(p.name for p in ROOT.glob('*.ps1')),['update-devkit.ps1'])
        helper=(ROOT/'scripts/devkit_approval_ui.py').read_text()
        self.assertNotIn('sqlite3',helper)
        self.assertNotIn('subprocess',helper)

    def test_docs_distinguish_native_ui_tests_from_llm_guarantee(self):
        text=(ROOT/'docs/session-approval.md').read_text()
        for term in ('작업 진행','작업 보류','추가 요구사항','Python CLI','prompt_toolkit','LLM'):
            self.assertIn(term,text)


if __name__=='__main__': unittest.main()
