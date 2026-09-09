#!/usr/bin/env python3
from __future__ import annotations

import argparse
import py_compile
import tempfile
from pathlib import Path

PATCH_MARKER = "from hermes_cli.devkit_kanban_worker_context import kanban_worker_context"
ANCHOR = '    logger.info("hermes-tools MCP server registered %d/%d tools", exposed_count, len(EXPOSED_TOOLS))\n    return mcp\n'
REPLACEMENT = '''    from hermes_cli.devkit_kanban_worker_context import kanban_worker_context
    _devkit_context_description = (
        "Verify the active dispatcher-owned Kanban worker Task/Board/Run/Claim context. "
        "Call this before workspace/source work in Codex Kanban workers."
    )
    try:
        mcp.add_tool(
            kanban_worker_context,
            name="kanban_worker_context",
            description=_devkit_context_description,
        )
    except TypeError:
        mcp.tool(
            name="kanban_worker_context",
            description=_devkit_context_description,
        )(kanban_worker_context)
    exposed_count += 1

    logger.info("hermes-tools MCP server registered %d/%d tools", exposed_count, len(EXPOSED_TOOLS) + 1)
    return mcp
'''


def strict_compile(path: Path) -> None:
    with tempfile.TemporaryDirectory() as directory:
        py_compile.compile(str(path), cfile=str(Path(directory) / "x.pyc"), doraise=True)


def candidate(path: Path) -> bool:
    try:
        source = path.read_text(encoding="utf-8")
    except Exception:
        return False
    if PATCH_MARKER in source:
        return True
    return (
        "def _build_server()" in source
        and "EXPOSED_TOOLS" in source
        and "mcp.add_tool" in source
        and source.count(ANCHOR) == 1
    )


def find_target(root: Path) -> Path:
    found = [path for path in root.rglob("*.py") if candidate(path)]
    if len(found) != 1:
        raise RuntimeError(
            "expected exactly one Hermes tools MCP server patch target under "
            f"{root}; found {len(found)}: {found[:10]}"
        )
    return found[0]


def patch_source(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    if PATCH_MARKER in source:
        strict_compile(path)
        return "already-patched"
    if source.count(ANCHOR) != 1:
        raise RuntimeError(f"{path}: compatible Hermes tools MCP registration anchor not found")
    path.write_text(source.replace(ANCHOR, REPLACEMENT, 1), encoding="utf-8")
    strict_compile(path)
    return "patched"


def _sample() -> str:
    return '''import logging\nlogger=logging.getLogger(__name__)\nEXPOSED_TOOLS=("kanban_show",)\ndef _build_server():\n    mcp=object()\n    exposed_count=0\n    for name in EXPOSED_TOOLS:\n        try:\n            mcp.add_tool(name)\n        except TypeError:\n            pass\n        exposed_count += 1\n\n    logger.info("hermes-tools MCP server registered %d/%d tools", exposed_count, len(EXPOSED_TOOLS))\n    return mcp\n'''


def self_test() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        target = root / "hermes_tools_mcp_server.py"
        target.write_text(_sample(), encoding="utf-8")
        assert find_target(root) == target
        assert patch_source(target) == "patched"
        assert patch_source(target) == "already-patched"
        source = target.read_text(encoding="utf-8")
        assert PATCH_MARKER in source
        assert 'name="kanban_worker_context"' in source
        assert "len(EXPOSED_TOOLS) + 1" in source
    print("Hermes Codex Kanban context patch self-test passed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument("--search-root", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return

    target = find_target(args.search_root) if args.search_root else args.path
    if target is None:
        parser.error("path or --search-root required")
    print(f"Hermes Codex Kanban context source state={patch_source(target)}: {target}")


if __name__ == "__main__":
    main()
