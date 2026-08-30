#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

SKILL_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
FRONTMATTER_NAME_RE = re.compile(r"^name:\s*['\"]?([^'\"#]+?)['\"]?\s*(?:#.*)?$")
PLATFORMS_RE = re.compile(r"^platforms:\s*(.+?)\s*$")


def parse_inline_list(value: str) -> list[str]:
    value = value.strip()
    if not (value.startswith("[") and value.endswith("]")):
        return []
    try:
        parsed = ast.literal_eval(value)
    except (ValueError, SyntaxError):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip("'\"") for item in inner.split(",") if item.strip()]
    if not isinstance(parsed, list):
        return []
    return [str(item).strip() for item in parsed if str(item).strip()]


def parse_external_dirs(config_path: Path) -> list[Path]:
    if not config_path.is_file():
        raise ValueError(f"profile config not found: {config_path}")

    lines = config_path.read_text(encoding="utf-8").splitlines()
    skills_index: int | None = None
    skills_indent = 0

    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if re.match(r"^skills\s*:\s*(?:#.*)?$", stripped):
            skills_index = index
            skills_indent = indent
            break

    if skills_index is None:
        return []

    external_index: int | None = None
    external_indent = 0
    inline_value = ""

    for index in range(skills_index + 1, len(lines)):
        line = lines[index]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent <= skills_indent:
            break
        match = re.match(r"^external_dirs\s*:\s*(.*?)\s*$", stripped)
        if match:
            external_index = index
            external_indent = indent
            inline_value = match.group(1)
            break

    if external_index is None:
        return []

    if inline_value:
        if not (inline_value.startswith("[") and inline_value.endswith("]")):
            raise ValueError(f"unsupported skills.external_dirs format: {config_path}")
        values = parse_inline_list(inline_value)
        return [Path(value).expanduser() for value in values]

    values: list[Path] = []
    for index in range(external_index + 1, len(lines)):
        line = lines[index]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent <= external_indent:
            break
        match = re.match(r"^-\s+(.+?)\s*$", stripped)
        if not match:
            raise ValueError(f"unsupported skills.external_dirs item: {config_path}:{index + 1}")
        value = match.group(1).strip().strip("'\"")
        if value:
            values.append(Path(value).expanduser())
    return values


def parse_skill_metadata(skill_file: Path) -> tuple[str | None, list[str]]:
    name: str | None = None
    platforms: list[str] = []
    try:
        lines = skill_file.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return None, []

    if not lines or lines[0].strip() != "---":
        return None, []

    for line in lines[1:]:
        if line.strip() == "---":
            break
        stripped = line.strip()
        name_match = FRONTMATTER_NAME_RE.match(stripped)
        if name_match:
            name = name_match.group(1).strip()
            continue
        platforms_match = PLATFORMS_RE.match(stripped)
        if platforms_match:
            platforms = parse_inline_list(platforms_match.group(1))
    return name, platforms


def discover_profile_skills(profile: str, profiles_root: Path) -> set[str]:
    profile_home = profiles_root / profile
    config_path = profile_home / "config.yaml"
    external_dirs = parse_external_dirs(config_path)

    roots = [profile_home / "skills", *external_dirs]
    discovered: set[str] = set()

    for root in roots:
        if not root.is_absolute():
            root = profile_home / root
        if not root.is_dir():
            continue
        for skill_file in root.rglob("SKILL.md"):
            name, platforms = parse_skill_metadata(skill_file)
            if not name or not SKILL_NAME_RE.fullmatch(name):
                continue
            if platforms and "linux" not in platforms:
                continue
            discovered.add(name)

    return discovered


def env_key(profile: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "_", profile).upper()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Kanban pinned skills against installed skills for target Hermes profiles."
    )
    parser.add_argument("--profile", action="append", dest="profiles", required=True)
    parser.add_argument("--skill", action="append", dest="skills", default=[])
    parser.add_argument("--profiles-root", default="/opt/data/profiles")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return exit code 3 when any requested skill is unavailable.",
    )
    args = parser.parse_args()

    profiles = list(dict.fromkeys(profile.strip() for profile in args.profiles if profile.strip()))
    requested = list(dict.fromkeys(skill.strip() for skill in args.skills if skill.strip()))
    invalid_names = [skill for skill in requested if not SKILL_NAME_RE.fullmatch(skill)]

    if not profiles:
        print("ERROR=no target profiles")
        return 2

    available_by_profile: dict[str, set[str]] = {}
    try:
        for profile in profiles:
            available_by_profile[profile] = discover_profile_skills(
                profile, Path(args.profiles_root).expanduser()
            )
    except ValueError as exc:
        print(f"ERROR={exc}")
        return 2

    validated: list[str] = []
    rejected: list[str] = []
    missing_by_profile: dict[str, list[str]] = {profile: [] for profile in profiles}

    for skill in requested:
        missing = [
            profile for profile in profiles if skill not in available_by_profile[profile]
        ]
        if skill in invalid_names or missing:
            rejected.append(skill)
            for profile in missing:
                missing_by_profile[profile].append(skill)
            continue
        validated.append(skill)

    print(f"PROFILES={','.join(profiles)}")
    print(f"REQUESTED_SKILLS={','.join(requested)}")
    print(f"VALIDATED_SKILLS={','.join(validated)}")
    print(f"REJECTED_SKILLS={','.join(rejected)}")
    for profile in profiles:
        print(f"MISSING_{env_key(profile)}={','.join(missing_by_profile[profile])}")
    print("STATUS=pass")

    if args.strict and rejected:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
