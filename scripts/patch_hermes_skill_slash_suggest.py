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
        # In split upstream layouts, BOTH catalog and inline completion must
        # be filtered. A partial patch is not safe to treat as idempotent.
        if path.name == "command_discovery.py" and "raw_skill_commands = get_interactive_skill_commands()" not in text:
            raise RuntimeError("tui_gateway.command_discovery: partial slash suggestion patch")
        return "already-patched"

    # Hermes <= 2026.9.14 kept the skills loop directly in commands.catalog.
    legacy_old = '''    for k, info in sorted(_tools_mod("agent.skill_commands").scan_skill_commands().items()):
        cat.pairs.append([k, str(info.get("description", "Skill"))])'''
    legacy_new = '''    for k, info in sorted(_tools_mod("agent.skill_commands").scan_skill_commands().items()):
        # DEVKIT_SLASH_SUGGEST_V1: commands.catalog is an input suggestion surface, not dispatch.
        if not info.get("slash_suggest", True):
            continue
        cat.pairs.append([k, str(info.get("description", "Skill"))])'''
    if legacy_old in text:
        text = _replace_once(text, legacy_old, legacy_new, "tui_gateway.methods_tools.legacy")
    else:
        # Current Hermes extracted catalog construction into _catalog_skills().
        current_old = '''    for k, info in sorted(sc.scan_skill_commands().items()):
        cat.pairs.append([k, str(info.get("description", "Skill"))])'''
        current_new = '''    for k, info in sorted(sc.scan_skill_commands().items()):
        # DEVKIT_SLASH_SUGGEST_V1: commands.catalog is an input suggestion surface, not dispatch.
        if not info.get("slash_suggest", True):
            continue
        cat.pairs.append([k, str(info.get("description", "Skill"))])'''
        if current_old in text:
            text = _replace_once(text, current_old, current_new, "tui_gateway.methods_tools.current")
        else:
            # Newer Hermes uses get_interactive_skill_commands() and maintains
            # usage/origin metadata alongside every catalog pair.
            translated_old = '''    for k, info in sorted(sc.get_interactive_skill_commands().items()):
        cat.pairs.append([k, str(info.get("description", "Skill"))])
        name = str(info.get("name") or k.lstrip("/"))'''
            translated_new = '''    for k, info in sorted(sc.get_interactive_skill_commands().items()):
        # DEVKIT_SLASH_SUGGEST_V1: hide suggestions without affecting dispatch.
        if not info.get("slash_suggest", True):
            continue
        cat.pairs.append([k, str(info.get("description", "Skill"))])
        name = str(info.get("name") or k.lstrip("/"))'''
            text = _replace_once(text, translated_old, translated_new,
                                 "tui_gateway.command_discovery.catalog" if path.name == "command_discovery.py"
                                 else "tui_gateway.methods_tools.interactive")

    if path.name == "command_discovery.py":
        # Since October 2026, both commands.catalog and complete.slash live
        # in this shared module. Only alter the suggestion-facing projection;
        # get_interactive_skill_commands() itself must remain unfiltered so
        # explicit /skill dispatch still finds internal skills.
        completion_old = '''        skill_commands, skill_bundles = dict(get_interactive_skill_commands()), dict(get_skill_bundles())'''
        completion_new = '''        # DEVKIT_SLASH_SUGGEST_V1: hide internal suggestions, not executable slash skills.
        raw_skill_commands = get_interactive_skill_commands()
        skill_commands = {key: info for key, info in raw_skill_commands.items()
                          if info.get("slash_suggest", True)}
        skill_bundles = dict(get_skill_bundles())'''
        text = _replace_once(text, completion_old, completion_new,
                             "tui_gateway.command_discovery.inline_completion")

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

    # Keep the legacy/current in-file catalog patch. Newer Hermes delegates
    # commands.catalog to command_discovery; patch that module instead.
    methods_source = targets["catalog"].read_text(encoding="utf-8")
    if "from tui_gateway.command_discovery import command_catalog" in methods_source:
        discovery = root / "tui_gateway" / "command_discovery.py"
        if not discovery.is_file():
            raise RuntimeError("Hermes command catalog delegate missing: tui_gateway/command_discovery.py")
        targets["catalog"] = discovery

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

        # Current Hermes extracted the catalog skill loop into _catalog_skills().
        # Use a fresh fixture file because MARKER is intentionally file-wide:
        # once the legacy fixture is patched, patch_catalog() must be idempotent
        # and return already-patched rather than attempting a second layout.
        current_catalog_path = root / "tui_gateway" / "methods_tools_current.py"
        current_catalog_path.write_text(
            '''class Cat:\n    def __init__(self):\n        self.pairs = []\nclass M:\n    @staticmethod\n    def scan_skill_commands():\n        return {}\ndef _tools_mod(name):\n    return M\n\ndef _catalog_skills(cat, skills):\n    sc = _tools_mod("agent.skill_commands")\n    for k, info in sorted(sc.scan_skill_commands().items()):\n        cat.pairs.append([k, str(info.get("description", "Skill"))])\n''',
            encoding="utf-8",
        )
        state = patch_catalog(current_catalog_path)
        if state != "patched":
            raise RuntimeError(f"self-test: current Hermes catalog shape was not patched: {state}")
        if patch_catalog(current_catalog_path) != "already-patched":
            raise RuntimeError("self-test: current Hermes catalog patch is not idempotent")
        current_catalog = current_catalog_path.read_text(encoding="utf-8")
        if 'info.get("slash_suggest", True)' not in current_catalog:
            raise RuntimeError("self-test: current Hermes catalog slash_suggest guard missing")

        interactive_catalog_path = root / "tui_gateway" / "methods_tools_interactive.py"
        interactive_catalog_path.write_text(
            '''def _catalog_skills(cat, skills):\n    sc = _tools_mod("agent.skill_commands")\n    for k, info in sorted(sc.get_interactive_skill_commands().items()):\n        cat.pairs.append([k, str(info.get("description", "Skill"))])\n        name = str(info.get("name") or k.lstrip("/"))\n        skills[k] = {"usage": usage(name), "origin": origin_of(name)}\n''',
            encoding="utf-8",
        )
        if patch_catalog(interactive_catalog_path) != "patched":
            raise RuntimeError("self-test: interactive catalog was not patched")
        if patch_catalog(interactive_catalog_path) != "already-patched":
            raise RuntimeError("self-test: interactive catalog patch not idempotent")
        if 'if not info.get("slash_suggest", True):' not in interactive_catalog_path.read_text(encoding="utf-8"):
            raise RuntimeError("self-test: interactive catalog visibility filter missing")

        # Hermes >= 2026-10-14 extracted catalog and completion into
        # tui_gateway.command_discovery; preserve direct dispatch via the
        # untouched get_interactive_skill_commands() registry.
        methods_path = root / "tui_gateway" / "methods_tools.py"
        methods_path.write_text(
            '''def catalog():
    from tui_gateway.command_discovery import command_catalog
    return command_catalog()
''', encoding="utf-8")
        discovery_path = root / "tui_gateway" / "command_discovery.py"
        discovery_path.write_text(
            '''import contextlib

def _catalog_skills(cat, skills, module_loader):
    sc = module_loader("agent.skill_commands")
    for k, info in sorted(sc.get_interactive_skill_commands().items()):
        cat.pairs.append([k, str(info.get("description", "Skill"))])
        name = str(info.get("name") or k.lstrip("/"))
        skills[k] = {"usage": 0, "origin": "local"}
    return ""

def slash_completions(get_interactive_skill_commands, get_skill_bundles):
    with contextlib.nullcontext():
        skill_commands, skill_bundles = dict(get_interactive_skill_commands()), dict(get_skill_bundles())
    return skill_commands
''', encoding="utf-8")
        states = patch_root(root)
        if states != {"skill_commands": "already-patched",
                      "completion": "already-patched", "catalog": "patched"}:
            raise RuntimeError(f"self-test: split catalog not selected: {states}")
        if patch_root(root) != {key: "already-patched" for key in states}:
            raise RuntimeError("self-test: split command discovery patch not idempotent")
        if MARKER in methods_path.read_text(encoding="utf-8"):
            raise RuntimeError("self-test: delegated methods_tools must remain unchanged")

        # Exercise BOTH actual suggestion projections using visible/hidden/
        # unspecified skills. The source registry must remain executable.
        entries = {
            "/visible": {"name": "visible", "description": "Public", "slash_suggest": True},
            "/internal": {"name": "internal", "description": "Internal", "slash_suggest": False},
            "/plugin:other": {"name": "other", "description": "Plugin"},
        }
        class SkillSource:
            @staticmethod
            def get_interactive_skill_commands():
                return entries

        namespace: dict = {}
        exec(compile(discovery_path.read_text(encoding="utf-8"),
                     str(discovery_path), "exec"), namespace)
        class Catalog:
            def __init__(self):
                self.pairs = []

        catalog = Catalog()
        catalog_skills = {}
        namespace["_catalog_skills"](catalog, catalog_skills, lambda _: SkillSource)
        if {key for key, _ in catalog.pairs} != {"/visible", "/plugin:other"}:
            raise RuntimeError("self-test: split catalog leaked hidden slash skill")
        if set(catalog_skills) != {"/visible", "/plugin:other"}:
            raise RuntimeError("self-test: split catalog metadata leaked hidden skill")
        inline = namespace["slash_completions"](SkillSource.get_interactive_skill_commands,
                                                 lambda: {})
        if set(inline) != {"/visible", "/plugin:other"} or "/internal" not in entries:
            raise RuntimeError("self-test: inline completion or explicit skill registry changed")

        # Unknown future layouts must fail explicitly rather than silently
        # exposing internal skills in suggestion surfaces.
        bad_discovery = discovery_path.read_text(encoding="utf-8")
        discovery_path.write_text("def command_catalog():\n    return {}\n", encoding="utf-8")
        try:
            patch_root(root)
        except RuntimeError as exc:
            if "expected exactly one patch anchor" not in str(exc):
                raise
        else:
            raise RuntimeError("self-test: unknown discovery layout was silently accepted")
        discovery_path.write_text(bad_discovery, encoding="utf-8")

        skill_text = (root / "agent" / "skill_commands.py").read_text(encoding="utf-8")
        completion_text = (root / "hermes_cli" / "commands_completion.py").read_text(encoding="utf-8")
        # The split catalog owns the suggestion filter; methods_tools is now
        # only a dispatcher and deliberately remains unchanged by this patch.
        catalog_text = discovery_path.read_text(encoding="utf-8")
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
