#!/usr/bin/env python3
"""Negative-path tests: fixture PASS must not impersonate official dialog E2E."""
from __future__ import annotations
import copy
import unittest
from managed_dialog_evidence import summarize


def fixture():
    cases=[]
    for scenario in ('reload','navigate','confirm'):
        for action in ('dismiss','accept'):
            accept=action=='accept'; keep=scenario=='confirm' or not accept
            cases.append({'scenario':scenario,'action':action,'mode':'hermes','result':'PASS',
              'automatic_control':False,'response_owner':'hermes.browser_dialog',
              'effective_no_auto_dialog':'1','capture_kind':'native-CDP','closed_before_response':False,
              'observer_session_id':'S','cleanup':{'status':'PASS'},
              'initial':{'activated':True,'dirty':True,'input':'SAMPLE','path':'/','docId':'old'},
              'final':{'docId':'old' if keep else 'new','input':'SAMPLE' if keep else '',
                       'path':'/' if scenario!='navigate' or keep else '/next','answer':accept},
              'page_preserved':keep,'input_preserved':keep,'dialog_result':accept,
              'response':{'action':action,'dialog_id':'d1','sent_at':2.0,'success':True},
              'events':[{'method':'Page.javascriptDialogOpening','sessionId':'S','time':1.0,
                         'params':{'frameId':'F','type':'confirm' if scenario=='confirm' else 'beforeunload'}},
                        {'method':'Page.javascriptDialogClosed','sessionId':'S','time':3.0,
                         'params':{'frameId':'F','result':accept}}]})
    return {'schema':'managed_dialog_probe_v1','provider':'browser_exec','mode':'hermes',
            'source_policy_model':False,'complete_matrix':True,'cases':cases}


class ManagedEvidenceTests(unittest.TestCase):
    def test_target_failure_is_not_hidden_by_incomplete_matrix(self):
        x=fixture(); x['complete_matrix']=False
        x['cases']=[{'scenario':'reload','action':'dismiss','result':'BLOCKED',
                     'failed_phase':'target_match','events':[]}]
        result=summarize(x)
        self.assertEqual(result['classification'],'FIXTURE_TARGET_UNCONFIRMED')
        self.assertEqual(result['failed_phase'],'target_match')
        self.assertEqual(result['failed_case'],'reload/dismiss')
        self.assertEqual(result['execution_status'],'INCONCLUSIVE')

    def test_missing_controls_are_readiness_not_identity_failure(self):
        x=fixture(); x['complete_matrix']=False
        x['cases']=[{'scenario':'reload','action':'dismiss','result':'BLOCKED',
                     'failed_phase':'fixture_ready'}]
        self.assertEqual(summarize(x)['classification'],'FIXTURE_NOT_READY')

    def test_partial_matrix_does_not_hide_early_close(self):
        x=fixture(); x['complete_matrix']=False; x['cases']=x['cases'][:1]
        x['cases'][0].update(result='BLOCKED', failed_phase='respond', closed_before_response=True)
        self.assertEqual(summarize(x)['classification'],'CLOSED_BEFORE_RESPONSE')
        self.assertEqual(summarize(x)['execution_status'],'BLOCKED_ENV')

    def test_unknown_failure_phase_is_redacted(self):
        x=fixture(); x['complete_matrix']=False
        x['cases']=[{'result':'BLOCKED','failed_phase':'https://private.invalid/secret'}]
        self.assertEqual(summarize(x)['failed_phase'],'unknown')
        self.assertNotIn('private',str(summarize(x)))

    def test_all_six_official_cases(self):
        self.assertEqual(summarize(fixture())['execution_status'],'PASS')
    def test_policy_model_is_not_official_pass(self):
        x=fixture(); x['source_policy_model']=True
        self.assertNotEqual(summarize(x)['execution_status'],'PASS')
    def test_direct_cdp_observer_is_not_official_response(self):
        x=fixture(); x['cases'][0]['response_owner']='direct-CDP'
        self.assertNotEqual(summarize(x)['execution_status'],'PASS')
    def test_no_auto_patch_is_required(self):
        x=fixture(); x['cases'][0]['effective_no_auto_dialog']='0'
        self.assertNotEqual(summarize(x)['execution_status'],'PASS')
    def test_close_before_response_is_blocked(self):
        x=fixture(); x['cases'][0]['closed_before_response']=True
        self.assertEqual(summarize(x)['execution_status'],'BLOCKED_ENV')
    def test_missing_send_time_is_not_pass(self):
        x=fixture(); del x['cases'][0]['response']['sent_at']
        self.assertNotEqual(summarize(x)['execution_status'],'PASS')
    def test_nonfinite_and_bool_times_are_rejected(self):
        for value in (float('nan'),float('inf'),True,'2.0'):
            x=fixture(); x['cases'][0]['response']['sent_at']=value
            self.assertNotEqual(summarize(x)['execution_status'],'PASS')
    def test_wrong_response_order_is_not_pass(self):
        for value in (.5,4.0):
            x=fixture(); x['cases'][0]['response']['sent_at']=value
            self.assertNotEqual(summarize(x)['execution_status'],'PASS')
    def test_frame_mismatch_is_not_pass(self):
        x=fixture(); x['cases'][0]['events'][1]['params']['frameId']='other'
        self.assertNotEqual(summarize(x)['execution_status'],'PASS')
    def test_missing_input_is_not_pass(self):
        x=fixture(); x['cases'][0]['final']['input']=''
        self.assertNotEqual(summarize(x)['execution_status'],'PASS')
    def test_accept_requires_real_document_change(self):
        x=fixture(); x['cases'][1]['final']['docId']='old'
        self.assertNotEqual(summarize(x)['execution_status'],'PASS')
    def test_cleanup_warning_is_not_final_pass(self):
        x=fixture(); x['cases'][0]['cleanup']['status']='WARNING'
        self.assertNotEqual(summarize(x)['execution_status'],'PASS')
    def test_duplicate_or_missing_case_is_not_pass(self):
        x=fixture(); x['cases'][0]=copy.deepcopy(x['cases'][1])
        self.assertNotEqual(summarize(x)['execution_status'],'PASS')
        x=fixture(); x['cases'].pop()
        self.assertNotEqual(summarize(x)['execution_status'],'PASS')
    def test_bridge_confirm_is_labeled_and_value_checked(self):
        x=fixture(); c=x['cases'][4]; c['capture_kind']='hermes-bridge'
        c['events']=[{'method':'Hermes.dialogPending','time':1.0},
                     {'method':'Hermes.dialogResponded','time':3.0}]
        self.assertEqual(summarize(x)['execution_status'],'PASS')
        c['final']['answer']=True
        self.assertNotEqual(summarize(x)['execution_status'],'PASS')
    def test_malformed_report_is_not_pass(self):
        with self.assertRaises(ValueError): summarize([])
        x=fixture(); x['cases'][0]['response']=[]
        self.assertNotEqual(summarize(x)['execution_status'],'PASS')


if __name__=='__main__': unittest.main(verbosity=2)
