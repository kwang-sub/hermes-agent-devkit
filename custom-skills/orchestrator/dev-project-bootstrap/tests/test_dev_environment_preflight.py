from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "dev_environment_preflight.py"
SPEC = importlib.util.spec_from_file_location("dev_environment_preflight", SCRIPT)
assert SPEC and SPEC.loader
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)


class GitAttributesPreflightTest(unittest.TestCase):
    def test_creates_rules_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            self.assertEqual("created", preflight.ensure_gitattributes(repo))
            first = (repo / ".gitattributes").read_text(encoding="utf-8")
            self.assertIn("gradlew text eol=lf", first)
            self.assertIn("mvnw text eol=lf", first)
            self.assertIn("*.sh text eol=lf", first)
            self.assertIn("*.bat text eol=crlf", first)
            self.assertIn("*.cmd text eol=crlf", first)

            self.assertEqual("unchanged", preflight.ensure_gitattributes(repo))
            second = (repo / ".gitattributes").read_text(encoding="utf-8")
            self.assertEqual(first, second)

    def test_preserves_existing_non_conflicting_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            path = repo / ".gitattributes"
            path.write_text("* text=auto\n*.png binary\n", encoding="utf-8")

            self.assertEqual("updated", preflight.ensure_gitattributes(repo))
            updated = path.read_text(encoding="utf-8")
            self.assertTrue(updated.startswith("* text=auto\n*.png binary\n"))
            self.assertIn("# Hermes development defaults", updated)

    def test_blocks_conflicting_eol_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            path = repo / ".gitattributes"
            path.write_text("*.sh text eol=crlf\n", encoding="utf-8")

            with self.assertRaises(preflight.PreflightError):
                preflight.ensure_gitattributes(repo)

            self.assertEqual("*.sh text eol=crlf\n", path.read_text(encoding="utf-8"))

    def test_reports_existing_wrapper_crlf_without_rewriting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            wrapper = repo / "gradlew"
            wrapper.write_bytes(b"#!/bin/sh\r\necho ok\r\n")

            warnings = preflight.inspect_wrapper_eol(repo, "gradle")

            self.assertEqual(1, len(warnings))
            self.assertIn("CRLF", warnings[0])
            self.assertEqual(b"#!/bin/sh\r\necho ok\r\n", wrapper.read_bytes())


if __name__ == "__main__":
    unittest.main()
