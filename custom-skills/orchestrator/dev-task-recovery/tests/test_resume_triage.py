import importlib.util
from pathlib import Path
from types import SimpleNamespace as S
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('resume', Path(__file__).resolve().parents[1] / 'scripts/resume_triage.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.task = S(status='triage', claim_lock=None, worker_pid=None, current_run_id=None)
        self.comments = [S(id=1, body='TASK_RECOVERY_REVISION_V1\nRecovery Gate: APPROVED\nRecovery Mode: SAME_TASK_RESUME\nSource Status: triage\nBoard: test\nTask: t_1')]
        self.calls = []
        def transition(conn, tid):
            conn.execute("BEGIN IMMEDIATE")
            self.calls.append(tid)
            self.task.status = 'todo'
            conn.execute('BEGIN IMMEDIATE')  # official recompute_ready transaction
            return True
        self.kb = S(get_task=lambda *a: self.task, list_comments=lambda *a: self.comments, specify_triage_task=transition)
    def run_resume(self):
        return m.resume(self.kb, S(execute=lambda *a: None, rollback=lambda: None), board='test', task_id='t_1', revision_marker='TASK_RECOVERY_REVISION_V1')
    def test_approved_transition_once(self):
        with patch.dict('os.environ', {}, clear=True):
            self.assertEqual(self.run_resume()['status'], 'todo')
            self.assertEqual(self.calls, ['t_1'])
    def test_stale_and_claimed_refused(self):
        for field, value in [('status','blocked'), ('claim_lock','owner'), ('worker_pid',42), ('current_run_id',3)]:
            with self.subTest(field=field), patch.dict('os.environ', {}, clear=True):
                old = getattr(self.task, field); setattr(self.task, field, value)
                with self.assertRaisesRegex(RuntimeError, 'STALE'): self.run_resume()
                setattr(self.task, field, old)
        self.assertEqual(self.calls, [])
    def test_newer_escalation_or_revision_refused(self):
        for marker in ('TASK_RECOVERY_ESCALATION_V2','TASK_RECOVERY_REVISION_V2'):
            self.comments.append(S(id=2, body=marker+'\nRecovery Gate: APPROVED'))
            with patch.dict('os.environ', {}, clear=True), self.assertRaisesRegex(RuntimeError, 'STALE'): self.run_resume()
            self.comments.pop()
        self.assertEqual(self.calls, [])
    def test_missing_approval_or_wrong_board_refused(self):
        for body in ('', self.comments[0].body.replace('Board: test','Board: other')):
            self.comments[0].body = body
            with patch.dict('os.environ', {}, clear=True), self.assertRaises(RuntimeError): self.run_resume()
        self.assertEqual(self.calls, [])
    def test_revision_changes_after_initial_read(self):
        original = self.kb.specify_triage_task
        def racing(conn, tid):
            self.comments.append(S(id=2, body='TASK_RECOVERY_ESCALATION_V2\nRecovery Gate: APPROVED'))
            return original(conn, tid)
        self.kb.specify_triage_task = racing
        with patch.dict('os.environ', {}, clear=True), self.assertRaisesRegex(RuntimeError, 'STALE'):
            self.run_resume()
        self.assertEqual(self.calls, [])
        self.assertEqual(self.task.status, 'triage')

    def test_worker_and_missing_api_refused(self):
        with patch.dict('os.environ', {'HERMES_KANBAN_TASK':'t_1'}, clear=True), self.assertRaisesRegex(RuntimeError,'ORCHESTRATOR'): self.run_resume()
        del self.kb.specify_triage_task
        with patch.dict('os.environ', {}, clear=True), self.assertRaisesRegex(RuntimeError,'CAPABILITY'): self.run_resume()
        self.assertEqual(self.calls, [])

if __name__ == '__main__': unittest.main()
