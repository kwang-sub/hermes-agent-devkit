#!/usr/bin/env python3
"""Canonical execution layout: installed and repository copies have identical imports."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import shutil
import unittest
ROOT=Path(__file__).resolve().parents[1]
class LayoutTest(unittest.TestCase):
    def test_installed_layout_without_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            installed=Path(tmp)/'devkit'
            shutil.copytree(ROOT/'scripts/verification',installed/'scripts/verification')
            lib=installed/'custom-skills/_lib';lib.mkdir(parents=True)
            shutil.copy2(ROOT/'custom-skills/_lib/process_execution.py',lib/'process_execution.py')
            env=os.environ.copy()
            for key in list(env):
                if key.startswith('HERMES_KANBAN_'):del env[key]
            for helper in (installed/'scripts/verification').glob('*.py'):
                p=subprocess.run([sys.executable,str(helper),'--help'],env=env,capture_output=True,text=True,timeout=10)
                self.assertEqual(p.returncode,0,p.stderr)
            self.assertFalse((installed/'custom-skills/coder').exists())
    def test_image_delivers_canonical_helpers(self):
        text=(ROOT/'Dockerfile').read_text()
        self.assertIn('COPY scripts/verification /opt/devkit/scripts/verification',text)
        self.assertIn('/opt/devkit/custom-skills/_lib/process_execution.py',text)
        self.assertNotIn('devkit_worker_startup.py',text)
if __name__=='__main__': unittest.main()
