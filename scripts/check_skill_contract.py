#!/usr/bin/env python3
from __future__ import annotations

import ast
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPO_ROOT / "custom-skills"

REQUIRED_SKILLS = {
    "dev-project-pattern",
    "dev-spring-guidelines",
    "dev-spring-feature",
    "dev-spring-data",
    "dev-spring-test",
    "dev-api-docs",
}

REQUIRED_REFERENCES = {
    ("coder", "dev-api-docs"): {
        "references/spring-openapi-reference.md",
        "references/postman-reference.md",
    },
}


def fail(message: str) -> None:
    raise SystemExit(f"[FAIL] {message}")


def parse_inline_list(value: str) -> list[str]:
    value = value.strip()
    if not (value.startswith("[") and value.endswith("]")):
        return []
    try:
        parsed = ast.literal_eval(value)
    except (ValueError, SyntaxError):
        # YAML bare-word lists such as [dev, coder] are valid but not Python.
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip("'\"") for item in inner.split(",") if item.strip()]
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def parse_frontmatter(text: str, path: Path) -> tuple[dict[str, str], dict[str, list[str]], str]:
    if not text.startswith("---\n"):
        fail(f"missing YAML frontmatter start: {path}")

    end = text.find("\n---\n", 4)
    if end < 0:
        fail(f"missing YAML frontmatter end: {path}")

    frontmatter = text[4:end]
    body = text[end + 5 :].strip()
    if not body:
        fail(f"empty SKILL.md body: {path}")

    scalar: dict[str, str] = {}
    lists: dict[str, list[str]] = {}

    for line in frontmatter.splitlines():
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if match:
            key, value = match.groups()
            if value:
                scalar[key] = value.strip().strip("'\"")
                if value.strip().startswith("["):
                    lists[key] = parse_inline_list(value)
            continue

        nested = re.match(r"^\s+([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if nested:
            key, value = nested.groups()
            if value.strip().startswith("["):
                lists[key] = parse_inline_list(value)

    return scalar, lists, body


def main() -> int:
    if not SKILLS_ROOT.is_dir():
        fail(f"custom skill root not found: {SKILLS_ROOT}")

    discovered: dict[tuple[str, str], Path] = {}
    paths_by_name: dict[str, list[Path]] = defaultdict(list)
    related_by_skill: dict[tuple[str, str], list[str]] = {}

    skill_files = sorted(SKILLS_ROOT.glob("*/*/SKILL.md"))
    if not skill_files:
        fail("no custom SKILL.md files found")

    for skill_file in skill_files:
        text = skill_file.read_text(encoding="utf-8")
        scalar, lists, _body = parse_frontmatter(text, skill_file)

        profile = skill_file.parent.parent.name
        name = scalar.get("name", "").strip()
        description = scalar.get("description", "").strip()
        directory_name = skill_file.parent.name
        key = (profile, name)

        if not name:
            fail(f"frontmatter name is required: {skill_file}")
        if name != directory_name:
            fail(f"skill name/path mismatch: name={name!r} dir={directory_name!r}")
        if key in discovered:
            fail(f"duplicate skill name within profile {profile!r}: {name!r}")
        if not description:
            fail(f"frontmatter description is required: {skill_file}")
        if len(description) > 1024:
            fail(f"description exceeds 1024 chars for {profile}/{name}")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
            fail(f"skill name must be lowercase kebab-case: {name}")

        discovered[key] = skill_file
        paths_by_name[name].append(skill_file)
        related_by_skill[key] = lists.get("related_skills", [])

    missing = sorted(REQUIRED_SKILLS - paths_by_name.keys())
    if missing:
        fail("required capability skills are missing: " + ", ".join(missing))

    for key, refs in REQUIRED_REFERENCES.items():
        skill_file = discovered.get(key)
        if skill_file is None:
            fail(f"required skill missing for reference validation: {key[0]}/{key[1]}")
        skill_dir = skill_file.parent
        for relative in sorted(refs):
            target = skill_dir / relative
            if not target.is_file():
                fail(f"required reference missing for {key[0]}/{key[1]}: {relative}")
            if not target.read_text(encoding="utf-8").strip():
                fail(f"required reference is empty for {key[0]}/{key[1]}: {relative}")

    unresolved: list[str] = []
    for (profile, skill_name), related in sorted(related_by_skill.items()):
        for related_name in related:
            if related_name.startswith("dev-") and related_name not in paths_by_name:
                unresolved.append(f"{profile}/{skill_name} -> {related_name}")

    for item in unresolved:
        print(f"[WARN] related skill is not installed in custom-skills: {item}")

    # Profile isolation is intentional. Same skill name may exist in different
    # external_dirs, such as coder/dev-review-cycle and reviewer/dev-review-cycle.
    cross_profile_duplicates = {
        name: paths for name, paths in paths_by_name.items() if len(paths) > 1
    }
    for name, paths in sorted(cross_profile_duplicates.items()):
        profiles = ", ".join(sorted(path.parent.parent.name for path in paths))
        print(f"[INFO] profile-scoped duplicate skill name allowed: {name} ({profiles})")

    # Hardening invariants for progressive disclosure.
    implement_file = discovered.get(("coder", "dev-implement-plan"))
    breakdown_file = discovered.get(("orchestrator", "dev-breakdown"))
    if implement_file is None or breakdown_file is None:
        fail("workflow entrypoint skills are missing")

    implement_text = implement_file.read_text(encoding="utf-8")
    breakdown_text = breakdown_file.read_text(encoding="utf-8")
    if 'skill_view("dev-project-pattern")' not in breakdown_text:
        fail("dev-breakdown must explicitly load dev-project-pattern via skill_view")
    for capability in (
        "dev-spring-guidelines",
        "dev-spring-feature",
        "dev-spring-data",
        "dev-spring-test",
        "dev-api-docs",
    ):
        if f'skill_view("{capability}")' not in implement_text:
            fail(f"dev-implement-plan must explicitly load {capability} via skill_view")

    print(
        f"[PASS] Custom skill contract: {len(discovered)} profile-scoped skills "
        f"({len(paths_by_name)} unique names) validated"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
