#!/usr/bin/env python3
from __future__ import annotations

import argparse
import py_compile
import tempfile
from pathlib import Path

PATCH_MARKER = "def _devkit_run_flow_model_transition("
POLICY_MARKER = "MODEL_POLICY_SNAPSHOT_V1"

HELPERS = r'''

# ---- BEGIN DEVKIT FLOW MODEL TRANSITION ----
_DEVKIT_MODEL_POLICY_SNAPSHOT_MARKER = "MODEL_POLICY_SNAPSHOT_V1"
_DEVKIT_FLOW_MODEL_POLICY_SCRIPT = "/opt/data/shared/scripts/flow_model_policy.py"


def _devkit_has_flow_model_policy(kb, conn, tid: str) -> bool:
    """True only for DevKit tasks carrying the durable Coder/Reviewer model contract."""
    task = kb.get_task(conn, tid)
    body = str(getattr(task, "body", "") or "") if task is not None else ""
    if "Coder Model Tier:" in body and "Reviewer Model:" in body:
        return True
    try:
        comments = kb.list_comments(conn, tid)
    except Exception:
        comments = []
    return any(
        _DEVKIT_MODEL_POLICY_SNAPSHOT_MARKER in str(getattr(comment, "body", "") or "")
        for comment in comments
    )


def _devkit_run_flow_model_transition(action: str, tid: str) -> tuple[bool, str]:
    """Run model-policy mutation only from the dispatcher-owned MCP worker context."""
    if os.environ.get("HERMES_KANBAN_TASK") != tid:
        return False, "dispatcher task ownership mismatch"
    if not _is_dispatcher_owned_worker():
        return False, "context is not dispatcher-owned"
    from pathlib import Path
    import subprocess
    import sys

    policy = Path(_DEVKIT_FLOW_MODEL_POLICY_SCRIPT)
    if not policy.is_file():
        return False, f"flow model policy helper is missing: {policy}"
    try:
        result = subprocess.run(
            [sys.executable, str(policy), action],
            text=True,
            capture_output=True,
            timeout=30,
            env=os.environ.copy(),
            check=False,
        )
    except Exception as exc:
        return False, f"flow model policy {action} failed to start: {type(exc).__name__}"
    output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part and part.strip())
    expected = {
        "review-enter": "STATUS=review-default-ready",
        "changes-return": "STATUS=coder-model-restored",
    }.get(action)
    if result.returncode != 0:
        return False, output or f"flow model policy {action} exited {result.returncode}"
    if expected and expected not in result.stdout:
        return False, output or f"flow model policy {action} did not emit {expected}"
    return True, output or expected or "ok"


def _devkit_transition_or_reject(action: str, tid: str) -> None:
    ok, detail = _devkit_run_flow_model_transition(action, tid)
    if not ok:
        raise _Reject(f"DevKit model transition {action} failed: {detail}")


def _devkit_rollback_or_reject(action: str, tid: str, lifecycle_error: str) -> None:
    ok, detail = _devkit_run_flow_model_transition(action, tid)
    if not ok:
        raise _Reject(
            f"{lifecycle_error}; DevKit model rollback {action} also failed: {detail}"
        )
# ---- END DEVKIT FLOW MODEL TRANSITION ----
'''

REQUEST_REVIEW_OLD = r'''@_kanban_handler("kanban_request_review")
def _handle_request_review(args: dict, **kw) -> str:
    """Move implementation into the first-class review phase."""
    tid = _worker_guard("kanban_request_review", args)
    summary = _redact(_require_text(
        args, "summary", "summary is required — describe what was implemented and how it "
        "was verified so the reviewer has context"))
    metadata = args.get("metadata")
    _require_dict_metadata(metadata)
    if metadata is not None:
        metadata = _redact_metadata(metadata)
        _check(metadata is not None, "metadata could not be safely serialized")
    metadata = _stamp_worker_session_metadata(tid, metadata)
    # Reviewer is model-supplied free text stored durably on the event payload.
    reviewer = _redact_opt(args.get("reviewer") or None)
    with _board(args.get("board")) as (kb, conn):
        _goal_gate("kanban_request_review", kb.get_task(conn, tid), tid, summary)
        ok, fail_reason = kb.request_review(
            conn, tid, summary=summary, metadata=metadata, reviewer=reviewer,
            expected_run_id=_worker_run_id(tid), with_reason=True)
        _check(ok, f"could not request review for {tid}: "
                   f"{fail_reason or 'unknown id or not in running/ready'}")
        return _ok_landed(kb, conn, tid, "review")
'''

REQUEST_REVIEW_NEW = r'''@_kanban_handler("kanban_request_review")
def _handle_request_review(args: dict, **kw) -> str:
    """Move implementation into review, applying DevKit Reviewer DEFAULT atomically with rollback."""
    tid = _worker_guard("kanban_request_review", args)
    summary = _redact(_require_text(
        args, "summary", "summary is required — describe what was implemented and how it "
        "was verified so the reviewer has context"))
    metadata = args.get("metadata")
    _require_dict_metadata(metadata)
    if metadata is not None:
        metadata = _redact_metadata(metadata)
        _check(metadata is not None, "metadata could not be safely serialized")
    metadata = _stamp_worker_session_metadata(tid, metadata)
    reviewer = _redact_opt(args.get("reviewer") or None)

    with _board(args.get("board")) as (kb, conn):
        task = kb.get_task(conn, tid)
        _goal_gate("kanban_request_review", task, tid, summary)
        managed_model_policy = _devkit_has_flow_model_policy(kb, conn, tid)

    if managed_model_policy:
        _devkit_transition_or_reject("review-enter", tid)

    try:
        with _board(args.get("board")) as (kb, conn):
            ok, fail_reason = kb.request_review(
                conn, tid, summary=summary, metadata=metadata, reviewer=reviewer,
                expected_run_id=_worker_run_id(tid), with_reason=True)
            if not ok:
                lifecycle_error = (
                    f"could not request review for {tid}: "
                    f"{fail_reason or 'unknown id or not in running/ready'}"
                )
                if managed_model_policy:
                    _devkit_rollback_or_reject("changes-return", tid, lifecycle_error)
                raise _Reject(lifecycle_error)
            return _ok_landed(kb, conn, tid, "review")
    except _Reject:
        raise
    except Exception as exc:
        lifecycle_error = f"kanban_request_review raised {type(exc).__name__}: {exc}"
        if managed_model_policy:
            _devkit_rollback_or_reject("changes-return", tid, lifecycle_error)
        raise
'''

REQUEST_CHANGES_OLD = r'''@_kanban_handler("kanban_request_changes")
def _handle_request_changes(args: dict, **kw) -> str:
    """Return a reviewer-owned running task to its implementer."""
    tid = _worker_guard("kanban_request_changes", args)
    reason = _redact(
        _require_text(args, "reason", "reason is required — describe the changes needed"))
    with _board(args.get("board")) as (kb, conn):
        ok, detail = kb.request_changes(
            conn, tid, reason=reason, expected_run_id=_worker_run_id(tid))
        _check(ok, f"could not request changes for {tid}: {detail or 'invalid review state'}")
        return _ok_landed(kb, conn, tid, "ready", implementer=detail)
'''

REQUEST_CHANGES_NEW = r'''@_kanban_handler("kanban_request_changes")
def _handle_request_changes(args: dict, **kw) -> str:
    """Return review to Coder, restoring the approved DevKit Coder model with rollback."""
    tid = _worker_guard("kanban_request_changes", args)
    reason = _redact(
        _require_text(args, "reason", "reason is required — describe the changes needed"))

    with _board(args.get("board")) as (kb, conn):
        managed_model_policy = _devkit_has_flow_model_policy(kb, conn, tid)

    if managed_model_policy:
        _devkit_transition_or_reject("changes-return", tid)

    try:
        with _board(args.get("board")) as (kb, conn):
            ok, detail = kb.request_changes(
                conn, tid, reason=reason, expected_run_id=_worker_run_id(tid))
            if not ok:
                lifecycle_error = f"could not request changes for {tid}: {detail or 'invalid review state'}"
                if managed_model_policy:
                    _devkit_rollback_or_reject("review-enter", tid, lifecycle_error)
                raise _Reject(lifecycle_error)
            return _ok_landed(kb, conn, tid, "ready", implementer=detail)
    except _Reject:
        raise
    except Exception as exc:
        lifecycle_error = f"kanban_request_changes raised {type(exc).__name__}: {exc}"
        if managed_model_policy:
            _devkit_rollback_or_reject("review-enter", tid, lifecycle_error)
        raise
'''


def strict_compile(path: Path) -> None:
    with tempfile.TemporaryDirectory() as directory:
        py_compile.compile(str(path), cfile=str(Path(directory) / "x.pyc"), doraise=True)


def patch_source(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    if PATCH_MARKER in source:
        strict_compile(path)
        return "already-patched"

    if source.count(REQUEST_REVIEW_OLD) != 1:
        raise RuntimeError(f"{path}: compatible kanban_request_review handler not found")
    if source.count(REQUEST_CHANGES_OLD) != 1:
        raise RuntimeError(f"{path}: compatible kanban_request_changes handler not found")

    source = source.replace(REQUEST_REVIEW_OLD, HELPERS + "\n" + REQUEST_REVIEW_NEW, 1)
    source = source.replace(REQUEST_CHANGES_OLD, REQUEST_CHANGES_NEW, 1)
    path.write_text(source, encoding="utf-8")
    strict_compile(path)
    return "patched"


def _fixture() -> str:
    return (
        'import os\n'
        'def _is_dispatcher_owned_worker(): return True\n'
        'class _Reject(Exception): pass\n'
        'def _kanban_handler(name): return lambda fn: fn\n'
        'def _worker_guard(name, args): return "t_demo"\n'
        'def _redact(x): return x\n'
        'def _require_text(args, name, message=None): return args.get(name, "x")\n'
        'def _require_dict_metadata(x): pass\n'
        'def _redact_metadata(x): return x\n'
        'def _check(c, m):\n    if not c: raise _Reject(m)\n'
        'def _stamp_worker_session_metadata(tid, m): return m\n'
        'def _redact_opt(x): return x\n'
        'def _worker_run_id(tid): return 1\n'
        'def _ok_landed(kb, conn, tid, status, **kw): return status\n'
        'class B:\n    def __enter__(self): return (self, self)\n    def __exit__(self,*a): pass\n    def get_task(self,*a): return type("T",(),{"body":""})()\n    def list_comments(self,*a): return []\n    def request_review(self,*a,**k): return (True,None)\n    def request_changes(self,*a,**k): return (True,"coder")\n'
        'def _board(x): return B()\n'
        'def _goal_gate(*a): pass\n\n'
        + REQUEST_REVIEW_OLD + '\n' + REQUEST_CHANGES_OLD
    )


def self_test() -> None:
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory) / "kanban_tools.py"
        target.write_text(_fixture(), encoding="utf-8")
        assert patch_source(target) == "patched"
        assert patch_source(target) == "already-patched"
        source = target.read_text(encoding="utf-8")
        for term in (
            PATCH_MARKER,
            POLICY_MARKER,
            '_devkit_transition_or_reject("review-enter", tid)',
            '_devkit_rollback_or_reject("changes-return", tid, lifecycle_error)',
            '_devkit_transition_or_reject("changes-return", tid)',
            '_devkit_rollback_or_reject("review-enter", tid, lifecycle_error)',
        ):
            assert term in source, term
    print("Hermes Kanban model transition patch self-test passed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if args.path is None:
        parser.error("path required")
    print(f"Hermes Kanban model transition source state={patch_source(args.path)}: {args.path}")


if __name__ == "__main__":
    main()
