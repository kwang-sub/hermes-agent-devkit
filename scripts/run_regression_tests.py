#!/usr/bin/env python3
"""Run all retained suites in separate processes; no fixture module name collisions."""
from pathlib import Path
import json
import os
import re
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
def main():
    suites=sorted({*ROOT.glob('scripts/test_*.py'),*ROOT.glob('scripts/verification/tests/test_*.py'),
                   *ROOT.glob('custom-skills/*/*/tests/test_*.py')})
    results=[]
    for path in suites:
        start=time.monotonic(); relative=str(path.relative_to(ROOT))
        try:
            proc=subprocess.run([sys.executable,str(path)],cwd=ROOT,text=True,capture_output=True,timeout=180)
            output=proc.stdout+proc.stderr; code=proc.returncode
        except subprocess.TimeoutExpired:
            output='Suite timed out; not PASS';code=124
        match=re.search(r'Ran (\d+) tests?',output)
        results.append(dict(path=relative,exit_code=code,tests=int(match.group(1)) if match else None,
                            seconds=round(time.monotonic()-start,2)))
        print(f'[{"PASS" if code==0 else "FAIL"}] {relative}',flush=True)
        print(output,flush=True)
    report=Path(os.getenv('DEVKIT_TEST_REPORT','/tmp/devkit-regression-results.json'))
    report.write_text(json.dumps(results,indent=2)+'\n')
    failures=[r for r in results if r['exit_code']]
    print(f'SUITES={len(results)} FAILURES={len(failures)} UNIT_TESTS={sum(r["tests"] or 0 for r in results)}')
    return bool(failures)
if __name__=='__main__': raise SystemExit(main())
