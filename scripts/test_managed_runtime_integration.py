#!/usr/bin/env python3
"""Glue tests using real fixture/probe processes; no false claim of browser E2E."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from browser_runtime_adapter import run
from test_managed_dialog_evidence import fixture


class ManagedRuntimeIntegrationTests(unittest.TestCase):
    def run_fixture(self, data, exit_code=0):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp); source=path/'input.json'; source.write_text(json.dumps(data))
            code='import pathlib,sys;pathlib.Path(sys.argv[2]).write_bytes(pathlib.Path(sys.argv[1]).read_bytes());sys.exit(int(sys.argv[3]))'
            return run([sys.executable,'-m','http.server','{port}','--bind','127.0.0.1'],
                       [sys.executable,'-c',code,str(source),'{result_file}',str(exit_code)],
                       path/'artifacts','probe-only','browser_exec',8,8)

    def test_complete_official_fixture_schema(self):
        data=fixture(); data['result']='PASS'
        result=self.run_fixture(data)
        self.assertEqual(result['execution_status'],'PASS',result)
        self.assertEqual(result['classification'],'MANAGED_DIALOG_CAPABILITY_CONFIRMED')
        self.assertEqual(result['cleanup']['status'],'PASS')

    def test_model_does_not_become_runtime_capability_pass(self):
        data=fixture(); data['mode']='policy-model'; data['source_policy_model']=True
        self.assertEqual(self.run_fixture(data)['execution_status'],'INCONCLUSIVE')

    def test_early_close_is_blocked(self):
        data=fixture(); data['cases'][0]['closed_before_response']=True
        result=self.run_fixture(data)
        self.assertEqual(result['execution_status'],'BLOCKED_ENV')
        self.assertEqual(result['next_action'],'STOP_RETRY_ESCALATE')

    def test_nonzero_probe_never_returns_pass(self):
        result=self.run_fixture(fixture(),exit_code=1)
        self.assertEqual(result['execution_status'],'INCONCLUSIVE')
        self.assertEqual(result['classification'],'PROBE_EXIT_NONZERO')

    def test_legacy_trace_still_works(self):
        data={'provider':'browser_exec','events':[
              {'method':'Page.javascriptDialogOpening','sessionId':'S','params':{'type':'beforeunload'},'time':1.0},
              {'method':'Page.javascriptDialogClosed','sessionId':'S','params':{'result':False},'time':3.0}],
              'dismiss':{'sent_at':2.0,'success':True},'page_preserved':True,'input_preserved':True}
        result=self.run_fixture(data)
        self.assertEqual(result['execution_status'],'PASS')
        self.assertEqual(result['classification'],'DISMISS_AND_PRESERVATION_CONFIRMED')


if __name__=='__main__': unittest.main(verbosity=2)
