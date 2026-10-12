#!/usr/bin/env python3
"""Run the approved managed-dialog fixture/probe through the existing adapter."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import uuid


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact-dir',type=Path,required=True)
    parser.add_argument('--profile-home',type=Path)
    parser.add_argument('--hermes-root',type=Path,default=Path('/opt/hermes'))
    args=parser.parse_args()
    if args.profile_home:
        if not args.profile_home.is_dir(): parser.error('profile-home is missing')
        os.environ['HERMES_HOME']=str(args.profile_home.resolve())
    if args.hermes_root.is_dir(): sys.path.insert(0,str(args.hermes_root))
    from browser_runtime_adapter import run
    scripts=Path(__file__).resolve().parent
    attempt='dialog-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    destination=args.artifact_dir.resolve()/attempt
    # Adapter owns fixture server and probe lifecycle. Probe owns only its named
    # managed browser, and calls the official browser_dialog in that same process.
    report=run(
        [sys.executable,str(scripts/'browser_dialog_fixture.py'),'--port','{port}'],
        [sys.executable,str(scripts/'probe_managed_dialog.py'),'--mode','hermes',
         '--hermes-root',str(args.hermes_root),'--origin','{origin}','--output','{result_file}'],
        destination,attempt,'browser_exec',startup_timeout=20,probe_timeout=180,
        cwd=scripts,ready_path='/')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    print('REPORT_PATH='+str(destination/'browser-runtime-report.json'))
    return 0 if report['execution_status']=='PASS' else 2


if __name__=='__main__': raise SystemExit(main())
