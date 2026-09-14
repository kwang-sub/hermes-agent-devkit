#!/usr/bin/env python3
from __future__ import annotations

import argparse
import py_compile
import tempfile
from pathlib import Path

PATCH_MARKER = "from hermes_cli.devkit_kanban_single_worker import live_prior_worker"
ANCHOR = '''    claim = _kb.claim_review_task if lane == "review" else _kb.claim_task
'''
REPLACEMENT = '''    from hermes_cli.devkit_kanban_single_worker import live_prior_worker
    _devkit_prior_worker = live_prior_worker(
        conn,
        task_id,
        pid_alive=_kb._pid_alive,
        host_prefix=_kb._host_prefix(),
    )
    if _devkit_prior_worker is not None:
        # The previous run is terminal in Kanban, but its process still owns the
        # workspace. Keep the card queued until that process is really gone.
        result.respawn_guarded.append((task_id, "live_prior_worker"))
        return False
    claim = _kb.claim_review_task if lane == "review" else _kb.claim_task
'''
CONTEXT = (
    "def _dispatch_lane_task(",
    "task_id",
    "result.respawn_guarded",
    "_kb.claim_task",
    "_kb.claim_review_task",
    "_kb._pid_alive",
    "_kb._host_prefix",
)


def strict_compile(path: Path) -> None:
    with tempfile.TemporaryDirectory() as directory:
        py_compile.compile(str(path), cfile=str(Path(directory) / "x.pyc"), doraise=True)


def candidate(path: Path) -> bool:
    try:
        source = path.read_text(encoding="utf-8")
    except Exception:
        return False
    if PATCH_MARKER in source:
        return True
    return source.count(ANCHOR) == 1 and all(term in source for term in CONTEXT)


def find_target(root: Path) -> Path:
    found = [path for path in root.rglob("*.py") if candidate(path)]
    if len(found) != 1:
        raise RuntimeError(
            "expected exactly one Hermes Kanban dispatcher patch target under "
            f"{root}; found {len(found)}: {found[:10]}"
        )
    return found[0]


def patch_source(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    if PATCH_MARKER in source:
        strict_compile(path)
        return "already-patched"
    if source.count(ANCHOR) != 1 or not all(term in source for term in CONTEXT):
        raise RuntimeError(f"{path}: compatible Kanban dispatch lane contract not found")
    path.write_text(source.replace(ANCHOR, REPLACEMENT, 1), encoding="utf-8")
    strict_compile(path)
    return "patched"


def _sample() -> str:
    return '''class _KB:\n    @staticmethod\n    def claim_review_task(*a, **k): return None\n    @staticmethod\n    def claim_task(*a, **k): return None\n    @staticmethod\n    def _pid_alive(pid): return True\n    @staticmethod\n    def _host_prefix(): return "host:"\n_kb = _KB()\nclass Result:\n    def __init__(self): self.respawn_guarded=[]\ndef _dispatch_lane_task(conn, task_id, lane, result):\n    claim = _kb.claim_review_task if lane == "review" else _kb.claim_task\n    claimed = claim(conn, task_id, ttl_seconds=60)\n    return claimed\n'''


def self_test() -> None:
    with tempfile.TemporaryDirectory(prefix="hermes-kanban-single-worker-patch-") as directory:
        root = Path(directory)
        target = root / "kanban_db_dispatch.py"
        target.write_text(_sample(), encoding="utf-8")
        assert find_target(root) == target
        assert patch_source(target) == "patched"
        assert patch_source(target) == "already-patched"
        text = target.read_text(encoding="utf-8")
        assert text.count(PATCH_MARKER) == 1
        assert 'result.respawn_guarded.append((task_id, "live_prior_worker"))' in text
        assert text.index(PATCH_MARKER) < text.index("claim = _kb.claim_review_task")
    print("Hermes Kanban single-active-worker patch self-test passed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument("--search-root", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return
    target = find_target(args.search_root) if args.search_root else args.path
    if target is None:
        parser.error("path or --search-root required")
    print(f"Hermes Kanban single-active-worker source state={patch_source(target)}: {target}")


if __name__ == "__main__":
    main()
