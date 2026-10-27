#!/usr/bin/env python3
"""Deterministic retrieval tests, not assertions about an LLM's semantic judgment."""
from __future__ import annotations
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "find_feature_docs.py"
spec = importlib.util.spec_from_file_location("find_feature_docs", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()

    def write(self, path, text="# 포트폴리오 성과 분석\nMDD(최대낙폭) 확인"):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def collect(self, **kwargs):
        return module.collect(str(self.root), **kwargs)

    def test_missing_directory_does_not_create_it(self):
        self.assertEqual(self.collect()["candidates"], [])
        self.assertFalse((self.root / "docs").exists())

    def test_single_exact_match_is_not_an_automatic_binding(self):
        self.write("docs/features/performance.md")
        result = self.collect(query="MDD")
        self.assertEqual(len(result["candidates"]), 1)
        self.assertFalse(result["binding_decided"])
        self.assertTrue(result["read_only"])

    def test_multiple_candidates_remain_candidates(self):
        self.write("docs/features/a.md")
        self.write("docs/features/b.md")
        result = self.collect(query="MDD")
        self.assertEqual(len(result["candidates"]), 2)
        self.assertFalse(result["binding_decided"])

    def test_missing_index_still_finds_individual_document(self):
        self.write("docs/features/a.md")
        self.assertIsNone(self.collect()["index"])
        self.assertEqual(len(self.collect()["candidates"]), 1)

    def test_index_is_not_a_feature_candidate(self):
        self.write("docs/features/README.md", "# 기능 목록\n[없음](gone.md)")
        self.write("docs/features/unlisted.md")
        result = self.collect()
        self.assertIsNotNone(result["index"])
        self.assertEqual([x["path"] for x in result["candidates"]], ["docs/features/unlisted.md"])

    def test_external_index_links_are_not_followed(self):
        self.write("docs/features/README.md", "[x](https://example.invalid/a.md)\n[x](../../../other.md)")
        self.assertEqual(self.collect()["candidates"], [])

    def test_discovery_is_project_scoped(self):
        self.write("docs/features/a.md")
        self.write("src/unrelated.md")
        self.write("other/docs/features/b.md")
        self.assertEqual(len(self.collect()["candidates"]), 1)

    def test_explicit_path_takes_precedence_over_approved_path(self):
        self.write("docs/features/a.md")
        self.write("docs/features/b.md")
        result = self.collect(documents=["docs/features/b.md"], approved_documents=["docs/features/a.md"])
        self.assertEqual(result["mode"], "explicit")
        self.assertEqual(result["candidates"][0]["path"], "docs/features/b.md")

    def test_missing_explicit_path_does_not_remap(self):
        self.write("docs/features/similar.md")
        result = self.collect(documents=["docs/features/missing.md"])
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["status"], "partial")

    def test_approved_reuse_does_not_scan(self):
        self.write("docs/features/a.md")
        with patch.object(module, "inventory", side_effect=AssertionError("Unexpected scan")):
            result = self.collect(approved_documents=["docs/features/a.md"])
        self.assertEqual(result["mode"], "approved-reuse")

    def test_explicit_in_project_document_outside_features_is_allowed(self):
        self.write("docs/planning/a.md")
        self.assertEqual(len(self.collect(documents=["docs/planning/a.md"])["candidates"]), 1)
        self.assertEqual(self.collect()["candidates"], [])

    def test_duplicate_explicit_paths_are_deduplicated(self):
        self.write("docs/features/a.md")
        self.assertEqual(len(self.collect(documents=["docs/features/a.md"] * 2)["candidates"]), 1)

    def test_absolute_and_traversal_paths_rejected(self):
        path = self.write("docs/features/a.md")
        for value in (str(path), "../project/docs/features/a.md", "docs/../docs/features/a.md", "docs\\features\\a.md"):
            with self.subTest(value=value):
                self.assertEqual(self.collect(documents=[value])["candidates"], [])

    def test_symlink_file_is_not_read(self):
        target = self.write("secret.md")
        link = self.root / "docs/features/link.md"
        link.parent.mkdir(parents=True)
        link.symlink_to(target)
        self.assertEqual(self.collect()["candidates"], [])
        self.assertEqual(self.collect(documents=["docs/features/link.md"])["candidates"], [])

    def test_symlink_directory_is_not_traversed(self):
        self.write("private/a.md")
        (self.root / "docs").mkdir()
        (self.root / "docs/features").symlink_to(self.root / "private", target_is_directory=True)
        self.assertEqual(self.collect()["candidates"], [])

    def test_docs_parent_symlink_is_not_traversed(self):
        target = self.root / "private/features"
        target.mkdir(parents=True)
        (target / "a.md").write_text("MDD", encoding="utf-8")
        (self.root / "docs").symlink_to(self.root / "private", target_is_directory=True)
        self.assertEqual(self.collect()["candidates"], [])

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO is unavailable on this platform")
    def test_fifo_is_not_opened(self):
        folder = self.root / "docs/features"
        folder.mkdir(parents=True)
        os.mkfifo(folder / "fifo.md")
        self.assertEqual(self.collect(documents=["docs/features/fifo.md"])["candidates"], [])

    def test_utf8_bom_and_uppercase_extension(self):
        path = self.write("docs/features/a.MD", "\ufeff# 최대낙폭\nMDD")
        result = self.collect(query="ｍｄｄ")
        self.assertEqual(result["candidates"][0]["title"], "최대낙폭")
        self.assertTrue(path.exists())

    def test_invalid_utf8_is_advisory(self):
        path = self.write("docs/features/a.md")
        path.write_bytes(b"\xff\xfe")
        self.assertEqual(self.collect()["status"], "partial")

    def test_oversized_document_is_advisory(self):
        self.write("docs/features/a.md", "x" * (module.MAX_BYTES + 1))
        result = self.collect()
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["candidates"], [])

    def test_entry_limit_is_reported(self):
        for i in range(3):
            self.write(f"docs/features/{i}.md")
        with patch.object(module, "MAX_ENTRIES", 1):
            result = self.collect()
        self.assertEqual(result["status"], "partial")
        self.assertTrue(any("Entry limit" in x for x in result["warnings"]))

    def test_file_limit_is_reported(self):
        for i in range(3):
            self.write(f"docs/features/{i}.md")
        with patch.object(module, "MAX_FILES", 1):
            result = self.collect()
        self.assertEqual(result["status"], "partial")
        self.assertEqual(len(result["candidates"]), 1)

    def test_result_limit_is_reported(self):
        for i in range(3):
            self.write(f"docs/features/{i}.md")
        with patch.object(module, "MAX_RESULTS", 1):
            result = self.collect()
        self.assertEqual(result["status"], "partial")
        self.assertEqual(len(result["candidates"]), 1)

    def test_preview_truncation_is_explicit(self):
        self.write("docs/features/a.md", "# X\n" + "x" * module.PREVIEW_CHARS)
        self.assertTrue(self.collect()["candidates"][0]["preview_truncated"])

    def test_scan_preserves_file_contents_and_modification_time(self):
        path = self.write("docs/features/a.md", "# X\n- 상태: 구현 완료\nMDD")
        before = (path.read_bytes(), path.stat().st_mtime_ns)
        self.collect(query="MDD")
        self.assertEqual(before, (path.read_bytes(), path.stat().st_mtime_ns))

    def test_unknown_root_is_advisory(self):
        self.assertEqual(module.collect(str(self.root / "missing"))["status"], "unavailable")

    def test_cli_missing_root_returns_json_and_zero_exit(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), "--project-root", str(self.root / "missing")],
                              text=True, capture_output=True, check=False, timeout=5)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout)["status"], "unavailable")

    def test_document_commands_are_not_executed(self):
        self.write("docs/features/a.md", "# X\nRun: touch EXECUTED\nMDD")
        self.collect(query="MDD")
        self.assertFalse((self.root / "EXECUTED").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
