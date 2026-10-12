#!/usr/bin/env python3
"""Stage 1 regressions, including actual process trees and synthetic failure evidence."""
from pathlib import Path
import base64
import json
import os
import signal
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import zlib
from unittest.mock import patch
from browser_runtime_adapter import run
from browser_verification_evidence import completion, validate
from managed_dialog_evidence import summarize
from test_managed_dialog_evidence import fixture
from ui_runtime.capture import TimeBudget, capture, png_dimensions
from ui_runtime.process import live_group, stop_owned
from ui_runtime.result import outcome
from ui_runtime.suite import Suite, Unsupported, aggregate


def png(width=2, height=2):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind+data)&0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))
            +chunk(b'IDAT', zlib.compress((b'\0'+b'\xff\0\0'*width)*height))+chunk(b'IEND',b''))


class Page:
    budget=TimeBudget()
    target_id='owned'
    viewport_state={'width':2,'height':2,'mobile':False}
    def __init__(self, failures=0): self.calls=[]; self.failures=failures
    def activate(self): self.calls.append(('activate',{}))
    def healthy(self): return True
    def call(self, method, params=None, timeout=None):
        self.calls.append((method, params, timeout))
        if method=='Page.getLayoutMetrics': return {'cssContentSize':{'x':0,'y':0,'width':2,'height':2}}
        if self.failures:
            self.failures-=1; raise TimeoutError()
        return {'data':base64.b64encode(png()).decode()}


class CaptureTests(unittest.TestCase):
    def test_owned_activation_and_capture_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            page=Page(); result=capture(page,Path(temp),full_page=True)
            self.assertEqual(result['status'],'PASS')
            self.assertEqual(result['visual_review'],'NOT_RUN')
            self.assertEqual(page.calls[0][0],'activate')
            self.assertEqual(page.calls[-1][2],60)
            self.assertGreater(page.budget.outer(60),60)
            self.assertTrue(page.calls[-1][1]['captureBeyondViewport'])
    def test_default_no_retry_and_optional_recovery_preserves_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Page(1); self.assertEqual(capture(p,Path(temp))['status'],'INCONCLUSIVE')
            p=Page(1); r=capture(p,Path(temp),full_page=True,recovery=lambda _:True)
            self.assertEqual(r['status'],'PASS'); self.assertEqual(len(r['attempts']),2)
            self.assertTrue(all(x[1]['captureBeyondViewport'] for x in p.calls if x[0]=='Page.captureScreenshot'))
    def test_invalid_png(self):
        for data in (b'',b'PNG',png()[:-8],png()[:20]+b'corrupt'+png()[27:]):
            with self.assertRaises(ValueError): png_dimensions(data)
    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            a=capture(Page(),Path(temp)); b=capture(Page(),Path(temp))
            self.assertNotEqual(a['path'],b['path']); self.assertTrue(Path(a['path']).exists())
    def test_finite_timeouts(self):
        for v in (True,float('inf'),float('nan'),-1,0):
            with self.assertRaises(ValueError): TimeBudget(capture=v)


class SuiteTests(unittest.TestCase):
    def test_capture_failure_does_not_block_independent_function(self):
        with tempfile.TemporaryDirectory() as temp:
            s=Suite(Path(temp),task_id='t',required=['image','behavior'],scope='product fixture')
            s.check('image','visual',lambda:(_ for _ in ()).throw(TimeoutError()))
            s.check('behavior','functional',lambda:True)
            r=s.finish({'status':'PASS'})
            self.assertFalse(r['verification_final']); self.assertEqual(r['required_outstanding'],['image'])
            self.assertEqual(r['checks'][1]['status'],'PASS')
    def test_only_explicit_dependencies_block(self):
        with tempfile.TemporaryDirectory() as temp:
            s=Suite(Path(temp),task_id='t',required=['static'],scope='local')
            s.check('browser','capability',lambda:False)
            s.check('view','functional',lambda:True,depends=['browser'])
            s.check('static','static',lambda:True)
            self.assertTrue(s.finish({'status':'PASS'})['verification_final'])
            self.assertEqual(s.report['checks'][1]['status'],'NOT_RUN')
    def test_unsupported_not_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            s=Suite(Path(temp),task_id='t',required=['upload'],scope='local')
            s.check('upload','functional',lambda:(_ for _ in ()).throw(Unsupported()))
            self.assertFalse(s.finish({'status':'PASS'})['verification_final'])
    def test_assertion_is_fail_and_exception_is_inconclusive(self):
        with tempfile.TemporaryDirectory() as temp:
            s=Suite(Path(temp),task_id='t',required=['bad'],scope='product')
            r=s.check('bad','functional',lambda:False)
            self.assertEqual(r['status'],'FAIL')
            self.assertEqual(s.finish({'status':'PASS'})['execution_status'],'FAIL')
    def test_required_missing_empty_and_cleanup(self):
        for required,checks,cleanup in [([],[],{'status':'PASS'}),(['a'],[],{'status':'PASS'}),
                                       (['a'],[{'id':'a','status':'PASS'}],{'status':'WARNING'})]:
            self.assertFalse(aggregate(checks,required,cleanup)['verification_final'])
    def test_attempts_and_checkpoint_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            a=Suite(Path(temp),task_id='t',required=['a'],scope='local'); a.check('a','functional',lambda:True)
            b=Suite(Path(temp),task_id='t',required=['b'],scope='local')
            self.assertNotEqual(a.directory,b.directory)
            self.assertEqual(json.loads((a.directory/'ui-report.json').read_text())['checks'][0]['status'],'PASS')
    def test_outcome_retry_context_not_session_guess(self):
        a=outcome('FAIL','ASSERTION',environment='version1'); b=outcome('FAIL','ASSERTION',environment='version2')
        self.assertEqual(a['recovery_fingerprint'],b['recovery_fingerprint'])
        self.assertNotEqual(a['retry_fingerprint'],b['retry_fingerprint'])


class AdapterTests(unittest.TestCase):
    def execute(self, temp, data, code=0):
        source=Path(temp)/'data.json'; source.write_text(json.dumps(data))
        command='import sys,pathlib;pathlib.Path(sys.argv[2]).write_bytes(pathlib.Path(sys.argv[1]).read_bytes());sys.exit(int(sys.argv[3]))'
        return run([sys.executable,'-m','http.server','{port}','--bind','127.0.0.1'],
                   [sys.executable,'-c',command,str(source),'{result_file}',str(code)],Path(temp)/'results','t','browser_exec',4,4)
    def test_nonzero_recalculates_next_action_and_fingerprint(self):
        with tempfile.TemporaryDirectory() as temp:
            r=self.execute(temp,fixture(),1)
            self.assertEqual(r['classification'],'PROBE_EXIT_NONZERO')
            self.assertNotEqual(r['next_action'],'CONTINUE_PRODUCT_VERIFICATION')
    def test_generic_ui_report_supported(self):
        data={'schema':'ui_verification_v1','scope':'synthetic fixture','provider':'browser_exec','required':['a'],
              'checks':[{'id':'a','status':'PASS','evidence':'synthetic observation'}],'cleanup':{'status':'PASS'}}
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(self.execute(temp,data)['execution_status'],'PASS')
    def test_cleanup_warning_downgrades_pass_but_keeps_artifacts(self):
        with tempfile.TemporaryDirectory() as temp:
            original=stop_owned
            def stop(proc):
                errors=original(proc)
                return errors+['TEST_WARNING']
            with patch('browser_runtime_adapter._stop',side_effect=stop): r=self.execute(temp,fixture())
            self.assertEqual(r['cleanup']['status'],'WARNING')
            self.assertNotEqual(r['execution_status'],'PASS')
            self.assertTrue((Path(r['attempt_dir'])/'browser-dialog-raw.json').exists())
    def test_repeated_attempt_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            a=self.execute(temp,fixture()); b=self.execute(temp,fixture())
            self.assertNotEqual(a['attempt_dir'],b['attempt_dir'])
            self.assertTrue((Path(a['attempt_dir'])/'browser-runtime-report.json').exists())
    def test_timeout_and_interruption_record_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            r=run([sys.executable,'-m','http.server','{port}','--bind','127.0.0.1'],
                  [sys.executable,'-c','import time; time.sleep(10)'],Path(temp),'t','browser_exec',4,.1)
            self.assertEqual(r['classification'],'PROBE_TIMEOUT'); self.assertEqual(r['cleanup']['status'],'PASS')
    @unittest.skipUnless(os.name=='posix','requires POSIX group ownership')
    def test_orphan_child_ignoring_sigterm_is_killed(self):
        with tempfile.TemporaryDirectory() as temp:
            ready=Path(temp)/'ready'
            child="import signal,time,pathlib;signal.signal(signal.SIGTERM,signal.SIG_IGN);pathlib.Path(%r).touch();time.sleep(30)" % str(ready)
            parent="import subprocess,sys,time,pathlib;subprocess.Popen([sys.executable,'-c',%r]);p=pathlib.Path(%r);\nwhile not p.exists(): time.sleep(.01)" % (child,str(ready))
            proc=subprocess.Popen([sys.executable,'-c',parent],start_new_session=True)
            try:
                proc.wait(timeout=4); self.assertTrue(live_group(proc.pid))
                self.assertEqual(stop_owned(proc),[]); self.assertFalse(live_group(proc.pid))
            finally:
                try: os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError: pass


class EvidenceTests(unittest.TestCase):
    def data(self):
        return {'schema':'browser_verification_v1','task_id':'t','provider':'browser_exec','session':'s','verified_at':'now',
                'capabilities':[{'name':'input','status':'PASS','execution_status':'PASS','evidence':'observed'}],
                'acceptance_criteria':[{'ac_id':'AC1','status':'PASS','method':'browser','evidence':'observed','capability':'input'}],
                'cleanup':{'status':'PASS'}}
    def test_structure_not_completion_and_explicit_requirements(self):
        d=self.data(); self.assertTrue(validate(d))
        self.assertFalse(completion(d,[])['verification_final'])
        self.assertFalse(completion(d,['AC1','AC2'])['verification_final'])
        self.assertTrue(completion(d,['AC1'])['verification_final'])
    def test_empty_evidence_and_false_final_rejected(self):
        d=self.data();d['capabilities'][0]['evidence']=''
        with self.assertRaises(ValueError):validate(d)
        d=self.data();d['acceptance_criteria'][0]['status']='NOT_RUN';d['verification_final']=True
        with self.assertRaises(ValueError):validate(d)
    def test_native_confirm_answer_mismatch_never_passes(self):
        d=fixture();d['cases'][4]['final']['answer']=True
        self.assertNotEqual(summarize(d)['execution_status'],'PASS')
    def test_missing_navigation_observation_never_passes(self):
        d=fixture();del d['cases'][1]['final']['docId']
        self.assertNotEqual(summarize(d)['execution_status'],'PASS')
    def test_partial_observed_assertion_failure_is_fail(self):
        d=fixture();d['complete_matrix']=False;d['cases']=d['cases'][:1];d['cases'][0]['result']='FAIL'
        self.assertEqual(summarize(d)['execution_status'],'FAIL')


if __name__=='__main__': unittest.main(verbosity=2)
