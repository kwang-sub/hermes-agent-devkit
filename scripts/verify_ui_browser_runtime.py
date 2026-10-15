#!/usr/bin/env python3
"""Run a bounded, model-free UI smoke without touching an application or Kanban."""
import argparse
import json
import os
from pathlib import Path
import sys
import uuid
from browser_runtime_adapter import run


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact-dir',type=Path,required=True)
    parser.add_argument('--profile-home',type=Path)
    parser.add_argument('--hermes-root',default='/opt/hermes')
    parser.add_argument('--mode',choices=['hermes','cdp-test'],default='hermes')
    parser.add_argument('--chrome',help='Existing executable; development cdp-test mode only')
    parser.add_argument('--features',default='',help='Approved optional capabilities: korean-font,upload,download,popup,frame,clipboard')
    args=parser.parse_args()
    if args.profile_home:
        if not args.profile_home.is_dir():parser.error('profile-home is missing')
        os.environ['HERMES_HOME']=str(args.profile_home.resolve())
    if args.mode=='hermes' and args.chrome:parser.error('do not replace the managed browser executable')
    if args.mode=='cdp-test' and not args.chrome:parser.error('cdp-test requires an installed --chrome')
    root=Path(__file__).resolve().parent
    command=[sys.executable,'-m','ui_runtime.smoke','probe','--origin','{origin}','--output','{result_file}',
             '--mode',args.mode,'--hermes-root',args.hermes_root,'--features',args.features]
    if args.chrome:command.extend(['--chrome',args.chrome])
    destination=args.artifact_dir.resolve()/('ui-'+uuid.uuid4().hex[:12])
    report=run([sys.executable,'-m','ui_runtime.smoke','serve','--port','{port}'],command,destination,
               'ui-smoke','browser_exec' if args.mode=='hermes' else 'cdp-test',
               startup_timeout=20,probe_timeout=600,cwd=root)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    print('REPORT_PATH='+str(destination/'browser-runtime-report.json'))
    return 0 if report['execution_status']=='PASS' else 2


if __name__=='__main__':raise SystemExit(main())
