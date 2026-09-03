#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import runpy

SHARED_HELPER = Path("/opt/data/shared/scripts/kanban_notify_subscribe.py")
REPO_FALLBACK = Path(__file__).resolve().parents[4] / "shared" / "scripts" / "kanban_notify_subscribe.py"


def main() -> int:
    helper = SHARED_HELPER if SHARED_HELPER.is_file() else REPO_FALLBACK
    namespace = runpy.run_path(str(helper), run_name="kanban_notify_shared")
    return int(namespace["main"]())


if __name__ == "__main__":
    raise SystemExit(main())
