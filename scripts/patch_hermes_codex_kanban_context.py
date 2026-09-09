#!/usr/bin/env python3
from __future__ import annotations

import argparse
import py_compile
import tempfile
from pathlib import Path

SCHEMA_MARKER = "KANBAN_WORKER_CONTEXT_SCHEMA = _schema("
HANDLER_MARKER = '@_kanban_handler("kanban_worker_context")'
TOOL_MARKER = '"kanban_worker_context"'

SCHEMA_APPEND = '''\n\nKANBAN_WORKER_CONTEXT_SCHEMA = _schema(\n    "kanban_worker_context",\n    (\n        "Verify the active dispatcher-owned Kanban worker Task/Board/Run/Claim context. "\n        "Use this read-only gate before workspace/source work in a Kanban worker. "\n        "Codex native shell intentionally does not receive worker ownership environment variables."\n    ),\n    {},\n    [],\n)\n'''

HANDLER_INSERT = '''\n\n@_kanban_handler("kanban_worker_context")\ndef _handle_worker_context(args: dict, **kw) -> str:\n    """Read-only DevKit worker ownership gate backed by the Hermes MCP process."""\n    from hermes_cli.devkit_kanban_worker_context import kanban_worker_context\n\n    return kanban_worker_context()\n'''


def strict_compile(path: Path) -> None:
    with tempfile.TemporaryDirectory() as directory:
        py_compile.compile(str(path), cfile=str(Path(directory) / "x.pyc"), doraise=True)


def replace_once(source: str, anchor: str, replacement: str, *, label: str) -> str:
    count = source.count(anchor)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one compatible anchor, found {count}")
    return source.replace(anchor, replacement, 1)


def patch_schemas(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    if SCHEMA_MARKER in source:
        strict_compile(path)
        return "already-patched"
    path.write_text(source.rstrip() + SCHEMA_APPEND, encoding="utf-8")
    strict_compile(path)
    return "patched"


def patch_kanban_tools(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    changed = False

    if "KANBAN_WORKER_CONTEXT_SCHEMA" not in source:
        anchor = "KANBAN_SHOW_SCHEMA, KANBAN_UNBLOCK_SCHEMA)"
        source = replace_once(
            source,
            anchor,
            "KANBAN_SHOW_SCHEMA, KANBAN_UNBLOCK_SCHEMA, KANBAN_WORKER_CONTEXT_SCHEMA)",
            label=str(path),
        )
        changed = True

    if HANDLER_MARKER not in source:
        anchor = "\n\n# --- Registration (order preserved: it is the order tools appear in the schema) ---\n"
        source = replace_once(source, anchor, HANDLER_INSERT + anchor, label=str(path))
        changed = True

    tool_row = '    ("kanban_worker_context", KANBAN_WORKER_CONTEXT_SCHEMA, _handle_worker_context, "🔐"),\n'
    if tool_row not in source:
        anchor = '    ("kanban_show", KANBAN_SHOW_SCHEMA, _handle_show, "📋"),\n'
        source = replace_once(source, anchor, anchor + tool_row, label=str(path))
        changed = True

    path.write_text(source, encoding="utf-8")
    strict_compile(path)
    return "patched" if changed else "already-patched"


def patch_toolsets(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    if TOOL_MARKER in source:
        strict_compile(path)
        return "already-patched"
    anchor = '    "kanban_show", "kanban_list",\n'
    source = replace_once(
        source,
        anchor,
        '    "kanban_show", "kanban_worker_context", "kanban_list",\n',
        label=str(path),
    )
    path.write_text(source, encoding="utf-8")
    strict_compile(path)
    return "patched"


def patch_mcp_server(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    if TOOL_MARKER in source:
        strict_compile(path)
        return "already-patched"
    anchor = '    "kanban_heartbeat", "kanban_show", "kanban_list",\n'
    source = replace_once(
        source,
        anchor,
        '    "kanban_heartbeat", "kanban_show", "kanban_worker_context", "kanban_list",\n',
        label=str(path),
    )
    path.write_text(source, encoding="utf-8")
    strict_compile(path)
    return "patched"


def patch_root(root: Path) -> list[tuple[Path, str]]:
    targets = (
        (root / "tools" / "kanban_tools_schemas.py", patch_schemas),
        (root / "tools" / "kanban_tools.py", patch_kanban_tools),
        (root / "toolsets.py", patch_toolsets),
        (root / "agent" / "transports" / "hermes_tools_mcp_server.py", patch_mcp_server),
    )
    missing = [str(path) for path, _ in targets if not path.is_file()]
    if missing:
        raise RuntimeError("Hermes Codex Kanban context patch targets missing: " + ", ".join(missing))

    results: list[tuple[Path, str]] = []
    for path, patcher in targets:
        results.append((path, patcher(path)))
    return results


def _write_fixture(root: Path) -> None:
    (root / "tools").mkdir(parents=True)
    (root / "agent" / "transports").mkdir(parents=True)
    (root / "tools" / "kanban_tools_schemas.py").write_text(
        '''def _schema(name, description, properties, required):\n    return {"name": name}\n''',
        encoding="utf-8",
    )
    (root / "tools" / "kanban_tools.py").write_text(
        '''from tools.kanban_tools_schemas import (\n    KANBAN_SHOW_SCHEMA, KANBAN_UNBLOCK_SCHEMA)\ndef _kanban_handler(name):\n    return lambda fn: fn\ndef _handle_show(args, **kw): return "show"\ndef _check_kanban_mode(): return True\ndef _check_kanban_orchestrator_mode(): return True\nclass R:\n    def register(self, **kw): pass\nregistry=R()\n\n# --- Registration (order preserved: it is the order tools appear in the schema) ---\n_ORCHESTRATOR_TOOLS=frozenset()\n_TOOLS = (\n    ("kanban_show", KANBAN_SHOW_SCHEMA, _handle_show, "📋"),\n)\nfor _name, _sch, _handler, _emoji in _TOOLS:\n    _gate = _check_kanban_orchestrator_mode if _name in _ORCHESTRATOR_TOOLS else _check_kanban_mode\n    registry.register(name=_name, toolset="kanban", schema=_sch, handler=_handler, emoji=_emoji, check_fn=_gate)\n''',
        encoding="utf-8",
    )
    (root / "toolsets.py").write_text(
        '''_HERMES_CORE_TOOLS = [\n    "kanban_show", "kanban_list",\n]\n''',
        encoding="utf-8",
    )
    (root / "agent" / "transports" / "hermes_tools_mcp_server.py").write_text(
        '''EXPOSED_TOOLS = (\n    "kanban_heartbeat", "kanban_show", "kanban_list",\n)\n''',
        encoding="utf-8",
    )


def self_test() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        _write_fixture(root)
        first = patch_root(root)
        assert all(state == "patched" for _, state in first)
        second = patch_root(root)
        assert all(state == "already-patched" for _, state in second)

        schemas = (root / "tools" / "kanban_tools_schemas.py").read_text(encoding="utf-8")
        tools = (root / "tools" / "kanban_tools.py").read_text(encoding="utf-8")
        toolsets = (root / "toolsets.py").read_text(encoding="utf-8")
        mcp = (root / "agent" / "transports" / "hermes_tools_mcp_server.py").read_text(encoding="utf-8")
        assert SCHEMA_MARKER in schemas
        assert HANDLER_MARKER in tools
        assert '("kanban_worker_context", KANBAN_WORKER_CONTEXT_SCHEMA' in tools
        assert '"kanban_show", "kanban_worker_context", "kanban_list"' in toolsets
        assert '"kanban_show", "kanban_worker_context", "kanban_list"' in mcp
    print("Hermes Codex Kanban context registry patch self-test passed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hermes-root", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return
    if args.hermes_root is None:
        parser.error("--hermes-root required")
    for path, state in patch_root(args.hermes_root):
        print(f"Hermes Codex Kanban context source state={state}: {path}")


if __name__ == "__main__":
    main()
