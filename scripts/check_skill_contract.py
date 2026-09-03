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
    "dev-skill-preflight",
    "dev-java-guidelines",
    "dev-spring-guidelines",
    "dev-spring-feature",
    "dev-spring-data",
    "dev-spring-test",
    "dev-api-docs",
}

REQUIRED_REFERENCES = {
    ("shared", "dev-api-docs"): {
        "references/spring-openapi-reference.md",
        "references/postman-reference.md",
    },
    ("orchestrator", "dev-workflow-orchestrate"): {
        "references/dispatch-efficiency.md",
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


def require_terms(text: str, label: str, terms: tuple[str, ...]) -> None:
    missing = [term for term in terms if term not in text]
    if missing:
        fail(f"{label} missing required contract terms: " + ", ".join(missing))


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
        scope = skill_file.parent.parent.name
        name = scalar.get("name", "").strip()
        description = scalar.get("description", "").strip()
        directory_name = skill_file.parent.name
        key = (scope, name)

        if not name:
            fail(f"frontmatter name is required: {skill_file}")
        if name != directory_name:
            fail(f"skill name/path mismatch: name={name!r} dir={directory_name!r}")
        if key in discovered:
            fail(f"duplicate skill name within scope {scope!r}: {name!r}")
        if not description:
            fail(f"frontmatter description is required: {skill_file}")
        if len(description) > 1024:
            fail(f"description exceeds 1024 chars for {scope}/{name}")
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
    for (scope, skill_name), related in sorted(related_by_skill.items()):
        for related_name in related:
            if related_name.startswith("dev-") and related_name not in paths_by_name:
                unresolved.append(f"{scope}/{skill_name} -> {related_name}")
    for item in unresolved:
        print(f"[WARN] related skill is not installed in custom-skills: {item}")

    for name, paths in sorted({name: paths for name, paths in paths_by_name.items() if len(paths) > 1}.items()):
        scopes = ", ".join(sorted(path.parent.parent.name for path in paths))
        print(f"[INFO] scope-scoped duplicate skill name allowed: {name} ({scopes})")

    implement_file = discovered.get(("coder", "dev-implement-plan"))
    breakdown_file = discovered.get(("orchestrator", "dev-breakdown"))
    dispatch_file = discovered.get(("orchestrator", "dev-workspace-dispatch"))
    preflight_file = discovered.get(("orchestrator", "dev-skill-preflight"))
    workflow_file = discovered.get(("orchestrator", "dev-workflow-orchestrate"))
    reviewer_file = discovered.get(("reviewer", "dev-code-review"))
    if None in (implement_file, breakdown_file, dispatch_file, preflight_file, workflow_file, reviewer_file):
        fail("workflow entrypoint skills are missing")

    implement_text = implement_file.read_text(encoding="utf-8")
    breakdown_text = breakdown_file.read_text(encoding="utf-8")
    dispatch_text = dispatch_file.read_text(encoding="utf-8")
    preflight_text = preflight_file.read_text(encoding="utf-8")
    workflow_text = workflow_file.read_text(encoding="utf-8")
    reviewer_text = reviewer_file.read_text(encoding="utf-8")

    if 'skill_view("dev-project-pattern")' not in breakdown_text:
        fail("dev-breakdown must explicitly load dev-project-pattern via skill_view")
    if 'skill_view("dev-skill-preflight")' not in dispatch_text:
        fail("dev-workspace-dispatch must explicitly load dev-skill-preflight via skill_view")
    for term in ("VALIDATED_SKILLS", "REJECTED_SKILLS", "kanban_create.skills"):
        if term not in preflight_text or term not in dispatch_text:
            fail(f"skill preflight dispatch contract missing term: {term}")

    require_terms(
        workflow_text,
        "dev-workflow-orchestrate dispatch efficiency",
        (
            "prepare_dispatch.py",
            "정확히 한 번",
            "working-tree 전체 scan을 하지 않는다",
            "kanban_create tool 1회",
            "kanban_show tool 1회",
            "hermes project list",
            "Kanban body 임시 파일",
            "dispatch-efficiency.md",
        ),
    )
    require_terms(
        dispatch_text,
        "dev-workspace-dispatch single path",
        (
            "prepare_dispatch.py",
            "정확히 한 번만 수행",
            "git diff --name-only -z HEAD",
            "WORKSPACE_CLASSIFICATION_TOTAL_SECONDS",
            "kanban_create tool 정확히 1회",
            "kanban_show tool 정확히 1회",
            "CLI body-file 지원 여부 탐색",
            "CLI fallback을 탐색하지 않고 BLOCK",
        ),
    )

    efficiency = workflow_file.parent / "references" / "dispatch-efficiency.md"
    efficiency_text = efficiency.read_text(encoding="utf-8")
    require_terms(
        efficiency_text,
        "dispatch-efficiency reference",
        (
            "prepare_dispatch.py",
            "정확히 한 번",
            "git status",
            "inline Python tracked/effective/EOL 분류",
            "kanban_create",
            "kanban_show",
            "hermes project --help",
            "CLI body-file capability probing",
        ),
    )

    for capability in (
        "dev-java-guidelines",
        "dev-spring-guidelines",
        "dev-spring-feature",
        "dev-spring-data",
        "dev-spring-test",
        "dev-api-docs",
    ):
        if f'skill_view("{capability}")' not in implement_text:
            fail(f"dev-implement-plan must explicitly load {capability} via skill_view")

    require_terms(
        breakdown_text,
        "dev-breakdown Java capability",
        ("dev-java-guidelines", "legacy 이름인 `java-project-conventions`는 사용하지 않고"),
    )
    require_terms(
        reviewer_text,
        "dev-code-review Java capability",
        ('skill_view("dev-java-guidelines")', "Java Convention Review Gate"),
    )

    print(
        f"[PASS] Custom skill contract: {len(discovered)} scoped skills "
        f"({len(paths_by_name)} unique names) validated"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
