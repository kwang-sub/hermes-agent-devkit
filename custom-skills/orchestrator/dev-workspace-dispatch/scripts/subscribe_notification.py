#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

SHARED_HELPER = Path("/opt/data/shared/scripts/kanban_notify_subscribe.py")
REPO_FALLBACK = Path(__file__).resolve().parents[4] / "shared" / "scripts" / "kanban_notify_subscribe.py"
DEFAULT_HERMES_PYTHON = Path("/opt/hermes/.venv/bin/python")


def hermes_python() -> Path:
    override = (os.getenv("HERMES_PYTHON") or "").strip()
    if override:
        return Path(override).expanduser()
    if DEFAULT_HERMES_PYTHON.is_file():
        return DEFAULT_HERMES_PYTHON
    return Path(sys.executable)


def main() -> int:
    helper = SHARED_HELPER if SHARED_HELPER.is_file() else REPO_FALLBACK
    runtime = hermes_python()
    try:
        result = subprocess.run([str(runtime), str(helper), *sys.argv[1:]])
    except OSError as exc:
        print("NOTIFY_STATUS=warning")
        print("NOTIFY_VERIFIED=false")
        print(f"NOTIFY_ERROR=Hermes runtime Python unavailable: {runtime} ({type(exc).__name__})")
        return 0
    if result.returncode != 0:
        print("NOTIFY_STATUS=warning")
        print("NOTIFY_VERIFIED=false")
        print(f"NOTIFY_ERROR=notification helper exited with code {result.returncode}")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
