#!/usr/bin/env python3
"""Browser verification contract regression tests: no browser dependencies."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from browser_verification_evidence import validate

def fixture():
    return {
        "schema": "browser_verification_v1",
        "task_id": "t_sample", "provider": "browser_exec",
        "session": "probe_1", "verified_at": "2026-10-11T10:00:00+09:00",
        "capabilities": [
            {"name": "navigate", "status": "PASS", "execution_status": "PASS", "evidence": "fixture"},
            {"name": "beforeunload-dismiss", "status": "NOT_RUN",
             "execution_status": "BLOCKED_ENV", "evidence": "dialog closed before response"},
        ],
        "acceptance_criteria": [
            {"ac_id": "AC-1", "status": "PASS", "capability": "navigate", "method": "browser", "evidence": "navigation confirmed"},
            {"ac_id": "AC-2", "status": "NOT_RUN", "capability": "beforeunload-dismiss",
             "method": "browser", "evidence": "blocked by provider"},
        ],
        "cleanup": {"status": "PASS"},
    }

class BrowserEvidenceTests(unittest.TestCase):
    def test_mixed_success_and_capability_block(self):
        self.assertTrue(validate(fixture()))

    def test_never_pretend_ac_pass_on_blocked_capability(self):
        value = fixture()
        value["acceptance_criteria"][1]["status"] = "PASS"
        with self.assertRaises(ValueError):
            validate(value)

    def test_never_pretend_capability_pass_from_inconclusive(self):
        value = fixture()
        value["capabilities"][1]["status"] = "PASS"
        with self.assertRaises(ValueError):
            validate(value)

    def test_invalid_duplicate_and_missing_capabilities(self):
        value = fixture()
        value["capabilities"][1]["name"] = "navigate"
        with self.assertRaises(ValueError):
            validate(value)
        value = fixture()
        value["acceptance_criteria"][1]["capability"] = "unknown"
        with self.assertRaises(ValueError):
            validate(value)

    def test_policy_is_integrated_in_devkit(self):
        test = (ROOT / "custom-skills/shared/dev-frontend-test/SKILL.md").read_text(encoding="utf-8")
        feature = (ROOT / "custom-skills/shared/dev-frontend-feature/SKILL.md").read_text(encoding="utf-8")
        coder = (ROOT / "custom-skills/core/dev-review/SKILL.md").read_text(encoding="utf-8")
        policy = (ROOT / "custom-skills/shared/dev-frontend-test/references/browser-verification.md").read_text(encoding="utf-8")
        for token in ("Browser Verification Contract V1", "beforeunload", "BLOCKED_ENV",
                      "NOT_RUN", "browser_verification_evidence.py"):
            self.assertIn(token, test + policy)
        self.assertIn("browser-verification.md", feature)
        self.assertIn("Browser Verification Contract V1", coder)
        self.assertIn("DevKit", policy)

if __name__ == "__main__":
    unittest.main(verbosity=2)
