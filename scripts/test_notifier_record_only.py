#!/usr/bin/env python3
"""Completion events must never delete user scratch/handoff/worktree or mutate a board."""
from pathlib import Path
import hashlib
import sqlite3
import tempfile
import unittest
import devkit_kanban_notifier as notifier

class RecordOnlyTest(unittest.TestCase):
    def test_done_event_only_advances_private_delivery_cursor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);workspace=root/'workspace';workspace.mkdir()
            sentinel=workspace/'user-data.txt';sentinel.write_text('keep')
            board=root/'kanban.db'
            with sqlite3.connect(board) as conn:
                conn.executescript('''CREATE TABLE tasks(id TEXT PRIMARY KEY,title TEXT,assignee TEXT,status TEXT,workspace_path TEXT,result TEXT,model_override TEXT,provider_override TEXT,created_by TEXT);
                CREATE TABLE task_events(id INTEGER PRIMARY KEY AUTOINCREMENT,task_id TEXT,run_id INTEGER,kind TEXT,payload TEXT,created_at INTEGER);
                CREATE TABLE task_runs(id INTEGER PRIMARY KEY,profile TEXT);''')
                conn.execute('INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?)',('t_1','fixture','default','done',str(workspace),None,None,None,'default'))
            state=notifier.open_state(root/'private-state.db')
            try:
                notifier.initialize_state(state,[('test',board)])
                with sqlite3.connect(board) as conn:
                    conn.execute("INSERT INTO task_events(task_id,kind,payload,created_at) VALUES ('t_1','completed','{}',1)")
                before=hashlib.sha256(board.read_bytes()).hexdigest()
                count,ok,error=notifier.process_board(state,'test',board,platform='discord',target='',hermes_cli='unavailable',deliver_enabled=False)
                self.assertTrue(ok,error);self.assertEqual(count,1)
                self.assertEqual(sentinel.read_text(),'keep')
                self.assertEqual(hashlib.sha256(board.read_bytes()).hexdigest(),before)
                self.assertEqual(notifier.cursor_for_board(state,'test',board),1)
            finally:state.close()
if __name__=='__main__':unittest.main()
