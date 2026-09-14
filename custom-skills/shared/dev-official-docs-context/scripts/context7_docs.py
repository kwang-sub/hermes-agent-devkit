#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

BASE_URL = "https://context7.com/api/v2"
DEFAULT_TIMEOUT = 15
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_RESULTS = 5
MAX_SNIPPETS = 8
MAX_SNIPPET_CHARS = 1800


class ProviderError(RuntimeError):
    pass


def _request(path: str, params: dict[str, str], timeout: int) -> Any:
    query = urllib.parse.urlencode(params)
    url = f"{BASE_URL}/{path}?{query}"
    headers = {
        "Accept": "application/json",
        "User-Agent": "hermes-agent-devkit/context7-readonly",
    }
    api_key = os.getenv("CONTEXT7_API_KEY", "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ProviderError("Context7 response exceeded bounded size")
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            raise ProviderError("Context7 authentication unavailable; configure CONTEXT7_API_KEY or use official fallback") from exc
        if exc.code == 429:
            raise ProviderError("Context7 rate limit exceeded; use official fallback") from exc
        raise ProviderError(f"Context7 HTTP error: {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ProviderError(f"Context7 network unavailable: {type(exc).__name__}") from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderError("Context7 returned invalid JSON") from exc


def _as_number(value: Any) -> str:
    return str(value) if isinstance(value, (int, float)) else "UNKNOWN"


def _normalize_version(value: str) -> str:
    return value.strip().removeprefix("v")


def _candidate_versions(item: dict[str, Any]) -> list[str]:
    raw = item.get("versions")
    if not isinstance(raw, list):
        return []
    return [str(v) for v in raw if str(v).strip()]


def _version_id(base_id: str, versions: list[str], requested: str) -> tuple[str, str]:
    if not requested:
        return base_id, "UNKNOWN"
    wanted = _normalize_version(requested)
    for value in versions:
        if _normalize_version(value) == wanted:
            clean = value.strip()
            return f"{base_id.rstrip('/')}/{clean}", "EXACT"
    wanted_parts = wanted.split(".")
    for value in versions:
        candidate = _normalize_version(value)
        parts = candidate.split(".")
        if len(wanted_parts) >= 2 and len(parts) >= 2 and parts[:2] == wanted_parts[:2]:
            return f"{base_id.rstrip('/')}/{value.strip()}", "COMPATIBLE"
    return base_id, "LATEST_ONLY"


def resolve(args: argparse.Namespace) -> int:
    try:
        data = _request("libs/search", {
            "libraryName": args.library,
            "query": args.query,
        }, args.timeout)
    except ProviderError as exc:
        print("CONTEXT7_STATUS=unavailable")
        print(f"CONTEXT7_DETAIL={exc}")
        return 0

    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list) or not results:
        print("CONTEXT7_STATUS=available")
        print("CONTEXT7_MATCH_COUNT=0")
        print("STATUS=partial")
        return 0

    print("CONTEXT7_STATUS=available")
    selected = 0
    for index, raw in enumerate(results[:MAX_RESULTS], 1):
        if not isinstance(raw, dict):
            continue
        library_id = str(raw.get("id", "")).strip()
        if not library_id:
            continue
        versions = _candidate_versions(raw)
        resolved_id, match = _version_id(library_id, versions, args.version or "")
        print(f"CANDIDATE_{index}_ID={library_id}")
        print(f"CANDIDATE_{index}_RESOLVED_ID={resolved_id}")
        print(f"CANDIDATE_{index}_TITLE={str(raw.get('title', '')).replace(chr(10), ' ')[:200]}")
        print(f"CANDIDATE_{index}_VERSION_MATCH={match}")
        print(f"CANDIDATE_{index}_SOURCE_REPUTATION={raw.get('sourceReputation', 'UNKNOWN')}")
        print(f"CANDIDATE_{index}_BENCHMARK_SCORE={_as_number(raw.get('benchmarkScore'))}")
        print(f"CANDIDATE_{index}_VERSIONS={','.join(versions[:20]) if versions else 'UNKNOWN'}")
        selected += 1
    print(f"CONTEXT7_MATCH_COUNT={selected}")
    print("STATUS=pass" if selected else "STATUS=partial")
    return 0


def _safe_text(value: Any, limit: int = MAX_SNIPPET_CHARS) -> str:
    text = str(value or "").replace("\x00", "").strip()
    return text[:limit]


def query(args: argparse.Namespace) -> int:
    if not args.library_id.startswith("/"):
        print("BLOCK_REASON=library id must be an explicit Context7 /org/project[/version] id")
        print("STATUS=blocked")
        return 2
    try:
        data = _request("context", {
            "libraryId": args.library_id,
            "query": args.query,
            "type": "json",
        }, args.timeout)
    except ProviderError as exc:
        print("CONTEXT7_STATUS=unavailable")
        print(f"CONTEXT7_DETAIL={exc}")
        print("STATUS=partial")
        return 0

    print("CONTEXT7_STATUS=available")
    print(f"CONTEXT7_LIBRARY_ID={args.library_id}")
    code = data.get("codeSnippets") if isinstance(data, dict) else []
    info = data.get("infoSnippets") if isinstance(data, dict) else []
    code = code if isinstance(code, list) else []
    info = info if isinstance(info, list) else []
    emitted = 0

    for item in code:
        if emitted >= MAX_SNIPPETS or not isinstance(item, dict):
            break
        emitted += 1
        print(f"--- CODE_SNIPPET_{emitted} ---")
        print(f"TITLE={_safe_text(item.get('codeTitle'), 300)}")
        print(f"DESCRIPTION={_safe_text(item.get('codeDescription'), 500)}")
        code_list = item.get("codeList")
        if isinstance(code_list, list):
            joined = "\n\n".join(
                _safe_text(entry.get("code") if isinstance(entry, dict) else entry)
                for entry in code_list[:3]
            )
            print(joined[:MAX_SNIPPET_CHARS])

    for item in info:
        if emitted >= MAX_SNIPPETS or not isinstance(item, dict):
            break
        emitted += 1
        print(f"--- INFO_SNIPPET_{emitted} ---")
        print(_safe_text(item.get("content")))

    print(f"CONTEXT7_SNIPPET_COUNT={emitted}")
    print("STATUS=pass" if emitted else "STATUS=partial")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only Context7 official documentation provider")
    sub = parser.add_subparsers(dest="command", required=True)

    resolve_parser = sub.add_parser("resolve")
    resolve_parser.add_argument("--library", required=True)
    resolve_parser.add_argument("--query", required=True)
    resolve_parser.add_argument("--version")
    resolve_parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    resolve_parser.set_defaults(func=resolve)

    query_parser = sub.add_parser("query")
    query_parser.add_argument("--library-id", required=True)
    query_parser.add_argument("--query", required=True)
    query_parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    query_parser.set_defaults(func=query)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
