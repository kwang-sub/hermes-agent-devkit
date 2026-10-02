#!/usr/bin/env python3
"""Regression tests for bounded session capture and comment delivery receipts."""
from __future__ import annotations

import contextlib
from concurrent.futures import ThreadPoolExecutor
import io
from pathlib import Path
import sqlite3
import shutil
import tempfile
import unittest
from unittest.mock import patch

import task_session_history as history


class SessionHistoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.profile = self.root / "coder"
        self.profile.mkdir()
        self.db = self.root / "history.db"
        self.context = dict(task_id="t_demo", profile="coder", profile_home=str(self.profile),
                            workspace="/workspace/demo", history_db=str(self.db), session_mode="NEW")
        self.create_state()

    def create_state(self, profile: Path | None = None) -> None:
        home = profile or self.profile
        home.mkdir(exist_ok=True)
        with sqlite3.connect(str(home / "state.db")) as conn:
            conn.execute("CREATE TABLE sessions(id TEXT PRIMARY KEY, source TEXT, cwd TEXT, started_at REAL)")
            conn.execute("CREATE TABLE messages(id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT)")

    def add_session(self, session_id="s1", *, task_id="t_demo", workspace="/workspace/demo",
                    source="kanban", role="user", started_at=1, profile=None, message=True) -> None:
        with sqlite3.connect(str((profile or self.profile) / "state.db")) as conn:
            conn.execute("INSERT INTO sessions VALUES (?, ?, ?, ?)", (session_id, source, workspace, started_at))
            if message:
                conn.execute("INSERT INTO messages(session_id, role, content) VALUES (?, ?, ?)",
                             (session_id, role, f"work kanban task {task_id}"))

    def run_capture(self, **options):
        return history.capture_with_retry(**{**self.context, **options})

    def ack(self, session_id="s1", profile="coder") -> None:
        history.acknowledge_comment(task_id="t_demo", profile=profile, session_id=session_id, history_db=str(self.db))

    def cli(self, command="capture", *extras):
        args = [command, "--task-id", "t_demo", "--history-db", str(self.db)]
        if command == "capture":
            args += ["--profile", "coder", "--profile-home", str(self.profile),
                     "--workspace", "/workspace/demo", "--retry-delay", "0"]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = history.main(args + list(extras))
        return result, output.getvalue()

    def test_success_returns_immediately(self):
        self.add_session()
        with patch.object(history.time, "sleep") as sleep:
            result = self.run_capture()
        self.assertEqual((result.status, result.attempts, result.session_id), ("captured", 1, "s1"))
        self.assertTrue(result.is_new)
        self.assertTrue(result.comment_pending)
        sleep.assert_not_called()

    def test_missing_state_is_bounded_and_does_not_create_databases(self):
        (self.profile / "state.db").unlink()
        with patch.object(history.time, "sleep") as sleep:
            result = self.run_capture()
        self.assertEqual((result.status, result.reason, result.attempts), ("unavailable", "STATE_DB_MISSING", 3))
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual([call.args for call in sleep.call_args_list], [(0.5,), (0.5,)])
        self.assertFalse(self.db.exists())
        self.assertFalse((self.profile / "state.db").exists())

    def test_missing_match_never_records_unavailable_as_an_id(self):
        result = self.run_capture(retry_delay=0)
        self.assertEqual(result.reason, "SESSION_MATCH_NOT_FOUND")
        self.assertIsNone(result.session_id)
        self.assertFalse(self.db.exists())

    def test_exact_task_workspace_source_and_user_message_are_required(self):
        self.add_session("wrong-task", task_id="t_other")
        self.add_session("wrong-workspace", workspace="/workspace/other")
        self.add_session("wrong-source", source="cli")
        self.add_session("wrong-role", role="assistant")
        self.assertEqual(self.run_capture(retry_delay=0).status, "unavailable")
        self.assertFalse(self.db.exists())

    def test_prompt_substring_is_not_a_match(self):
        self.add_session(task_id="t_demo_extra")
        self.assertEqual(self.run_capture(retry_delay=0).status, "unavailable")

    def test_session_appearing_during_retry_is_captured(self):
        with patch.object(history.time, "sleep", side_effect=lambda _: self.add_session()) as sleep:
            result = self.run_capture()
        self.assertEqual((result.status, result.attempts, result.session_id), ("captured", 2, "s1"))
        sleep.assert_called_once_with(0.5)

    def test_message_committed_later_is_captured(self):
        self.add_session(message=False)
        def commit_message(_):
            with sqlite3.connect(str(self.profile / "state.db")) as conn:
                conn.execute("INSERT INTO messages VALUES (1, 's1', 'user', 'work kanban task t_demo')")
        with patch.object(history.time, "sleep", side_effect=commit_message):
            result = self.run_capture()
        self.assertEqual((result.status, result.attempts), ("captured", 2))

    def test_finalize_is_one_attempt_without_sleep(self):
        with patch.object(history.time, "sleep") as sleep:
            result = self.run_capture(phase="finalize")
        self.assertEqual((result.status, result.attempts), ("unavailable", 1))
        sleep.assert_not_called()

    def test_finalize_recovers_missing_metadata_on_same_task(self):
        self.assertEqual(self.run_capture(retry_delay=0).status, "unavailable")
        self.add_session("late-coder")
        result = self.run_capture(phase="finalize")
        self.assertEqual((result.status, result.session_id), ("captured", "late-coder"))
        self.ack("late-coder")
        rows = history.list_history(task_id="t_demo", history_db=str(self.db))
        self.assertEqual([(row["task_id"], row["profile"], row["session_id"]) for row in rows],
                         [("t_demo", "coder", "late-coder")])

    def test_db_duplicate_remains_pending_until_comment_ack(self):
        self.add_session()
        self.run_capture()
        again = self.run_capture()
        self.assertFalse(again.is_new)
        self.assertTrue(again.comment_pending)
        self.ack()
        resolved = self.run_capture(phase="finalize")
        self.assertFalse(resolved.comment_pending)
        self.assertFalse(resolved.is_new)

    def test_ack_is_idempotent(self):
        self.add_session()
        self.run_capture()
        self.ack()
        self.ack()
        with sqlite3.connect(str(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM task_session_history_comments").fetchone()[0], 1)

    def test_unverified_and_placeholder_ids_cannot_be_acknowledged(self):
        for session_id in ("not-captured", "UNAVAILABLE", "bad\nid"):
            with self.subTest(session_id=session_id), self.assertRaises(ValueError):
                self.ack(session_id)
        with sqlite3.connect(str(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM task_session_history_comments").fetchone()[0], 0)

    def test_legacy_db_row_does_not_imply_comment_delivered(self):
        self.add_session()
        with sqlite3.connect(str(self.db)) as conn:
            conn.execute("CREATE TABLE task_session_history(task_id TEXT, profile TEXT, session_id TEXT, session_mode TEXT, workspace TEXT, first_seen_at REAL, last_seen_at REAL, PRIMARY KEY(task_id, profile, session_id))")
            conn.execute("INSERT INTO task_session_history VALUES ('t_demo','coder','s1','NEW','/workspace/demo',123,123)")
        result = self.run_capture()
        self.assertFalse(result.is_new)
        self.assertTrue(result.comment_pending)
        self.ack()
        rows = history.list_history(task_id="t_demo", history_db=str(self.db))
        self.assertEqual(rows[0]["first_seen_at"], 123)

    def test_unknown_recapture_does_not_erase_known_mode(self):
        self.add_session()
        self.run_capture(session_mode="RESUME")
        self.run_capture(session_mode="UNKNOWN")
        rows = history.list_history(task_id="t_demo", history_db=str(self.db))
        self.assertEqual(rows[0]["session_mode"], "RESUME")

    def test_multiple_sessions_are_append_only(self):
        self.add_session()
        self.run_capture()
        self.add_session("s2", started_at=2)
        self.run_capture()
        rows = history.list_history(task_id="t_demo", history_db=str(self.db))
        self.assertEqual({row["session_id"] for row in rows}, {"s1", "s2"})

    def test_known_session_id_is_pinned_during_comment_repair(self):
        self.add_session()
        self.run_capture()
        self.add_session("newer", started_at=2)
        result = self.run_capture(phase="finalize", session_id="s1")
        self.assertEqual(result.session_id, "s1")

    def test_missing_pinned_session_does_not_fall_back_to_older_id(self):
        self.add_session("old-session")
        result = self.run_capture(phase="finalize", session_id="current-missing")
        self.assertEqual(result.status, "unavailable")
        self.assertFalse(self.db.exists())

    def test_reviewer_cannot_use_coder_profile_history(self):
        self.add_session()
        self.run_capture()
        reviewer = self.root / "reviewer"
        self.create_state(reviewer)
        result = self.run_capture(profile="reviewer", profile_home=str(reviewer), phase="finalize")
        self.assertEqual(result.status, "unavailable")
        self.add_session("review-session", profile=reviewer)
        result = self.run_capture(profile="reviewer", profile_home=str(reviewer))
        self.assertEqual(result.session_id, "review-session")
        rows = history.list_history(task_id="t_demo", history_db=str(self.db))
        self.assertEqual({(row["profile"], row["session_id"]) for row in rows},
                         {("coder", "s1"), ("reviewer", "review-session")})

    def test_schema_error_is_not_missing_session_and_not_retried(self):
        with sqlite3.connect(str(self.profile / "state.db")) as conn:
            conn.execute("DROP TABLE messages")
        with patch.object(history.time, "sleep") as sleep:
            result = self.run_capture()
        self.assertEqual((result.status, result.reason, result.attempts), ("error", "STATE_DB_ERROR", 1))
        sleep.assert_not_called()
        self.assertFalse(self.db.exists())

    def test_corrupt_state_is_error(self):
        (self.profile / "state.db").write_bytes(b"not a SQLite database")
        result = self.run_capture()
        self.assertEqual((result.status, result.error_type), ("error", "DatabaseError"))

    def test_state_lock_is_error_not_unavailable(self):
        conn = sqlite3.connect(str(self.profile / "state.db"))
        try:
            conn.execute("BEGIN EXCLUSIVE")
            result = self.run_capture()
            self.assertEqual((result.status, result.reason), ("error", "STATE_DB_ERROR"))
        finally:
            conn.close()

    def test_state_directory_is_error_not_missing_metadata(self):
        (self.profile / "state.db").unlink()
        (self.profile / "state.db").mkdir()
        result = self.run_capture()
        self.assertEqual((result.status, result.reason), ("error", "STATE_DB_ERROR"))

    def test_history_write_error_is_reported(self):
        self.add_session()
        self.db.mkdir()
        result = self.run_capture()
        self.assertEqual((result.status, result.reason), ("error", "HISTORY_DB_ERROR"))

    def test_history_workspace_conflict_does_not_overwrite_existing_row(self):
        self.add_session()
        self.run_capture()
        with sqlite3.connect(str(self.profile / "state.db")) as conn:
            conn.execute("UPDATE sessions SET cwd='/workspace/other'")
        result = self.run_capture(workspace="/workspace/other")
        self.assertEqual(result.status, "invalid")
        self.assertEqual(history.list_history(task_id="t_demo", history_db=str(self.db))[0]["workspace"], "/workspace/demo")

    def test_history_db_cannot_be_hermes_state_db(self):
        result = self.run_capture(history_db=str(self.profile / "state.db"))
        self.assertEqual(result.status, "invalid")
        with sqlite3.connect(str(self.profile / "state.db")) as conn:
            tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        self.assertNotIn("task_session_history", tables)

    def test_invalid_context_is_not_retried(self):
        cases = [dict(task_id=""), dict(task_id="UNAVAILABLE"), dict(profile="other"),
                 dict(workspace="relative"), dict(profile_home=""), dict(session_id="UNAVAILABLE"),
                 dict(session_mode="BAD"), dict(history_db="relative.db")]
        for case in cases:
            with self.subTest(case=case), patch.object(history.time, "sleep") as sleep:
                self.assertEqual(self.run_capture(**case).status, "invalid")
                sleep.assert_not_called()

    def test_unbounded_and_non_finite_retry_settings_are_rejected(self):
        cases = [dict(attempts=0), dict(attempts=4), dict(retry_delay=-1), dict(retry_delay=2),
                 dict(retry_delay=float("nan")), dict(retry_delay=float("inf")), dict(phase="other")]
        for case in cases:
            with self.subTest(case=case):
                self.assertEqual(self.run_capture(**case).status, "invalid")

    def test_cli_unavailable_is_exit_zero_with_warning_action(self):
        code, output = self.cli()
        self.assertEqual(code, 0)
        self.assertIn("SESSION_HISTORY_STATUS=unavailable", output)
        self.assertIn("SESSION_HISTORY_ACTION=CONTINUE_WITH_WARNING", output)
        self.assertIn("SESSION_HISTORY_RECHECK_REQUIRED=true", output)
        self.assertNotIn("SESSION_HISTORY_MARKER_BEGIN", output)

    def test_cli_real_error_is_nonzero_and_has_sanitized_diagnostics(self):
        with patch.object(history, "_find_latest_session", side_effect=PermissionError("SECRET_RAW_CONTENT")):
            code, output = self.cli()
        self.assertEqual(code, 3)
        self.assertIn("SESSION_HISTORY_STATUS=error", output)
        self.assertIn("SESSION_HISTORY_ERROR_TYPE=PermissionError", output)
        self.assertNotIn("SECRET_RAW_CONTENT", output)

    def test_cli_invalid_is_exit_two(self):
        code, output = self.cli("capture", "--attempts", "100")
        self.assertEqual(code, 2)
        self.assertIn("SESSION_HISTORY_STATUS=invalid", output)

    def test_cli_capture_ack_and_list(self):
        self.add_session()
        code, output = self.cli()
        self.assertEqual(code, 0)
        self.assertIn("SESSION_HISTORY_COMMENT_PENDING=true", output)
        self.assertIn("TASK_SESSION_HISTORY\n- Session ID: s1\n- Profile: coder", output)
        code, output = self.cli("ack-comment", "--profile", "coder", "--session-id", "s1")
        self.assertEqual(code, 0)
        self.assertIn("SESSION_HISTORY_RECHECK_REQUIRED=false", output)
        code, output = self.cli()
        self.assertIn("SESSION_HISTORY_COMMENT_PENDING=false", output)
        self.assertIn("SESSION_HISTORY_NEW=false", output)
        code, output = self.cli("list")
        self.assertEqual(code, 0)
        self.assertIn("id=s1", output)

    def test_concurrent_captures_create_one_db_row(self):
        self.add_session()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.run_capture(), range(4)))
        self.assertEqual({result.status for result in results}, {"captured"})
        self.assertEqual(sum(result.is_new for result in results), 1)
        self.assertEqual(len(history.list_history(task_id="t_demo", history_db=str(self.db))), 1)

    def test_sqlite_uri_escapes_special_profile_path(self):
        profile = self.root / "profile?readonly#name"
        self.create_state(profile)
        self.add_session(profile=profile)
        self.assertEqual(self.run_capture(profile_home=str(profile)).status, "captured")


class WorkerContractTest(unittest.TestCase):
    def test_current_shared_worker_contracts(self):
        from check_session_history_contract import ROOT, check_workers
        check_workers(ROOT)

    def test_old_unavailable_hard_block_is_rejected(self):
        from check_session_history_contract import ROOT, REFERENCE, CODER, REVIEWER, CYCLE, check_workers
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in (REFERENCE, CODER, REVIEWER, CYCLE.format(role="coder"), CYCLE.format(role="reviewer")):
                (root / path).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / path, root / path)
            with (root / CODER).open("a") as file:
                file.write("\nSession ID를 추측하지 않고 mutation 전에 capability blocker로 종료한다\n")
            with self.assertRaises(AssertionError):
                check_workers(root)

    def test_missing_reviewer_finalization_is_rejected(self):
        from check_session_history_contract import ROOT, REFERENCE, CODER, REVIEWER, CYCLE, FINALIZE, check_workers
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in (REFERENCE, CODER, REVIEWER, CYCLE.format(role="coder"), CYCLE.format(role="reviewer")):
                (root / path).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / path, root / path)
            path = root / REVIEWER
            path.write_text(path.read_text().replace(FINALIZE, "REMOVED"))
            with self.assertRaises(AssertionError):
                check_workers(root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
