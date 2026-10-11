#!/usr/bin/env python3
"""Regression cases for the actual beforeunload failure and clean CDP dismiss."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from browser_dialog_trace import analyze

def trace(result=True, sent=None, closed_time=2.0):
    return {"provider": "browser_exec", "events": [
        {"method": "Page.javascriptDialogOpening", "sessionId": "S",
         "params": {"type": "beforeunload"}, "time": 1.0},
        {"method": "Page.javascriptDialogClosed", "sessionId": "S",
         "params": {"result": result}, "time": closed_time}],
        "dismiss": {"sent_at": sent, "success": sent is not None} if sent is not None else None,
        "page_preserved": result is False, "input_preserved": result is False}

class TestDialogTrace(unittest.TestCase):
    def test_run91_auto_closed(self):
        result = analyze(trace())
        self.assertEqual(result["classification"], "CLOSED_WITHOUT_RECORDED_RESPONSE")
        self.assertEqual(result["next_action"], "STOP_RETRY_ESCALATE")
    def test_too_late(self):
        result = analyze(trace(sent=3.0))
        self.assertEqual(result["classification"], "CLOSED_BEFORE_RESPONSE")
    def test_e_probe(self):
        result = analyze(trace(False, sent=1.5))
        self.assertEqual(result["execution_status"], "PASS")
    def test_no_false_pass_without_preservation(self):
        sample = trace(False, sent=1.5)
        sample["input_preserved"] = False
        self.assertEqual(analyze(sample)["execution_status"], "INCONCLUSIVE")
    def test_requires_beforeunload(self):
        self.assertEqual(analyze({"events": []})["execution_status"], "INCONCLUSIVE")
    def test_stable_fingerprint(self):
        self.assertEqual(analyze(trace())["recovery_fingerprint"], analyze(trace())["recovery_fingerprint"])
    def test_session_mismatch_does_not_assume_closed(self):
        sample = trace()
        sample["events"][1]["sessionId"] = "other"
        self.assertEqual(analyze(sample)["classification"], "DIALOG_RESPONSE_UNCONFIRMED")
    def test_invalid_input(self):
        with self.assertRaises(ValueError):
            analyze({"events": "wrong"})
if __name__ == "__main__":
    unittest.main(verbosity=2)
