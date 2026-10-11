#!/usr/bin/env python3
"""Runtime adapter regression: real fixture process, fake isolated probe."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parent))
from browser_runtime_adapter import _argv, run

PROBE = """
import json,sys
from pathlib import Path
result=bool(int(sys.argv[2]))
data={'provider':'browser_exec',
'events':[
{'method':'Page.javascriptDialogOpening','sessionId':'A','params':{'type':'beforeunload'},'time':1.0},
{'method':'Page.javascriptDialogClosed','sessionId':'A','params':{'result':not result},'time':2.0}],
'dismiss':({'sent_at':1.5,'success':True} if result else None),
'page_preserved':result,'input_preserved':result}
Path(sys.argv[1]).write_text(json.dumps(data),encoding='utf-8')
"""

def server():
    return [sys.executable, "-m", "http.server", "{port}", "--bind", "127.0.0.1"]

def probe(pass_case=True):
    return [sys.executable, "-c", PROBE, "{result_file}", "1" if pass_case else "0"]

class BrowserAdapterTests(unittest.TestCase):
    def test_probe_pass_and_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            report = run(server(), probe(), Path(temp), "t_sample", "browser_exec", 8, 8)
            self.assertEqual(report["execution_status"], "PASS", report)
            self.assertEqual(report["cleanup"]["status"], "PASS")
            self.assertTrue((Path(temp) / "browser-runtime-report.json").exists())
            self.assertEqual(report["classification"], "DISMISS_AND_PRESERVATION_CONFIRMED")

    def test_closed_before_response_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            report = run(server(), probe(False), Path(temp), "t_sample", "browser_exec", 8, 8)
            self.assertEqual(report["execution_status"], "BLOCKED_ENV", report)
            self.assertEqual(report["next_action"], "STOP_RETRY_ESCALATE")

    def test_missing_evidence_is_not_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            report = run(server(), [sys.executable, "-c", "pass"], Path(temp), "t_sample", "browser_exec", 8, 8)
            self.assertEqual(report["classification"], "PROBE_EVIDENCE_MISSING")
            self.assertEqual(report["cleanup"]["status"], "PASS")

    def test_stale_pass_evidence_is_never_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "browser-dialog-raw.json"
            file.write_text(json.dumps({"provider":"browser_exec","events":[]}),encoding="utf-8")
            report = run(server(), [sys.executable, "-c", "pass"], Path(temp), "t_sample", "browser_exec", 8, 8)
            self.assertEqual(report["classification"], "PROBE_EVIDENCE_MISSING")
            self.assertFalse(file.exists())

    def test_server_failure_records_report(self):
        with tempfile.TemporaryDirectory() as temp:
            report = run([sys.executable, "-c", "raise RuntimeError('stop')"], probe(),
                         Path(temp), "t_sample", "browser_exec", 3, 5)
            self.assertEqual(report["classification"], "SERVER_NOT_READY")
            self.assertTrue((Path(temp) / "browser-runtime-report.json").exists())

    def test_probe_timeout_stops_own_server(self):
        with tempfile.TemporaryDirectory() as temp:
            report = run(server(), [sys.executable,"-c","import time;time.sleep(9)"],
                         Path(temp), "t_sample", "browser_exec", 8, .2)
            self.assertEqual(report["classification"], "PROBE_TIMEOUT")
            self.assertEqual(report["cleanup"]["status"], "PASS")

    def test_reject_shell_strings(self):
        with self.assertRaises(ValueError):
            _argv("python -m http.server", "server-command")
        with self.assertRaises(ValueError):
            _argv('["python", null]', "server-command")

if __name__ == "__main__":
    unittest.main(verbosity=2)
