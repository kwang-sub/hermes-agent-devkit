#!/usr/bin/env python3
"""Stage 3 optional feature boundaries and actual memory-DOM upload/frame tests."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import tempfile
import unittest
from unittest.mock import Mock
from ui_runtime.browser import BrowserPage,Locator
from ui_runtime.extensions import OptionalOperations,FrameView
from ui_runtime.suite import EnvironmentBlocked,Unsupported
from ui_runtime.visual import compare_png
from test_ui_stability import png


class OptionalUnitTests(unittest.TestCase):
    def page(self):
        p=Mock();p.context_id=None;p.target_id='parent';p.allowed_origins={('http','127.0.0.1',3107)}
        return p
    def test_features_are_opt_in(self):
        op=OptionalOperations(self.page())
        for feature in ['download','upload','clipboard','popup','frame']:
            with self.assertRaises(Unsupported):op.require(feature)
    def test_download_never_changes_default_context(self):
        p=self.page();op=OptionalOperations(p,enabled=['download'])
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(Unsupported):op.prepare_downloads(Path(temp)/'downloads')
        p.call.assert_not_called()
    def test_download_artifact_and_optional_content_validation(self):
        p=self.page();p.context_id='owned-context';op=OptionalOperations(p,enabled=['download'])
        with tempfile.TemporaryDirectory() as temp:
            root=op.prepare_downloads(Path(temp)/'downloads')
            (root/'file.txt').write_bytes(b'expected')
            digest=hashlib.sha256(b'expected').hexdigest()
            self.assertEqual(op.wait_download('file.txt',expected_sha256=digest)['status'],'PASS')
            self.assertEqual(op.wait_download('file.txt',expected_sha256='a'*64)['status'],'FAIL')
            self.assertEqual(op.wait_download('file.txt')['content_verification'],'NOT_RUN')
            with self.assertRaises(ValueError):op.wait_download('../outside.txt')
        self.assertEqual(p.call.call_args.args[1]['browserContextId'],'owned-context')
    def test_upload_cannot_read_outside_approved_directory(self):
        p=self.page();op=OptionalOperations(p,enabled=['upload'])
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):op.upload(Locator(selector='#file'),[Path('/etc/passwd')],approved_root=Path(temp))
        p.call.assert_not_called()
    def test_popup_only_uses_approved_origin_and_owner(self):
        p=self.page();op=OptionalOperations(p,enabled=['popup'],owner=Mock())
        with self.assertRaises(Unsupported):op.popup('https://external.invalid/')
        p.call.assert_not_called()
    def test_clipboard_does_not_read_shared_state(self):
        p=self.page();p.context_id='context';owner=Mock(disposable=False)
        with self.assertRaises(Unsupported):OptionalOperations(p,enabled=['clipboard'],owner=owner).clipboard_roundtrip('sample')
        p.call.assert_not_called()
    def test_frame_close_does_not_close_parent_tab(self):
        parent=BrowserPage(Mock(),'T','S',allowed_origins=['http://127.0.0.1:3107'])
        view=FrameView(parent,Locator(selector='iframe'),3,inherited=True)
        view.close();self.assertFalse(parent.closed);parent.transport.call.assert_not_called()
    def test_conditional_smoke_not_a_silent_fallback(self):
        source=Path(__file__).with_name('ui_runtime').joinpath('smoke.py').read_text()
        self.assertIn("if args.mode == 'hermes'",source)
        self.assertIn("provider='browser_exec' if args.mode=='hermes' else 'cdp-test'",source)
        self.assertIn("not product UI acceptance",source)


@unittest.skipUnless(importlib.util.find_spec('PIL'),'existing optional visual matcher dependency')
class VisualTests(unittest.TestCase):
    def test_missing_baseline_or_environment_is_not_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'current.png';p.write_bytes(png())
            r=compare_png(p,Path(temp)/'absent.png',current_context={'viewport':2},baseline_context={'viewport':2},max_changed_ratio=.01)
            self.assertEqual(r['status'],'NOT_RUN')
            self.assertEqual(compare_png(p,p,current_context={},baseline_context={},max_changed_ratio=0)['status'],'INCONCLUSIVE')
    def test_compare_preserves_baseline_and_uses_threshold(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as temp:
            a,b=Path(temp)/'a.png',Path(temp)/'b.png';a.write_bytes(png());b.write_bytes(png())
            digest=hashlib.sha256(b.read_bytes()).hexdigest();context={'viewport':(2,2),'browser':'test'}
            kw={'current_context':context,'baseline_context':context,'max_changed_ratio':0}
            self.assertEqual(compare_png(a,b,**kw)['status'],'PASS')
            Image.new('RGB',(2,2),(0,255,0)).save(a)
            self.assertEqual(compare_png(a,b,**kw)['status'],'FAIL')
            self.assertEqual(hashlib.sha256(b.read_bytes()).hexdigest(),digest)
    def test_mask_cannot_hide_entire_comparison(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'a.png';p.write_bytes(png())
            with self.assertRaises(ValueError):compare_png(p,p,current_context={'v':1},baseline_context={'v':1},max_changed_ratio=0,masks=[(0,0,2,2)])


@unittest.skipUnless(os.environ.get('DEVKIT_TEST_CHROME') and os.environ.get('DEVKIT_TEST_MEMORY')=='1','explicit memory DOM opt-in')
class MemoryOptionalTests(unittest.TestCase):
    def setUp(self):
        from ui_runtime.testing import TestBrowser
        self.browser=TestBrowser(os.environ['DEVKIT_TEST_CHROME'],allowed_origins=['http://127.0.0.1:3107'])
    def tearDown(self):self.assertEqual(self.browser.close()['status'],'PASS')
    def test_real_upload_scoped_file(self):
        p=self.browser.open_memory('<input id="file" type="file">')
        op=OptionalOperations(p,enabled=['upload'])
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'sample.txt';path.write_bytes(b'sample')
            self.assertEqual(op.upload(Locator(selector='#file'),[path],approved_root=Path(temp))['status'],'PASS')
            self.assertEqual(p.evaluate("document.querySelector('#file').files[0].name"),'sample.txt')
    def test_real_frame_input_and_parent_retained(self):
        p=self.browser.open_memory('''<iframe id="frame" srcdoc="<label for='child'>Child</label><input id='child'>"></iframe>''')
        p.wait("!!document.querySelector('#frame').contentDocument?.querySelector('#child')")
        child=OptionalOperations(p,enabled=['frame']).frame(Locator(selector='#frame'))
        child.fill(Locator(label='Child'),'FRAME')
        self.assertEqual(child.evaluate("document.querySelector('#child').value"),'FRAME')
        child.close();self.assertTrue(p.healthy())


if __name__=='__main__':unittest.main(verbosity=2)
