#!/usr/bin/env python3
"""Install a minimal Kanban body-normalization guard at the real write edges.

Core create/edit and dashboard PATCH are covered; task_links, task state and
other fields are never changed. Fail fast if upstream signatures drift.
"""
from __future__ import annotations

import argparse
import ast
from pathlib import Path

CORE_CREATE_MARKER = "DEVKIT_PARENT_TRACKING_CREATE_V1"
CORE_EDIT_MARKER = "DEVKIT_PARENT_TRACKING_EDIT_V1"
DASHBOARD_MARKER = "DEVKIT_PARENT_TRACKING_DASHBOARD_V1"

CREATE_ANCHOR = "    completion_contract = validate_contract(completion_contract)"
CREATE_REPLACEMENT = (
    "    # " + CORE_CREATE_MARKER + ": ensure dashboard-readable tracking lines.\n"
    "    from hermes_cli.devkit_parent_tracking import normalize_parent_body\n"
    "    body = normalize_parent_body(body, title=title)\n"
    + CREATE_ANCHOR
)

EDIT_ANCHOR = '    """Edit task fields, optionally backfilling a completed task\'s result."""\n'
EDIT_REPLACEMENT = (
    EDIT_ANCHOR
    + "    # " + CORE_EDIT_MARKER + ": preserve text while repairing legacy inline tracking.\n"
    + "    if body is not None:\n"
    + "        from hermes_cli.devkit_parent_tracking import normalize_parent_body\n"
    + "        current_title = title\n"
    + "        if current_title is None:\n"
    + '            saved = conn.execute("SELECT title FROM tasks WHERE id = ?", (task_id,)).fetchone()\n'
    + '            current_title = saved[0] if saved else ""\n'
    + '        body = normalize_parent_body(body, title=current_title or "")\n'
)

DASHBOARD_ANCHOR = '''        if payload.body is not None:
            sets.append("body = ?")
            vals.append(payload.body)
'''
DASHBOARD_REPLACEMENT = '''        if payload.body is not None:
            # ''' + DASHBOARD_MARKER + ''': same contract as CLI and kanban_create.
            from hermes_cli.devkit_parent_tracking import normalize_parent_body
            saved = conn.execute("SELECT title FROM tasks WHERE id = ?", (task_id,)).fetchone()
            current_title = payload.title or (saved[0] if saved else "")
            try:
                normalized_body = normalize_parent_body(payload.body, title=current_title)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            sets.append("body = ?")
            vals.append(normalized_body)
'''


def replace_once(text: str, anchor: str, replacement: str, label: str) -> str:
    count = text.count(anchor)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one supported anchor, got {count}")
    return text.replace(anchor, replacement, 1)


def patch_core(text: str) -> str:
    if CORE_CREATE_MARKER not in text:
        text = replace_once(text, CREATE_ANCHOR, CREATE_REPLACEMENT, "Kanban create_task")
    if CORE_EDIT_MARKER not in text:
        text = replace_once(text, EDIT_ANCHOR, EDIT_REPLACEMENT, "Kanban edit_task")
    return text


def patch_dashboard(text: str) -> str:
    if DASHBOARD_MARKER not in text:
        text = replace_once(text, DASHBOARD_ANCHOR, DASHBOARD_REPLACEMENT, "Dashboard PATCH body")
    return text


def _apply(path: Path, change) -> None:
    original = path.read_text(encoding="utf-8")
    modified = change(original)
    ast.parse(modified, filename=str(path))
    if modified != original:
        path.write_text(modified, encoding="utf-8")


def check(core: Path, dashboard: Path) -> None:
    for marker in (CORE_CREATE_MARKER, CORE_EDIT_MARKER):
        if marker not in core.read_text(encoding="utf-8"):
            raise RuntimeError("Kanban core body guard missing: " + marker)
    if DASHBOARD_MARKER not in dashboard.read_text(encoding="utf-8"):
        raise RuntimeError("Dashboard body guard missing")


def self_test() -> None:
    source = (
        "def create_task(conn, title, body, completion_contract):\n"
        "    from hermes_cli.kanban_pr_acceptance import validate_contract\n"
        + CREATE_ANCHOR + "\n    return body\n\n"
        + "def edit_task(conn, task_id, *, title=None, body=None):\n"
        + EDIT_ANCHOR
        + "    changed_fields = []\n    return changed_fields\n"
    )
    patched = patch_core(source)
    assert patch_core(patched) == patched
    ast.parse(patched)
    assert CORE_CREATE_MARKER in patched and CORE_EDIT_MARKER in patched

    fake_dashboard = (
        "def _patch_title_body(conn, task_id, payload):\n"
        "    with fake_context():\n"
        "        sets, vals = [], []\n"
        + DASHBOARD_ANCHOR + "        return sets, vals\n"
    )
    patched_dashboard = patch_dashboard(fake_dashboard)
    assert patch_dashboard(patched_dashboard) == patched_dashboard
    ast.parse(patched_dashboard)
    assert DASHBOARD_MARKER in patched_dashboard
    assert 'UPDATE tasks SET' not in DASHBOARD_REPLACEMENT
    try:
        patch_core("def incompatible(): pass\n")
    except RuntimeError:
        pass
    else:
        raise AssertionError("upstream mismatch must fail closed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hermes-root", default="/opt/hermes")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        print("parent tracking write guard self-test passed")
        return 0
    root = Path(args.hermes_root)
    core = root / "hermes_cli/kanban_db.py"
    dashboard = root / "plugins/kanban/dashboard/plugin_api.py"
    if not core.is_file() or not dashboard.is_file():
        raise SystemExit("required Hermes Kanban modules not found")
    if not args.check_only:
        _apply(core, patch_core)
        _apply(dashboard, patch_dashboard)
    check(core, dashboard)
    print("parent tracking write guard verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
