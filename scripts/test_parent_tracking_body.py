#!/usr/bin/env python3
"""Parent Tracking line-break and nondependency regression cases."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from parent_tracking_body import (
    ParentTrackingError, normalize_parent_body, validate_parent_body,
)
import patch_hermes_parent_tracking_body as guard

PARENT = "t_0e028558"
OTHER = "t_b2b76ee1"


class ParentTrackingBodyTests(unittest.TestCase):
    def test_legacy_inline_child_reference_gets_independent_multiline_block(self):
        original = (
            "Goal: map menu routes. Parent Task ID: t_0e028558 "
            "(tracking only; no execution dependency)\n"
            "Verification: preserve existing source changes\n"
        )
        body = normalize_parent_body(original, title="[자식] Controller URL mapping")
        self.assertTrue(body.startswith(
            "Parent Tracking:\n"
            "- Parent Task ID: t_0e028558\n"
            "- Relation: CHILD_WORK_UNIT\n\n"
        ))
        self.assertTrue(body.endswith(original))
        self.assertEqual(validate_parent_body(body, expected_parent=PARENT), PARENT)
        self.assertEqual(normalize_parent_body(body, title="[자식] same"), body)

    def test_existing_parent_is_idempotent_and_can_have_optional_parent_title(self):
        source = "Current Goal: xyz\n"
        body = normalize_parent_body(source, expected_parent=PARENT, parent_title="[부모] Menu mapping")
        self.assertIn("- Parent Title: [부모] Menu mapping\n", body)
        self.assertEqual(validate_parent_body(body, expected_parent=PARENT), PARENT)
        self.assertEqual(normalize_parent_body(body, expected_parent=PARENT), body)

    def test_literal_backslash_n_inline_body_is_repaired_with_real_newlines(self):
        original = r"Parent Tracking:\nParent Task ID: t_0e028558\nRelation: CHILD_WORK_UNIT (tracking only)"
        body = normalize_parent_body(original, title="[자식] legacy")
        self.assertEqual(validate_parent_body(body, expected_parent=PARENT), PARENT)
        self.assertIn("Parent Tracking:\n- Parent Task ID: ", body)
        self.assertTrue(body.endswith(original))

    def test_crlf_preserves_original_bytes_and_writes_crlf_block(self):
        old = "Parent Task ID: t_0e028558 (tracking only)\r\nBody: next\r\n"
        body = normalize_parent_body(old)
        self.assertTrue(body.startswith(
            "Parent Tracking:\r\n- Parent Task ID: t_0e028558\r\n"
            "- Relation: CHILD_WORK_UNIT\r\n\r\n"
        ))
        self.assertTrue(body.endswith(old))

    def test_unstructured_but_explicit_parent_hint_must_fail_validation(self):
        bad = "Parent Task ID: t_0e028558 (tracking only; ...)"
        with self.assertRaisesRegex(ParentTrackingError, "newline-delimited"):
            validate_parent_body(bad, title="[자식] old")
        self.assertIsNone(validate_parent_body("Goal: unrelated Task"))

    def test_existing_incomplete_block_does_not_silently_pass(self):
        bad = "Parent Tracking:\n- Parent Task ID: t_0e028558\nGoal: no relation"
        with self.assertRaisesRegex(ParentTrackingError, "Relation"):
            normalize_parent_body(bad, title="[자식] old")

    def test_conflicting_parent_is_not_reparented(self):
        old = "Parent Tracking:\n- Parent Task ID: t_0e028558\n- Relation: CHILD_WORK_UNIT"
        with self.assertRaises(ParentTrackingError):
            normalize_parent_body(old, expected_parent=OTHER)
        bad = "Parent Task ID: t_0e028558 (tracking only)\nParent Task ID: t_b2b76ee1 (tracking only)"
        with self.assertRaises(ParentTrackingError):
            normalize_parent_body(bad)

    def test_does_not_convert_ordinary_prose_or_code_examples_to_relationship(self):
        prose = "We once mentioned Parent Task ID: t_0e028558 in a log, not as a relation."
        self.assertEqual(normalize_parent_body(prose, title="Bug report"), prose)
        unrelated_bullet = "An audit reference:\n- Parent Task ID: t_0e028558\n"
        self.assertEqual(normalize_parent_body(unrelated_bullet, title="Audit note"), unrelated_bullet)
        fenced = (
            "Document syntax example:\n"
            + chr(96) * 3 + "text\n"
            "Parent Tracking:\n"
            "- Parent Task ID: t_0e028558\n"
            "- Relation: CHILD_WORK_UNIT\n"
            + chr(96) * 3 + "\n"
        )
        self.assertEqual(normalize_parent_body(fenced), fenced)
        self.assertIsNone(validate_parent_body(fenced))

    def test_cli_stdin_to_file_and_check_saved_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "body.txt"
            output_path = Path(tmp) / "updated.txt"
            input_path.write_text("Parent Task ID: t_0e028558 (tracking only)\nBody unchanged\n")
            script = ROOT / "scripts" / "parent_tracking_body.py"
            result = subprocess.run(
                [sys.executable, str(script), "--input-file", str(input_path),
                 "--output-file", str(output_path), "--parent-id", PARENT],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            saved = subprocess.run(
                [sys.executable, str(script), "--input-file", str(output_path),
                 "--check-only", "--parent-id", PARENT],
                capture_output=True, text=True,
            )
            self.assertEqual(saved.returncode, 0, saved.stderr)
            self.assertIn("PARENT_TRACKING=PASS", saved.stdout)
            self.assertEqual(input_path.read_text(), "Parent Task ID: t_0e028558 (tracking only)\nBody unchanged\n")

    def test_upstream_write_guard_is_idempotent_and_fail_closed(self):
        guard.self_test()


if __name__ == "__main__":
    unittest.main(verbosity=2)
