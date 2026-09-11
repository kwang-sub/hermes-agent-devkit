#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import py_compile
import tempfile
from pathlib import Path

PATCH_MARKER = "def _devkit_run_flow_model_transition("
POLICY_MARKER = "MODEL_POLICY_SNAPSHOT_V1"
REVIEW_WRAPPER_MARKER = "_devkit_original_handle_request_review = _handle_request_review"
CHANGES_WRAPPER_MARKER = "_devkit_original_handle_request_changes = _handle_request_changes"

HELPERS = r'''

# ---- BEGIN DEVKIT FLOW MODEL TRANSITION ----
_DEVKIT_MODEL_POLICY_SNAPSHOT_MARKER = "MODEL_POLICY_SNAPSHOT_V1"
_DEVKIT_FLOW_MODEL_POLICY_SCRIPT = "/opt/data/shared/scripts/flow_model_policy.py"


def _devkit_open_kanban_board(board):
    """Open the Kanban DB across legacy and current Hermes layouts."""
    from hermes_cli import kanban_db as kb
    try:
        from hermes_cli import kanban_db_connect as kbc
    except ImportError:
        return kb, kb.connect(board=board)
    return kb, kbc.connect(board=board)


def _devkit_model_policy_state(board, tid: str) -> tuple[bool, bool, str]:
    """Return (inspection_ok, managed_by_devkit, detail) for one task."""
    conn = None
    try:
        kb, conn = _devkit_open_kanban_board(board)
        task = kb.get_task(conn, tid)
        if task is None:
            return False, False, f"task {tid} not found during model-policy inspection"
        body = str(getattr(task, "body", "") or "")
        if "Coder Model Tier:" in body and "Reviewer Model:" in body:
            return True, True, "task body model policy"
        try:
            comments = kb.list_comments(conn, tid)
        except Exception:
            comments = []
        managed = any(
            _DEVKIT_MODEL_POLICY_SNAPSHOT_MARKER in str(getattr(comment, "body", "") or "")
            for comment in comments
        )
        return True, managed, "durable model policy comment" if managed else "no DevKit model policy"
    except Exception as exc:
        return False, False, f"{type(exc).__name__}: {exc}"
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _devkit_transition_context(args: dict) -> tuple[str, bool, str | None]:
    """Enable transition wrapping only for the dispatcher-owned task itself."""
    import os

    env_tid = str(os.environ.get("HERMES_KANBAN_TASK") or "")
    tid = str(args.get("task_id") or env_tid or "")
    if not env_tid or not tid or tid != env_tid:
        return tid, False, None
    try:
        if not _is_dispatcher_owned_worker():
            return tid, False, None
    except Exception as exc:
        return tid, False, f"dispatcher ownership check failed: {type(exc).__name__}: {exc}"

    ok, managed, detail = _devkit_model_policy_state(args.get("board"), tid)
    if not ok:
        return tid, False, detail
    return tid, managed, None


def _devkit_run_flow_model_transition(action: str, tid: str) -> tuple[bool, str]:
    """Run model-policy mutation only from the dispatcher-owned worker context."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    if os.environ.get("HERMES_KANBAN_TASK") != tid:
        return False, "dispatcher task ownership mismatch"
    try:
        if not _is_dispatcher_owned_worker():
            return False, "context is not dispatcher-owned"
    except Exception as exc:
        return False, f"dispatcher ownership check failed: {type(exc).__name__}: {exc}"

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


def _devkit_result_is_error(result) -> bool:
    """Recognize Hermes structured tool errors without depending on handler internals."""
    import json

    if not isinstance(result, str):
        return False
    try:
        payload = json.loads(result)
    except Exception:
        return False
    return isinstance(payload, dict) and (
        payload.get("ok") is False or bool(payload.get("error"))
    )


def _devkit_transition_failure(action: str, detail: str):
    return tool_error(f"DevKit model transition {action} failed: {detail}")


def _devkit_rollback_after_result(action: str, tid: str, result):
    ok, detail = _devkit_run_flow_model_transition(action, tid)
    if ok:
        return result
    return tool_error(
        f"Kanban lifecycle failed and DevKit model rollback {action} also failed: {detail}"
    )
# ---- END DEVKIT FLOW MODEL TRANSITION ----
'''

REVIEW_WRAPPER = r'''

# DevKit wraps the upstream handler instead of replacing its body. This keeps
# upstream validation/redaction/goal/reviewer-profile behavior intact across
# Hermes versions while adding the model transition around the lifecycle call.
_devkit_original_handle_request_review = _handle_request_review


def _handle_request_review(args: dict, **kw) -> str:
    tid, managed_model_policy, inspection_error = _devkit_transition_context(args)
    if inspection_error is not None:
        return tool_error(f"DevKit model policy inspection failed: {inspection_error}")
    if not managed_model_policy:
        return _devkit_original_handle_request_review(args, **kw)

    ok, detail = _devkit_run_flow_model_transition("review-enter", tid)
    if not ok:
        return _devkit_transition_failure("review-enter", detail)

    try:
        result = _devkit_original_handle_request_review(args, **kw)
    except Exception:
        rollback_ok, rollback_detail = _devkit_run_flow_model_transition("changes-return", tid)
        if not rollback_ok:
            raise RuntimeError(
                f"kanban_request_review raised and DevKit rollback changes-return also failed: {rollback_detail}"
            )
        raise

    if _devkit_result_is_error(result):
        return _devkit_rollback_after_result("changes-return", tid, result)
    return result
'''

CHANGES_WRAPPER = r'''

_devkit_original_handle_request_changes = _handle_request_changes


def _handle_request_changes(args: dict, **kw) -> str:
    tid, managed_model_policy, inspection_error = _devkit_transition_context(args)
    if inspection_error is not None:
        return tool_error(f"DevKit model policy inspection failed: {inspection_error}")
    if not managed_model_policy:
        return _devkit_original_handle_request_changes(args, **kw)

    ok, detail = _devkit_run_flow_model_transition("changes-return", tid)
    if not ok:
        return _devkit_transition_failure("changes-return", detail)

    try:
        result = _devkit_original_handle_request_changes(args, **kw)
    except Exception:
        rollback_ok, rollback_detail = _devkit_run_flow_model_transition("review-enter", tid)
        if not rollback_ok:
            raise RuntimeError(
                f"kanban_request_changes raised and DevKit rollback review-enter also failed: {rollback_detail}"
            )
        raise

    if _devkit_result_is_error(result):
        return _devkit_rollback_after_result("review-enter", tid, result)
    return result
'''


def strict_compile(path: Path) -> None:
    with tempfile.TemporaryDirectory() as directory:
        py_compile.compile(str(path), cfile=str(Path(directory) / "x.pyc"), doraise=True)


def _top_level_function(source: str, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast.parse(source)
    matches = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one {name} handler, found {len(matches)}")
    return matches[0]


def _line_offsets(source: str) -> list[int]:
    offsets = [0]
    total = 0
    for line in source.splitlines(keepends=True):
        total += len(line)
        offsets.append(total)
    return offsets


def _function_start_line(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    decorator_lines = [decorator.lineno for decorator in node.decorator_list]
    return min([node.lineno, *decorator_lines])


def patch_source(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    if (
        PATCH_MARKER in source
        and REVIEW_WRAPPER_MARKER in source
        and CHANGES_WRAPPER_MARKER in source
    ):
        strict_compile(path)
        return "already-patched"

    review = _top_level_function(source, "_handle_request_review")
    changes = _top_level_function(source, "_handle_request_changes")
    if review.end_lineno is None or changes.end_lineno is None:
        raise RuntimeError(f"{path}: handler source boundaries unavailable")

    offsets = _line_offsets(source)
    insertions = [
        (offsets[_function_start_line(review) - 1], HELPERS + "\n"),
        (offsets[review.end_lineno], REVIEW_WRAPPER + "\n"),
        (offsets[changes.end_lineno], CHANGES_WRAPPER + "\n"),
    ]

    for offset, text in sorted(insertions, key=lambda item: item[0], reverse=True):
        source = source[:offset] + text + source[offset:]

    path.write_text(source, encoding="utf-8")
    strict_compile(path)
    return "patched"


def _fixture_legacy() -> str:
    """Hermes v2026.8.16.x style: plain handlers without _kanban_handler decorator."""
    return '''import json\nimport os\n\ndef tool_error(message): return json.dumps({"error": message})\ndef _is_dispatcher_owned_worker(): return True\n\ndef _handle_request_review(args: dict, **kw) -> str:\n    reviewer = args.get("reviewer")\n    return json.dumps({"ok": True, "status": "review", "reviewer": reviewer})\n\ndef _handle_request_changes(args: dict, **kw) -> str:\n    return json.dumps({"ok": True, "status": "ready"})\n\ndef _handle_heartbeat(args: dict, **kw) -> str:\n    return json.dumps({"ok": True})\n'''


def _fixture_current() -> str:
    """Current Hermes style: decorated handlers whose body may evolve upstream."""
    return '''import functools\nimport json\nimport os\n\ndef tool_error(message): return json.dumps({"error": message})\ndef _is_dispatcher_owned_worker(): return True\ndef _kanban_handler(name):\n    def deco(fn):\n        @functools.wraps(fn)\n        def wrapper(args: dict, **kw):\n            try: return fn(args, **kw)\n            except Exception as exc: return tool_error(f"{name}: {exc}")\n        return wrapper\n    return deco\n\n@_kanban_handler("kanban_request_review")\ndef _handle_request_review(args: dict, **kw) -> str:\n    reviewer = args.get("reviewer")\n    if reviewer == "missing-profile":\n        return tool_error("reviewer profile does not exist")\n    return json.dumps({"ok": True, "status": "review", "reviewer": reviewer})\n\n@_kanban_handler("kanban_request_changes")\ndef _handle_request_changes(args: dict, **kw) -> str:\n    return json.dumps({"ok": True, "status": "ready"})\n\ndef _handle_heartbeat(args: dict, **kw) -> str:\n    return json.dumps({"ok": True})\n'''


def _assert_fixture_patches(source: str) -> None:
    import json

    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory) / "kanban_tools.py"
        target.write_text(source, encoding="utf-8")
        assert patch_source(target) == "patched"
        assert patch_source(target) == "already-patched"
        patched = target.read_text(encoding="utf-8")
        for term in (
            PATCH_MARKER,
            POLICY_MARKER,
            REVIEW_WRAPPER_MARKER,
            CHANGES_WRAPPER_MARKER,
            '_devkit_run_flow_model_transition("review-enter", tid)',
            '_devkit_rollback_after_result("changes-return", tid, result)',
            '_devkit_run_flow_model_transition("changes-return", tid)',
            '_devkit_rollback_after_result("review-enter", tid, result)',
        ):
            assert term in patched, term

        # With no dispatcher task in env, wrappers preserve upstream behavior
        # without touching the Kanban DB or model policy helper.
        namespace: dict = {}
        exec(compile(patched, str(target), "exec"), namespace)
        review_result = namespace["_handle_request_review"]({"reviewer": "reviewer"})
        changes_result = namespace["_handle_request_changes"]({})
        assert json.loads(review_result)["ok"] is True
        assert json.loads(changes_result)["ok"] is True


def self_test() -> None:
    _assert_fixture_patches(_fixture_legacy())
    _assert_fixture_patches(_fixture_current())
    print("Hermes Kanban model transition patch self-test passed (legacy + current handler layouts)")


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
