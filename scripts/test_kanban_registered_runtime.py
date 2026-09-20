#!/usr/bin/env python3
"""Runtime integration regression for Standard Flow registered notifications."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="devkit-kanban-notify-") as tmp:
        home = Path(tmp)
        os.environ["HERMES_HOME"] = str(home)

        from gateway.config import Platform
        from gateway.kanban_watchers_notifier import (
            TERMINAL_KINDS,
            _EVENT_FORMATTERS,
            _KanbanNotification,
            _notifier_collect,
        )
        from hermes_cli import kanban_db as kb
        from hermes_cli import kanban_db_connect as kbc
        from hermes_cli import kanban_db_notify as kbn

        assert "registered" in TERMINAL_KINDS, TERMINAL_KINDS
        assert "registered" in _EVENT_FORMATTERS, _EVENT_FORMATTERS.keys()

        board = "devkit-notify-integration"
        kb.create_board(board)
        conn = kbc.connect(board=board)
        try:
            task_id = kb.create_task(
                conn,
                title="registered notification integration",
                assignee="coder",
                created_by="orchestrator",
                initial_status="blocked",
                goal_mode=True,
                board=board,
            )
            kbn.add_notify_sub(
                conn,
                task_id=task_id,
                platform="discord",
                chat_id="integration-channel",
                chat_type="channel",
                notifier_profile="default",
                delivery_mode="notify",
            )
            before = kbn.list_notify_subs(conn, task_id)[0]
            initial_cursor = int(before.get("last_event_id") or 0)
            payload = json.dumps({"source": "devkit-integration", "status": "blocked"})
            with kb.write_txn(conn):
                cur = conn.execute(
                    "INSERT INTO task_events (task_id, run_id, kind, payload, created_at) "
                    "VALUES (?, NULL, 'registered', ?, ?)",
                    (task_id, payload, int(time.time())),
                )
                event_id = int(cur.lastrowid)
            assert event_id > initial_cursor, (initial_cursor, event_id)
        finally:
            conn.close()

        sent: list[tuple[str, str]] = []

        class Adapter:
            async def send(self, chat_id, msg, metadata=None):
                sent.append((str(chat_id), str(msg)))
                return SimpleNamespace(success=True)

        adapter = Adapter()

        class Runner:
            def __init__(self):
                self.adapters = {Platform.DISCORD: adapter}
                self._profile_adapters = {}
                self._kanban_notifier_profile = "default"
                self.config = SimpleNamespace(multiplex_profiles=False, profile_routes=[])

            def _owns_kanban_dispatcher_lock(self):
                return True

            def _active_profile_name(self):
                return "default"

            def _authorization_adapter(self, platform, owner_profile):
                return self.adapters.get(platform)

            def _kanban_sub_op(self, board_slug, op, sub, **extra):
                c = kbc.connect(board=board_slug)
                try:
                    getattr(kbn, op)(
                        c,
                        task_id=sub["task_id"],
                        platform=sub["platform"],
                        chat_id=sub["chat_id"],
                        thread_id=sub.get("thread_id") or "",
                        **extra,
                    )
                finally:
                    c.close()

            def _kanban_advance(self, sub, cursor, board_slug=None):
                self._kanban_sub_op(board_slug, "advance_notify_cursor", sub, new_cursor=cursor)

            def _kanban_rewind(self, sub, claimed_cursor, old_cursor, board_slug=None):
                self._kanban_sub_op(
                    board_slug,
                    "rewind_notify_cursor",
                    sub,
                    claimed_cursor=claimed_cursor,
                    old_cursor=old_cursor,
                )

            def _kanban_unsub(self, sub, board_slug=None):
                self._kanban_sub_op(board_slug, "remove_notify_sub", sub)

            async def _deliver_kanban_artifacts(self, **kwargs):
                return None

        runner = Runner()
        deliveries = _notifier_collect(
            runner,
            kb,
            notifier_profile="default",
            gc_due=False,
            gc_retention_days=30,
        )
        matching = [d for d in deliveries if d["sub"]["task_id"] == task_id]
        assert len(matching) == 1, {
            "task_id": task_id,
            "event_id": event_id,
            "deliveries": [(d["sub"]["task_id"], [e.kind for e in d["events"]]) for d in deliveries],
        }
        delivery = matching[0]
        assert [e.id for e in delivery["events"]] == [event_id], [e.id for e in delivery["events"]]

        await _KanbanNotification(
            runner,
            delivery,
            platform_cls=Platform,
            sub_fail_counts={},
        ).deliver()

        conn = kbc.connect(board=board)
        try:
            after = kbn.list_notify_subs(conn, task_id)[0]
        finally:
            conn.close()

        assert len(sent) == 1, sent
        assert "작업 등록" in sent[0][1], sent[0][1]
        assert int(after.get("last_event_id") or 0) == event_id, after
        assert int(after.get("last_ping_event_id") or 0) == event_id, after
        print(
            "Kanban registered notification runtime integration passed "
            f"task={task_id} event={event_id} cursor={after.get('last_event_id')} "
            f"ping={after.get('last_ping_event_id')}"
        )


if __name__ == "__main__":
    asyncio.run(main())
