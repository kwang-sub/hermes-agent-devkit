#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import importlib.util
import io
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "context7_docs.py"
SPEC = importlib.util.spec_from_file_location("context7_docs", SCRIPT)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class Context7DocsTest(unittest.TestCase):
    def capture(self, func, args):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = func(args)
        return code, stream.getvalue()

    def test_resolve_prefers_exact_version_id_when_available(self) -> None:
        args = MOD.build_parser().parse_args([
            "resolve", "--library", "Next.js", "--version", "16.3.5",
            "--query", "generated route types",
        ])
        payload = {"results": [{
            "id": "/vercel/next.js",
            "title": "Next.js",
            "versions": ["v16.3.5", "v16.3.4"],
            "sourceReputation": "High",
            "benchmarkScore": 95.5,
        }]}
        with patch.object(MOD, "_request", return_value=payload):
            code, output = self.capture(MOD.resolve, args)
        self.assertEqual(code, 0)
        self.assertIn("CANDIDATE_1_RESOLVED_ID=/vercel/next.js/v16.3.5", output)
        self.assertIn("CANDIDATE_1_VERSION_MATCH=EXACT", output)
        self.assertIn("CANDIDATE_1_SOURCE_REPUTATION=High", output)

    def test_resolve_marks_latest_only_when_version_missing(self) -> None:
        args = MOD.build_parser().parse_args([
            "resolve", "--library", "Next.js", "--version", "16.3.5",
            "--query", "generated route types",
        ])
        with patch.object(MOD, "_request", return_value={"results": [{
            "id": "/vercel/next.js", "title": "Next.js", "versions": ["v17.0.0"],
        }]}):
            _, output = self.capture(MOD.resolve, args)
        self.assertIn("CANDIDATE_1_VERSION_MATCH=LATEST_ONLY", output)
        self.assertIn("CANDIDATE_1_RESOLVED_ID=/vercel/next.js", output)

    def test_query_is_bounded(self) -> None:
        args = MOD.build_parser().parse_args([
            "query", "--library-id", "/vercel/next.js/v16.3.5", "--query", "routing",
        ])
        payload = {
            "codeSnippets": [{
                "codeTitle": "Example",
                "codeDescription": "desc",
                "codeList": [{"code": "x" * 4000}],
            } for _ in range(20)],
            "infoSnippets": [{"content": "info"} for _ in range(20)],
        }
        with patch.object(MOD, "_request", return_value=payload):
            code, output = self.capture(MOD.query, args)
        self.assertEqual(code, 0)
        self.assertIn("CONTEXT7_SNIPPET_COUNT=8", output)
        self.assertNotIn("CODE_SNIPPET_9", output)
        self.assertLess(len(output), 20000)

    def test_provider_failure_degrades_to_partial_without_secret_echo(self) -> None:
        args = MOD.build_parser().parse_args([
            "query", "--library-id", "/supabase/supabase", "--query", "auth",
        ])
        with patch.object(MOD, "_request", side_effect=MOD.ProviderError("Context7 rate limit exceeded; use official fallback")):
            code, output = self.capture(MOD.query, args)
        self.assertEqual(code, 0)
        self.assertIn("CONTEXT7_STATUS=unavailable", output)
        self.assertIn("STATUS=partial", output)

    def test_query_requires_explicit_library_id(self) -> None:
        args = MOD.build_parser().parse_args([
            "query", "--library-id", "next", "--query", "routing",
        ])
        code, output = self.capture(MOD.query, args)
        self.assertEqual(code, 2)
        self.assertIn("STATUS=blocked", output)


if __name__ == "__main__":
    unittest.main()
