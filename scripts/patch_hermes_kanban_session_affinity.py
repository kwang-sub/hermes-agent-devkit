#!/usr/bin/env python3
from __future__ import annotations
import argparse, py_compile, tempfile
from pathlib import Path

PATCH_MARKER = "from hermes_cli.devkit_session_affinity import choose_worker_session"
ANCHOR = '''    worker_toolsets = _resolve_worker_cli_toolsets(env.get("HERMES_HOME"))
    if worker_toolsets:
        cmd.extend(["--toolsets", ",".join(worker_toolsets)])
    cmd.extend([
        "chat",
        "-q", prompt,
    ])
'''
REPLACEMENT = '''    worker_toolsets = _resolve_worker_cli_toolsets(env.get("HERMES_HOME"))
    if worker_toolsets:
        cmd.extend(["--toolsets", ",".join(worker_toolsets)])
    from hermes_cli.devkit_session_affinity import choose_worker_session
    _devkit_session = choose_worker_session(
        task=task, workspace=workspace, profile=profile_arg,
        profile_home=env.get("HERMES_HOME"),
        kanban_db_path=str(kanban_db_path(board=board)),
        worker_toolsets=worker_toolsets or (),
    )
    env["HERMES_KANBAN_SESSION_MODE"] = _devkit_session.mode
    if _devkit_session.session_id:
        env["HERMES_KANBAN_AFFINITY_SESSION_ID"] = _devkit_session.session_id
        cmd.extend(["--resume", _devkit_session.session_id])
    else:
        env.pop("HERMES_KANBAN_AFFINITY_SESSION_ID", None)
    cmd.extend([
        "chat",
        "-q", prompt,
    ])
'''
CONTEXT = ('prompt = f"work kanban task {task.id}"', '_resolve_worker_cli_toolsets', 'profile_arg', 'kanban_db_path')

def strict_compile(path: Path) -> None:
    with tempfile.TemporaryDirectory() as d:
        py_compile.compile(str(path), cfile=str(Path(d)/"x.pyc"), doraise=True)

def candidate(path: Path) -> bool:
    try: s=path.read_text(encoding="utf-8")
    except Exception: return False
    return PATCH_MARKER in s or (s.count(ANCHOR)==1 and all(x in s for x in CONTEXT))

def find_target(root: Path) -> Path:
    found=[p for p in root.rglob("*.py") if candidate(p)]
    if len(found)!=1:
        raise RuntimeError(f"expected exactly one Hermes Kanban worker patch target under {root}; found {len(found)}: {found[:10]}")
    return found[0]

def patch_source(path: Path) -> str:
    s=path.read_text(encoding="utf-8")
    if PATCH_MARKER in s:
        strict_compile(path); return "already-patched"
    if not all(x in s for x in CONTEXT) or s.count(ANCHOR)!=1:
        raise RuntimeError(f"{path}: compatible Kanban worker command contract not found")
    path.write_text(s.replace(ANCHOR, REPLACEMENT, 1), encoding="utf-8")
    strict_compile(path); return "patched"

def self_test() -> None:
    sample='''def _resolve_worker_cli_toolsets(home): return []\ndef kanban_db_path(board=None): return "/tmp/k"\ndef spawn_worker(task, workspace, *, board=None):\n    profile_arg=task.assignee\n    prompt = f"work kanban task {task.id}"\n    env={"HERMES_HOME":"/tmp/p"}\n    cmd=["hermes"]\n    worker_toolsets = _resolve_worker_cli_toolsets(env.get("HERMES_HOME"))\n    if worker_toolsets:\n        cmd.extend(["--toolsets", ",".join(worker_toolsets)])\n    cmd.extend([\n        "chat",\n        "-q", prompt,\n    ])\n'''
    with tempfile.TemporaryDirectory() as d:
        root=Path(d); p=root/"kanban_dispatcher.py"; p.write_text(sample,encoding="utf-8")
        assert find_target(root)==p
        assert patch_source(p)=="patched"
        assert patch_source(p)=="already-patched"
        text=p.read_text(encoding="utf-8")
        assert 'cmd.extend(["--resume", _devkit_session.session_id])' in text
        assert text.index('cmd.extend(["--resume"') < text.index('    cmd.extend([\n        "chat"')
    print("Hermes Kanban session-affinity patch self-test passed")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("path", nargs="?", type=Path); ap.add_argument("--search-root", type=Path); ap.add_argument("--self-test", action="store_true"); a=ap.parse_args()
    if a.self_test: self_test(); return
    target=find_target(a.search_root) if a.search_root else a.path
    if target is None: ap.error("path or --search-root required")
    print(f"Hermes Kanban session-affinity source state={patch_source(target)}: {target}")
if __name__ == "__main__": main()
