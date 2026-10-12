#!/usr/bin/env python3
"""Glue tests using real fixture/probe processes; no false claim of browser E2E."""
from pathlib import Path
import asyncio
import os
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import ProxyHandler, build_opener
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from browser_runtime_adapter import run
from test_managed_dialog_evidence import fixture
from probe_managed_dialog import (CDP, FIXTURE_STATE, FixtureHandler, fixture_html,
                                  fixture_target_check, fixture_url, fixture_url_matches,
                                  launch_chrome, select_fixture_target, stop_owned, wait_for)


class ManagedRuntimeIntegrationTests(unittest.TestCase):
    def run_fixture(self, data, exit_code=0):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp); source=path/'input.json'; source.write_text(json.dumps(data))
            code='import pathlib,sys;pathlib.Path(sys.argv[2]).write_bytes(pathlib.Path(sys.argv[1]).read_bytes());sys.exit(int(sys.argv[3]))'
            return run([sys.executable,'-m','http.server','{port}','--bind','127.0.0.1'],
                       [sys.executable,'-c',code,str(source),'{result_file}',str(exit_code)],
                       path/'artifacts','probe-only','browser_exec',8,8)

    def test_partial_failure_reaches_runtime_summary(self):
        data=fixture(); data['complete_matrix']=False
        data['cases']=[{'scenario':'reload','action':'dismiss','result':'BLOCKED',
                        'failed_phase':'target_match','events':[]}]
        result=self.run_fixture(data,exit_code=2)
        self.assertEqual(result['classification'],'FIXTURE_TARGET_UNCONFIRMED')
        self.assertEqual(result['failed_phase'],'target_match')
        self.assertEqual(result['failed_case'],'reload/dismiss')
        self.assertEqual(result['execution_status'],'INCONCLUSIVE')

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


NONCE='test-attempt-1'
ORIGIN='http://127.0.0.1:3107'
URL=fixture_url(ORIGIN,NONCE)


class FixtureIdentityTests(unittest.TestCase):
    def check(self, **changes):
        document={'url':URL,'nonce':NONCE}
        document.update(changes)
        return fixture_target_check(document,URL,NONCE)['ok']

    def test_title_emoji_empty_or_missing_is_irrelevant(self):
        self.assertTrue(self.check())
        for title in ('DevKit native dialog probe','🐴 DevKit native dialog probe','', 'Renamed'):
            with self.subTest(title=title): self.assertTrue(self.check(title=title))

    def test_no_static_marker_tag_or_readystate_gate(self):
        # Presentation/implementation details aren't identity. Behavior is tested later.
        self.assertTrue(self.check(marker=None,ready='loading',docId='',tagName='A'))

    def test_fragments_extra_query_and_query_order_are_allowed(self):
        for url in (URL+'#details',URL+'&debug=1',ORIGIN+'?debug=1&devkit_probe='+NONCE):
            with self.subTest(url=url): self.assertTrue(self.check(url=url))

    def test_foreign_origin_port_path_and_credentials_still_block(self):
        for url in (URL.replace('3107','3108'),URL.replace('http:','https:'),
                    URL.replace('/?','/other?'),URL.replace('127.0.0.1','127.0.0.1.evil'),
                    URL.replace('127.0.0.1','user:password@127.0.0.1')):
            with self.subTest(url=url): self.assertFalse(self.check(url=url))

    def test_stale_missing_and_ambiguous_attempt_still_block(self):
        for nonce in (None,'','previous-attempt'):
            with self.subTest(nonce=nonce): self.assertFalse(self.check(nonce=nonce))
        for url in (ORIGIN,URL.replace(NONCE,'previous'),URL+'&devkit_probe='+NONCE):
            with self.subTest(url=url): self.assertFalse(self.check(url=url))

    def test_malformed_identity_is_not_pass(self):
        for value in (None,[],{},'page'):
            self.assertFalse(fixture_target_check(value,URL,NONCE)['ok'])
        for url in (None,'http://[invalid', 'http://127.0.0.1:invalid/'):
            self.assertFalse(fixture_url_matches(url,URL))

    def test_unrelated_tabs_do_not_block_unique_owned_page(self):
        own={'type':'page','targetId':'own','url':URL+'&extra=1#fragment'}
        stale={'type':'page','targetId':'stale','url':URL.replace(NONCE,'old')}
        self.assertEqual(select_fixture_target([stale,own],URL),'own')

    def test_multiple_owned_pages_are_not_arbitrarily_selected(self):
        own={'type':'page','targetId':'first','url':URL}
        other=dict(own,targetId='second')
        for targets in ([],[own,other],[dict(own,type='iframe')]):
            with self.assertRaises(RuntimeError): select_fixture_target(targets,URL)

    def test_check_evidence_does_not_log_page_text_or_nonce(self):
        value={'url':'https://private.invalid/secret','title':'private title','nonce':NONCE}
        result=fixture_target_check(value,URL,NONCE)
        self.assertEqual(set(result),{'ok','address_match','attempt_match'})
        self.assertNotIn(NONCE,str(result)); self.assertNotIn('private',str(result))

    def test_nonce_html_is_escaped_not_format_restricted(self):
        html=fixture_html('a"<script>bad()</script>')
        self.assertNotIn(b'<script>bad()',html)
        self.assertIn(b'&quot;&lt;script&gt;',html)
        self.assertNotIn(b'__DEVKIT_NONCE__',fixture_html())

    def test_http_fixture_preserves_attempt_with_extra_query(self):
        with ThreadingHTTPServer(('127.0.0.1',0),FixtureHandler) as server:
            thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
            opener=build_opener(ProxyHandler({}))
            origin=f'http://127.0.0.1:{server.server_port}'
            try:
                with opener.open(fixture_url(origin,NONCE)+'&debug=1',timeout=2) as reply:
                    html=reply.read()
                    self.assertIn(('content="'+NONCE+'"').encode(),html)
                    self.assertIn(b'id="activate"',html)
                with self.assertRaises(HTTPError) as caught:
                    opener.open(fixture_url(origin,NONCE)+'&devkit_probe=other',timeout=2)
                self.assertEqual(caught.exception.code,400)
            finally: server.shutdown(); thread.join(timeout=2)


@unittest.skipUnless(os.environ.get('DEVKIT_TEST_CHROME'), 'Opt-in: existing Chromium required')
class LiveFixtureIdentityTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_dom_title_decoration_and_relaxed_identity(self):
        # Real Chromium DOM, not a Hermes/HTTP/dialog E2E. Never relabel it as one.
        import websockets
        proc=log=cdp=None
        with tempfile.TemporaryDirectory(prefix='devkit-title-regression-') as profile:
            try:
                proc,log,ws,_=await launch_chrome(os.environ['DEVKIT_TEST_CHROME'],profile)
                cdp=CDP(await websockets.connect(ws,open_timeout=8))
                target=(await cdp.call('Target.createTarget',{'url':'about:blank'}))['targetId']
                sid=(await cdp.call('Target.attachToTarget',{'targetId':target,'flatten':True}))['sessionId']
                await cdp.call('Page.enable',session=sid)
                frame=(await cdp.call('Page.getFrameTree',session=sid))['frameTree']['frame']['id']
                await cdp.call('Page.setDocumentContent',{'frameId':frame,'html':fixture_html(NONCE).decode()},session=sid)
                for title in ('🐴 DevKit native dialog probe','','Different title'):
                    await cdp.js('document.title='+json.dumps(title),sid)
                    document=await cdp.js(FIXTURE_STATE,sid)
                    self.assertTrue(fixture_target_check(document,URL,NONCE,offline=True)['ok'])
                    self.assertTrue(document['controlsReady'])
                    self.assertFalse(fixture_target_check(document,URL,NONCE)['ok'])
                await cdp.js("document.querySelector('meta[name=devkit-dialog-probe]').remove()",sid)
                self.assertFalse(fixture_target_check(await cdp.js(FIXTURE_STATE,sid),URL,NONCE,offline=True)['ok'])
                print('REAL_DOM_IDENTITY=PASS; browser='+str((await cdp.call('Browser.getVersion'))['product']))
            finally:
                if cdp: await cdp.close()
                if proc: stop_owned(proc)
                if log: log.close()


if __name__=='__main__': unittest.main(verbosity=2)
