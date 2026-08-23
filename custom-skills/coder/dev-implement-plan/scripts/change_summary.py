#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import subprocess
import sys

def run(cmd, check=True):
    p = subprocess.run(cmd, text=True, capture_output=True)
    if check and p.returncode != 0:
        print((p.stderr or p.stdout).strip(), file=sys.stderr)
        raise SystemExit(p.returncode)
    return p

root = Path(run(["git", "rev-parse", "--show-toplevel"]).stdout.strip()).resolve()
branch = run(["git", "-C", str(root), "branch", "--show-current"]).stdout.strip()
status = run(["git", "-C", str(root), "status", "--short", "--untracked-files=all"]).stdout.rstrip()
tracked = run(["git", "-C", str(root), "diff", "--name-only", "HEAD", "--"]).stdout.splitlines()
untracked = run(["git", "-C", str(root), "ls-files", "--others", "--exclude-standard"]).stdout.splitlines()
diff_check = run(["git", "-C", str(root), "diff", "--check"], check=False)

print(f"WORKSPACE={root}")
print(f"BRANCH={branch}")
print(f"TRACKED_CHANGED_COUNT={len(tracked)}")
for i, path in enumerate(tracked, 1):
    print(f"TRACKED_{i}={path}")
print(f"UNTRACKED_COUNT={len(untracked)}")
for i, path in enumerate(untracked, 1):
    print(f"UNTRACKED_{i}={path}")
print(f"DIFF_CHECK={'PASS' if diff_check.returncode == 0 else 'FAIL'}")
print("STATUS_BEGIN")
print(status)
print("STATUS_END")
