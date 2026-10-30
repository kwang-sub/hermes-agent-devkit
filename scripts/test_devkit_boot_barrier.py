#!/usr/bin/env python3
"""Actual shell barrier behavior in disposable paths, without s6/Docker."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]

class BarrierTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.ready=self.root/'ready'; self.trace=self.root/'trace'
        self.fake=self.root/'upstream'
        self.fake.write_text('#!/bin/sh\ntouch "'+str(self.trace)+'"\n');self.fake.chmod(0o755)
        self.env=dict(os.environ,S6_BEHAVIOUR_IF_STAGE2_FAILS='2')
    def script(self,name):
        text=(ROOT/'docker/cont-init.d'/name).read_text()
        text=text.replace('/run/devkit-ready',str(self.ready))
        text=text.replace('/opt/devkit/upstream/02-reconcile-profiles',str(self.fake))
        file=self.root/name;file.write_text(text);return file
    def test_reconcile_never_runs_without_boot_success(self):
        p=subprocess.run(['sh',str(self.script('02-devkit-reconcile-guard'))],capture_output=True)
        self.assertNotEqual(p.returncode,0);self.assertFalse(self.trace.exists())
    def test_symlink_marker_cannot_authorize_reconcile(self):
        self.ready.symlink_to(self.fake)
        p=subprocess.run(['sh',str(self.script('02-devkit-reconcile-guard'))],capture_output=True)
        self.assertNotEqual(p.returncode,0);self.assertFalse(self.trace.exists())
    def test_success_marker_runs_original_reconcile(self):
        self.ready.touch()
        p=subprocess.run(['sh',str(self.script('02-devkit-reconcile-guard'))],capture_output=True)
        self.assertEqual(p.returncode,0);self.assertTrue(self.trace.exists())
    def test_failed_migration_clears_prior_boot_marker(self):
        self.ready.touch();p=self.script('018-devkit-init')
        text=p.read_text().replace('s6-setuidgid hermes ','')
        text=text.replace('/opt/hermes/.venv/bin/python','/bin/false')
        p.write_text(text)
        result=subprocess.run(['sh',str(p)],env=self.env,capture_output=True)
        self.assertNotEqual(result.returncode,0);self.assertFalse(self.ready.exists())
    def test_successful_migration_publishes_marker(self):
        p=self.script('018-devkit-init')
        p.write_text(p.read_text().replace('s6-setuidgid hermes ','').replace('/opt/hermes/.venv/bin/python','/bin/true'))
        result=subprocess.run(['sh',str(p)],env=self.env,capture_output=True)
        self.assertEqual(result.returncode,0);self.assertTrue(self.ready.is_file())

if __name__=='__main__':unittest.main()
