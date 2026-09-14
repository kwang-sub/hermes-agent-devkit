#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
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

    def test_anonymous_is_default_and_sends_no_authorization_header(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            headers, mode = MOD._headers()
        self.assertIsNone(headers)
        self.assertEqual(mode, "anonymous")

    def test_api_key_is_optional_higher_limit_bearer_mode(self) -> None:
        with patch.dict(os.environ, {"CONTEXT7_API_KEY": "ctx7-secret"}, clear=True):
            headers, mode = MOD._headers()
        self.assertEqual(mode, "bearer")
        self.assertEqual(headers, {"Authorization": "Bearer ctx7-secret"})

    def test_resolve_calls_hosted_mcp_resolver_with_version_hint(self) -> None:
        args = MOD.build_parser().parse_args([
            "resolve", "--library", "Next.js", "--version", "16.3.5",
            "--query", "generated route types",
        ])
        result = "Next.js /vercel/next.js/v16.3.5 source reputation High"
        with patch.object(MOD, "_call_mcp_tool_sync", return_value=(result, "anonymous")) as call:
            code, output = self.capture(MOD.resolve, args)
        self.assertEqual(code, 0)
        call.assert_called_once_with(
            "resolve-library-id",
            {"libraryName": "Next.js", "query": "generated route types"},
            MOD.DEFAULT_TIMEOUT,
        )
        self.assertIn("CONTEXT7_TRANSPORT=hosted_mcp", output)
        self.assertIn("CONTEXT7_AUTH_MODE=anonymous", output)
        self.assertIn("CONTEXT7_REQUESTED_VERSION=16.3.5", output)
        self.assertIn("VERSION_MATCH_HINT=EXACT", output)

    def test_query_calls_only_query_docs(self) -> None:
        args = MOD.build_parser().parse_args([
            "query", "--library-id", "/supabase/supabase/v2.116.0",
            "--query", "browser auth createClient",
        ])
        with patch.object(MOD, "_call_mcp_tool_sync", return_value=("official docs", "anonymous")) as call:
            code, output = self.capture(MOD.query, args)
        self.assertEqual(code, 0)
        call.assert_called_once_with(
            "query-docs",
            {
                "libraryId": "/supabase/supabase/v2.116.0",
                "query": "browser auth createClient",
            },
            MOD.DEFAULT_TIMEOUT,
        )
        self.assertIn("CONTEXT7_LIBRARY_ID=/supabase/supabase/v2.116.0", output)
        self.assertIn("STATUS=pass", output)

    def test_result_output_is_bounded(self) -> None:
        fake = SimpleNamespace(
            structuredContent=None,
            structured_content=None,
            content=[SimpleNamespace(text="x" * (MOD.MAX_RESULT_CHARS * 2))],
        )
        rendered = MOD._result_text(fake)
        self.assertEqual(len(rendered), MOD.MAX_RESULT_CHARS)

    def test_provider_failure_degrades_to_partial_without_secret_echo(self) -> None:
        args = MOD.build_parser().parse_args([
            "query", "--library-id", "/supabase/supabase", "--query", "auth",
        ])
        with patch.object(
            MOD,
            "_call_mcp_tool_sync",
            side_effect=MOD.ProviderError("Context7 hosted MCP unavailable: ConnectError"),
        ):
            code, output = self.capture(MOD.query, args)
        self.assertEqual(code, 0)
        self.assertIn("CONTEXT7_STATUS=unavailable", output)
        self.assertIn("STATUS=partial", output)
        self.assertNotIn("ctx7-secret", output)

    def test_query_requires_explicit_library_id(self) -> None:
        args = MOD.build_parser().parse_args([
            "query", "--library-id", "next", "--query", "routing",
        ])
        code, output = self.capture(MOD.query, args)
        self.assertEqual(code, 2)
        self.assertIn("STATUS=blocked", output)

    def test_only_documentation_tools_are_allowed(self) -> None:
        self.assertEqual(MOD.ALLOWED_TOOLS, {"resolve-library-id", "query-docs"})

    def test_self_test_accepts_modern_or_legacy_http_client(self) -> None:
        with patch.object(MOD, "_load_sdk", return_value=(object, lambda *a, **k: None)), \
             patch.dict(os.environ, {}, clear=True):
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = MOD.self_test()
        self.assertEqual(code, 0)
        self.assertIn("[PASS] Context7 Hosted MCP runtime client contract", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
