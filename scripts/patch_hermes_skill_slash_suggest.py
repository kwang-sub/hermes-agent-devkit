#!/usr/bin/env python3
"""Patch Hermes so internal skills can stay executable but disappear from slash suggestions.

Suggestion decision order:
1. ``metadata.hermes.slash_suggest`` when explicitly true/false.
2. DevKit policy file (default: /opt/data/shared/references/skill-slash-suggest-policy.json).
3. Backward-compatible default: suggest the skill.

The patch intentionally does NOT change direct slash dispatch, skills_list, skill_view,
or execution/tool logs.
"""

from __future__ import annotations

import argparse
import py_compile
import tempfile
from pathlib import Path

MARKER = "DEVKIT_SLASH_SUGGEST_V1"


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one patch anchor, found {count}")
    return text.replace(old, new, 1)


def patch_skill_commands(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return "already-patched"

    old_entry = '''    commands[cmd_key] = {"name": name, "description": description or f"Invoke the {name} skill",
                         "skill_md_path": str(skill_md), "skill_dir": str(skill_md.parent)}'''
    new_entry = '''    # DEVKIT_SLASH_SUGGEST_V1: suggestion visibility is separate from registration/dispatch.
    metadata = frontmatter.get("metadata")
    hermes_metadata = metadata.get("hermes") if isinstance(metadata, dict) else None
    explicit_slash_suggest = (
        hermes_metadata.get("slash_suggest")
        if isinstance(hermes_metadata, dict) and isinstance(hermes_metadata.get("slash_suggest"), bool)
        else None
    )
    if explicit_slash_suggest is not None:
        slash_suggest = explicit_slash_suggest
    else:
        slash_suggest = True
        policy_path = Path(os.getenv(
            "HERMES_SLASH_SUGGEST_POLICY",
            "/opt/data/shared/references/skill-slash-suggest-policy.json",
        ))
        try:
            policy = json.loads(policy_path.read_text(encoding="utf-8")) if policy_path.is_file() else {}
            hidden = policy.get("hidden_skills", []) if isinstance(policy, dict) else []
            if isinstance(hidden, list) and name in hidden:
                slash_suggest = False
        except Exception as exc:
            logger.debug("Ignoring invalid slash suggestion policy %s: %s", policy_path, exc)
    commands[cmd_key] = {"name": name, "description": description or f"Invoke the {name} skill",
                         "skill_md_path": str(skill_md), "skill_dir": str(skill_md.parent),
                         "slash_suggest": slash_suggest}'''
    text = _replace_once(text, old_entry, new_entry, "agent.skill_commands")
    path.write_text(text, encoding="utf-8")
    return "patched"


def patch_completion(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return "already-patched"

    old = '''    def _iter_skill_commands(self) -> Mapping[str, dict[str, Any]]:
        return self._call_provider(self._skill_commands_provider)'''
    new = '''    def _iter_skill_commands(self) -> Mapping[str, dict[str, Any]]:
        # DEVKIT_SLASH_SUGGEST_V1: autocomplete sees only suggested skills; dispatch keeps the full map.
        commands = self._call_provider(self._skill_commands_provider)
        return {key: info for key, info in commands.items()
                if info.get("slash_suggest", True)}'''
    text = _replace_once(text, old, new, "hermes_cli.commands_completion")
    path.write_text(text, encoding="utf-8")
    return "patched"


def patch_catalog(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return "already-patched"

    old = '''    for k, info in sorted(_tools_mod("agent.skill_commands").scan_skill_commands().items()):
        cat.pairs.append([k, str(info.get("description", "Skill"))])'''
    new = '''    for k, info in sorted(_tools_mod("agent.skill_commands").scan_skill_commands().items()):
        # DEVKIT_SLASH_SUGGEST_V1: commands.catalog is an input suggestion surface, not dispatch.
        if not info.get("slash_suggest", True):
            continue
        cat.pairs.append([k, str(info.get("description", "Skill"))])'''
    text = _replace_once(text, old, new, "tui_gateway.methods_tools")
    path.write_text(text, encoding="utf-8")
    return "patched"


def strict_compile(paths: list[Path]) -> None:
    with tempfile.TemporaryDirectory(prefix="hermes-slash-suggest-compile-") as tmp:
        root = Path(tmp)
        for index, path in enumerate(paths):
            py_compile.compile(str(path), cfile=str(root / f"{index}.pyc"), doraise=True)


def patch_root(root: Path) -> dict[str, str]:
    targets = {
        "skill_commands": root / "agent" / "skill_commands.py",
        "completion": root / "hermes_cli" / "commands_completion.py",
        "catalog": root / "tui_gateway" / "methods_tools.py",
    }
    missing = [str(path) for path in targets.values() if not path.is_file()]
    if missing:
        raise RuntimeError("Hermes slash suggestion patch target missing: " + ", ".join(missing))

    states = {
        "skill_commands": patch_skill_commands(targets["skill_commands"]),
        "completion": patch_completion(targets["completion"]),
        "catalog": patch_catalog(targets["catalog"]),
    }
    strict_compile(list(targets.values()))
    return states


def self_test() -> None:
    with tempfile.TemporaryDirectory(prefix="hermes-slash-suggest-test-") as tmp:
        root = Path(tmp)
        (root / "agent").mkdir()
        (root / "hermes_cli").mkdir()
        (root / "tui_gateway").mkdir()

        (root / "agent" / "skill_commands.py").write_text(
            '''import json\nimport logging\nimport os\nfrom pathlib import Path\nfrom typing import Any\nlogger = logging.getLogger(__name__)\n\ndef fixture(frontmatter, commands, cmd_key, name, description, skill_md):\n    commands[cmd_key] = {"name": name, "description": description or f"Invoke the {name} skill",\n                         "skill_md_path": str(skill_md), "skill_dir": str(skill_md.parent)}\n''', encoding="utf-8")
        (root / "hermes_cli" / "commands_completion.py").write_text(
            '''from typing import Any, Mapping\n\nclass Fixture:\n    def _call_provider(self, provider):\n        return provider()\n    _skill_commands_provider = staticmethod(lambda: {})\n\n    def _iter_skill_commands(self) -> Mapping[str, dict[str, Any]]:\n        return self._call_provider(self._skill_commands_provider)\n''', encoding="utf-8")
        (root / "tui_gateway" / "methods_tools.py").write_text(
            '''class Cat:\n    def __init__(self):\n        self.pairs = []\nclass M:\n    @staticmethod\n    def scan_skill_commands():\n        return {}\ndef _tools_mod(name):\n    return M\n\ndef catalog():\n    cat = Cat()\n    for k, info in sorted(_tools_mod("agent.skill_commands").scan_skill_commands().items()):\n        cat.pairs.append([k, str(info.get("description", "Skill"))])\n    return cat.pairs\n''', encoding="utf-8")

        states = patch_root(root)
        if set(states.values()) != {"patched"}:
            raise RuntimeError(f"self-test: unexpected first patch states: {states}")
        states = patch_root(root)
        if set(states.values()) != {"already-patched"}:
            raise RuntimeError(f"self-test: patch is not idempotent: {states}")

        skill_text = (root / "agent" / "skill_commands.py").read_text(encoding="utf-8")
        completion_text = (root / "hermes_cli" / "commands_completion.py").read_text(encoding="utf-8")
        catalog_text = (root / "tui_gateway" / "methods_tools.py").read_text(encoding="utf-8")
        for needle, haystack in (
            ('hermes_metadata.get("slash_suggest")', skill_text),
            ('HERMES_SLASH_SUGGEST_POLICY', skill_text),
            ('hidden_skills', skill_text),
            ('info.get("slash_suggest", True)', completion_text),
            ('info.get("slash_suggest", True)', catalog_text),
        ):
            if needle not in haystack:
                raise RuntimeError(f"self-test: expected contract missing: {needle}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hermes-root", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test == (args.hermes_root is not None):
        parser.error("provide exactly one of --self-test or --hermes-root")
    return args


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        print("Hermes skill slash suggestion patch self-test passed")
        return

    states = patch_root(args.hermes_root.resolve())
    print("Hermes skill slash suggestion patch " + " ".join(f"{k}={v}" for k, v in states.items()))


if __name__ == "__main__":
    main()
