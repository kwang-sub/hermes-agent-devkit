#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "figma_context.py"
spec = importlib.util.spec_from_file_location("figma_context", MODULE)
assert spec and spec.loader
figma = importlib.util.module_from_spec(spec)
spec.loader.exec_module(figma)


def assert_equal(actual, expected, label):
    if actual != expected:
        raise AssertionError(f"{label}: expected={expected!r}, actual={actual!r}")


def test_parse_url():
    key, node = figma.parse_figma_url("https://www.figma.com/design/ABC_123/Test?node-id=12-34")
    assert_equal(key, "ABC_123", "file key")
    assert_equal(node, "12:34", "node id")


def test_auth_headers():
    old_access = os.environ.get("FIGMA_ACCESS_TOKEN")
    old_oauth = os.environ.get("FIGMA_OAUTH_TOKEN")
    try:
        os.environ["FIGMA_ACCESS_TOKEN"] = "access-secret"
        os.environ.pop("FIGMA_OAUTH_TOKEN", None)
        assert_equal(figma.auth_headers(), {"X-Figma-Token": "access-secret"}, "access auth")
        os.environ["FIGMA_OAUTH_TOKEN"] = "oauth-secret"
        assert_equal(figma.auth_headers(), {"Authorization": "Bearer oauth-secret"}, "oauth auth")
    finally:
        if old_access is None:
            os.environ.pop("FIGMA_ACCESS_TOKEN", None)
        else:
            os.environ["FIGMA_ACCESS_TOKEN"] = old_access
        if old_oauth is None:
            os.environ.pop("FIGMA_OAUTH_TOKEN", None)
        else:
            os.environ["FIGMA_OAUTH_TOKEN"] = old_oauth


def test_targeted_inspect():
    calls = []
    original = figma.request_json
    try:
        def fake(path, params=None):
            calls.append((path, params))
            if path.startswith("/v1/images/"):
                return {"images": {"12:34": "https://example.test/render.png"}}
            return {
                "name": "Asset App",
                "lastModified": "2026-09-06T00:00:00Z",
                "version": "7",
                "nodes": {
                    "12:34": {
                        "document": {"id": "12:34", "name": "Dashboard", "type": "FRAME", "layoutMode": "VERTICAL", "children": [{"id": "1:2", "name": "Title", "type": "TEXT", "characters": "Assets"}]},
                        "components": {}, "componentSets": {}, "styles": {}
                    }
                }
            }
        figma.request_json = fake
        result = figma.inspect("https://figma.com/design/ABC/Test?node-id=12-34", 4, True, False, False)
        assert_equal(result["status"], "pass", "status")
        assert_equal(result["source"]["nodeId"], "12:34", "source node")
        assert_equal(result["node"]["layoutMode"], "VERTICAL", "layout")
        assert_equal(result["renderUrl"], "https://example.test/render.png", "render")
        assert_equal(len(calls), 2, "request count")
    finally:
        figma.request_json = original


def test_file_level_is_blocked():
    try:
        figma.inspect("https://figma.com/design/ABC/Test", 4, False, False, False)
    except figma.FigmaError as exc:
        if "node-id" not in str(exc):
            raise
    else:
        raise AssertionError("file-level URL must be blocked without --allow-file")


def test_safe_output():
    old = os.environ.get("HERMES_WRITE_SAFE_ROOT")
    try:
        os.environ["HERMES_WRITE_SAFE_ROOT"] = "/tmp/figma-safe:/opt/data"
        assert str(figma.safe_output("/tmp/figma-safe/a.png")).endswith("/tmp/figma-safe/a.png")
        try:
            figma.safe_output("/tmp/not-safe/a.png")
        except figma.FigmaError:
            pass
        else:
            raise AssertionError("unsafe preview path must be rejected")
    finally:
        if old is None:
            os.environ.pop("HERMES_WRITE_SAFE_ROOT", None)
        else:
            os.environ["HERMES_WRITE_SAFE_ROOT"] = old


def main():
    for test in (test_parse_url, test_auth_headers, test_targeted_inspect, test_file_level_is_blocked, test_safe_output):
        test()
    print("[PASS] Figma context tests")


if __name__ == "__main__":
    main()
