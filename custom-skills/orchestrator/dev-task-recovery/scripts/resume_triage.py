#!/usr/bin/env python3
"""Resume an approved triage recovery using Hermes' official state transition."""
from __future__ import annotations
import argparse
import json
import os
import re
import sys

MARKER = re.compile(r'^TASK_RECOVERY_(?:REVISION|RETRY)_V[1-9][0-9]*$')


class RevisionGuardConnection:
    """Revalidate after the official API acquires its write lock, before writes."""
    def __init__(self, connection, validate):
        self.connection = connection
        self.validate = validate
        self.checked = False
    def __getattr__(self, name):
        return getattr(self.connection, name)
    def execute(self, sql, *args):
        if sql.strip().upper() == 'BEGIN IMMEDIATE' and not self.checked:
            result = self.connection.execute(sql, *args)
            try:
                self.validate()
                self.checked = True
            except Exception:
                self.connection.rollback()
                raise
            return result
        if sql.lstrip().upper().startswith(('UPDATE', 'INSERT', 'DELETE')) and not self.checked:
            raise RuntimeError('TRIAGE_RECOVERY_CAPABILITY_UNAVAILABLE')
        return self.connection.execute(sql, *args)


def resume(kb, conn, *, board, task_id, revision_marker):
    if os.environ.get('HERMES_KANBAN_TASK'):
        raise RuntimeError('ORCHESTRATOR_ONLY')
    if not callable(getattr(kb, 'specify_triage_task', None)):
        raise RuntimeError('TRIAGE_RECOVERY_CAPABILITY_UNAVAILABLE')
    if not MARKER.fullmatch(revision_marker):
        raise RuntimeError('RECOVERY_REVISION_NOT_PERSISTED')
    def validate():
        task = kb.get_task(conn, task_id)
        if task is None or task.status != 'triage' or any(
            getattr(task, key, None) for key in ('claim_lock', 'worker_pid', 'current_run_id')
        ):
            raise RuntimeError('STALE_RECOVERY_SELECTION')
        comments = kb.list_comments(conn, task_id)
        approved = [c for c in comments if 'Recovery Gate: APPROVED' in c.body
                    and re.search(r'^TASK_RECOVERY_(?:REVISION|RETRY|ESCALATION)_V[1-9][0-9]*$', c.body, re.M)]
        if not approved:
            raise RuntimeError('RECOVERY_REVISION_NOT_PERSISTED')
        latest = max(approved, key=lambda c: c.id)
        lines = latest.body.splitlines()
        required = {revision_marker, 'Recovery Gate: APPROVED', 'Source Status: triage',
                    f'Board: {board}', f'Task: {task_id}'}
        if not required.issubset(lines) or not any(
            f'Recovery Mode: {mode}' in lines for mode in ('SAME_TASK_RESUME', 'RETRY_SAME_CONTRACT')
        ):
            raise RuntimeError('STALE_RECOVERY_SELECTION')
    validate()
    guarded = RevisionGuardConnection(conn, validate)
    # Official compare-and-swap preserves fields, audits transition, and gates parents.
    if not kb.specify_triage_task(guarded, task_id):
        raise RuntimeError('STALE_RECOVERY_SELECTION')
    task = kb.get_task(conn, task_id)
    if task.status not in ('todo', 'ready', 'running'):
        raise RuntimeError('TRIAGE_RESUME_READBACK_FAILED')
    return {'task_id': task_id, 'board': board, 'status': task.status}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--board', required=True)
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--revision-marker', required=True)
    args = parser.parse_args()
    try:
        if os.environ.get('HERMES_KANBAN_TASK'):
            raise RuntimeError('ORCHESTRATOR_ONLY')
        if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', args.board):
            raise RuntimeError('INVALID_BOARD')
        from hermes_cli import kanban_db as kb
        from hermes_cli import kanban_db_connect as kbc
        if not kb.board_exists(args.board):
            raise RuntimeError('BOARD_INVENTORY_UNAVAILABLE')
        conn = kbc.connect(board=args.board)
        try:
            result = resume(kb, conn, board=args.board, task_id=args.task_id,
                            revision_marker=args.revision_marker)
        finally:
            conn.close()
        print(json.dumps(result))
        return 0
    except (ImportError, AttributeError):
        print(json.dumps({'blocker': 'TRIAGE_RECOVERY_CAPABILITY_UNAVAILABLE'}), file=sys.stderr)
        return 2
    except Exception as exc:
        print(json.dumps({'blocker': str(exc)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
