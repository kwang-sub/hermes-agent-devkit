#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any, Callable

MCP_URL = "https://mcp.context7.com/mcp"
DEFAULT_TIMEOUT = 30
MAX_RESULT_CHARS = 12000
ALLOWED_TOOLS = frozenset({"resolve-library-id", "query-docs"})


class ProviderError(RuntimeError):
    pass


def _load_sdk() -> tuple[type[Any], Callable[..., Any]]:
    """Load the MCP SDK lazily from the Hermes runtime.

    Hermes currently supports both the modern ``streamable_http_client`` name
    and the legacy ``streamablehttp_client`` alias. Keep the DevKit adapter
    compatible with either SDK lane while preferring the modern symbol.
    """

    try:
        from mcp import ClientSession
        from mcp.client import streamable_http
    except ImportError as exc:  # pragma: no cover - exercised in runtime smoke
        raise ProviderError("Hermes MCP SDK is unavailable") from exc

    http_client = getattr(streamable_http, "streamable_http_client", None)
    if http_client is None:
        http_client = getattr(streamable_http, "streamablehttp_client", None)
    if http_client is None:
        raise ProviderError("Hermes MCP SDK has no Streamable HTTP client")
    return ClientSession, http_client


def _headers() -> tuple[dict[str, str] | None, str]:
    api_key = os.getenv("CONTEXT7_API_KEY", "").strip()
    if not api_key:
        return None, "anonymous"
    return {"Authorization": f"Bearer {api_key}"}, "bearer"


def _tool_names(list_result: Any) -> set[str]:
    tools = getattr(list_result, "tools", None)
    if tools is None and isinstance(list_result, dict):
        tools = list_result.get("tools")
    if not isinstance(tools, list):
        return set()
    names: set[str] = set()
    for tool in tools:
        name = getattr(tool, "name", None)
        if name is None and isinstance(tool, dict):
            name = tool.get("name")
        if isinstance(name, str) and name:
            names.add(name)
    return names


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if hasattr(value, "model_dump"):
        try:
            return _json_safe(value.model_dump())
        except Exception:
            pass
    return str(value)


def _result_text(result: Any) -> str:
    structured = getattr(result, "structuredContent", None)
    if structured is None:
        structured = getattr(result, "structured_content", None)
    if structured is not None:
        try:
            rendered = json.dumps(_json_safe(structured), ensure_ascii=False, indent=2)
            if rendered.strip() not in {"", "{}", "[]", "null"}:
                return rendered[:MAX_RESULT_CHARS]
        except (TypeError, ValueError):
            pass

    content = getattr(result, "content", None)
    if content is None and isinstance(result, dict):
        content = result.get("content")
    if isinstance(content, list):
        pieces: list[str] = []
        for item in content:
            text = getattr(item, "text", None)
            if text is None and isinstance(item, dict):
                text = item.get("text")
            if text is not None:
                pieces.append(str(text))
        if pieces:
            return "\n\n".join(pieces)[:MAX_RESULT_CHARS]

    return str(_json_safe(result))[:MAX_RESULT_CHARS]


async def _call_mcp_tool(tool_name: str, arguments: dict[str, Any], timeout: int) -> tuple[str, str]:
    if tool_name not in ALLOWED_TOOLS:
        raise ProviderError(f"Context7 MCP tool is not allowed: {tool_name}")

    ClientSession, http_client = _load_sdk()
    headers, auth_mode = _headers()

    try:
        async with asyncio.timeout(timeout):
            async with http_client(MCP_URL, headers=headers) as transport:
                read_stream, write_stream = transport[0], transport[1]
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    available = _tool_names(await session.list_tools())
                    missing = ALLOWED_TOOLS - available
                    if missing:
                        raise ProviderError(
                            "Context7 hosted MCP is missing expected tools: "
                            + ", ".join(sorted(missing))
                        )
                    result = await session.call_tool(tool_name, arguments)
    except TimeoutError as exc:
        raise ProviderError("Context7 hosted MCP timed out") from exc
    except ProviderError:
        raise
    except Exception as exc:
        # Avoid echoing request headers or credentials through provider exceptions.
        raise ProviderError(f"Context7 hosted MCP unavailable: {type(exc).__name__}") from exc

    return _result_text(result), auth_mode


def _call_mcp_tool_sync(tool_name: str, arguments: dict[str, Any], timeout: int) -> tuple[str, str]:
    return asyncio.run(_call_mcp_tool(tool_name, arguments, timeout))


def _normalize_version(value: str) -> str:
    return value.strip().removeprefix("v")


def _version_match_hint(text: str, requested: str | None) -> str:
    if not requested:
        return "UNKNOWN"
    wanted = _normalize_version(requested)
    if not wanted:
        return "UNKNOWN"
    normalized_text = text.replace("@v", "@").replace("/v", "/")
    return "EXACT" if wanted in normalized_text else "UNKNOWN"


def resolve(args: argparse.Namespace) -> int:
    arguments = {
        "libraryName": args.library,
        "query": args.query,
    }
    try:
        text, auth_mode = _call_mcp_tool_sync("resolve-library-id", arguments, args.timeout)
    except ProviderError as exc:
        print("CONTEXT7_TRANSPORT=hosted_mcp")
        print("CONTEXT7_STATUS=unavailable")
        print(f"CONTEXT7_DETAIL={exc}")
        print("STATUS=partial")
        return 0

    print("CONTEXT7_TRANSPORT=hosted_mcp")
    print(f"CONTEXT7_AUTH_MODE={auth_mode}")
    print("CONTEXT7_STATUS=available")
    if args.version:
        print(f"CONTEXT7_REQUESTED_VERSION={args.version}")
    print(f"VERSION_MATCH_HINT={_version_match_hint(text, args.version)}")
    print("--- CONTEXT7_MCP_RESULT ---")
    print(text)
    print("STATUS=pass" if text.strip() else "STATUS=partial")
    return 0


def query(args: argparse.Namespace) -> int:
    if not args.library_id.startswith("/"):
        print("BLOCK_REASON=library id must be an explicit Context7 /org/project[/version] id")
        print("STATUS=blocked")
        return 2

    arguments = {
        "libraryId": args.library_id,
        "query": args.query,
    }
    try:
        text, auth_mode = _call_mcp_tool_sync("query-docs", arguments, args.timeout)
    except ProviderError as exc:
        print("CONTEXT7_TRANSPORT=hosted_mcp")
        print("CONTEXT7_STATUS=unavailable")
        print(f"CONTEXT7_DETAIL={exc}")
        print("STATUS=partial")
        return 0

    print("CONTEXT7_TRANSPORT=hosted_mcp")
    print(f"CONTEXT7_AUTH_MODE={auth_mode}")
    print("CONTEXT7_STATUS=available")
    print(f"CONTEXT7_LIBRARY_ID={args.library_id}")
    print("--- CONTEXT7_MCP_RESULT ---")
    print(text)
    print("STATUS=pass" if text.strip() else "STATUS=partial")
    return 0


def self_test() -> int:
    try:
        _, http_client = _load_sdk()
    except ProviderError as exc:
        print(f"[FAIL] {exc}")
        return 1
    if not callable(http_client):
        print("[FAIL] Context7 Hosted MCP HTTP client is not callable")
        return 1
    headers, auth_mode = _headers()
    if auth_mode == "anonymous" and headers is not None:
        print("[FAIL] anonymous mode must not send Authorization headers")
        return 1
    print("[PASS] Context7 Hosted MCP runtime client contract")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only Context7 Hosted MCP documentation provider")
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

    self_test_parser = sub.add_parser("--self-test")
    self_test_parser.set_defaults(func=lambda _args: self_test())
    return parser


def main() -> int:
    # Support the conventional one-flag self-test form without complicating
    # the normal resolve/query subcommand contract.
    if sys.argv[1:] == ["--self-test"]:
        return self_test()
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
