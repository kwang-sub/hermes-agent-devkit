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
    "dev-project-pattern", "dev-skill-preflight", "dev-java-guidelines",
    "dev-spring-guidelines", "dev-spring-feature", "dev-spring-data",
    "dev-spring-test", "dev-api-docs",
}

REQUIRED_REFERENCES = {
    ("shared", "dev-api-docs"): {"references/spring-openapi-reference.md", "references/postman-reference.md"},
    ("orchestrator", "dev-workflow-orchestrate"): {"references/dispatch-efficiency.md"},
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
        return [item.strip().strip("'\"") for item in inner.split(",") if item.strip()] if inner else []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def parse_frontmatter(text: str, path: Path) -> tuple[dict[str, str], dict[str, list[str]], str]:
    if not text.startswith("---\n"):
        fail(f"missing YAML frontmatter start: {path}")
    end = text.find("\n---\n", 4)
    if end < 0:
        fail(f"missing YAML frontmatter end: {path}")
    frontmatter = text[4:end]
    body = text[end + 5:].strip()
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
        if nested and nested.group(2).strip().startswith("["):
            lists[nested.group(1)] = parse_inline_list(nested.group(2))
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
        scalar, lists, _ = parse_frontmatter(text, skill_file)
        scope = skill_file.parent.parent.name
        name = scalar.get("name", "").strip()
        description = scalar.get("description", "").strip()
        if not name or name != skill_file.parent.name:
            fail(f"skill name/path mismatch: {skill_file}")
        if (scope, name) in discovered:
            fail(f"duplicate skill name within scope {scope!r}: {name!r}")
        if not description or len(description) > 1024:
            fail(f"invalid description: {skill_file}")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
            fail(f"skill name must be lowercase kebab-case: {name}")
        discovered[(scope, name)] = skill_file
        paths_by_name[name].append(skill_file)
        related_by_skill[(scope, name)] = lists.get("related_skills", [])

    missing = sorted(REQUIRED_SKILLS - paths_by_name.keys())
    if missing:
        fail("required capability skills are missing: " + ", ".join(missing))

    for key, refs in REQUIRED_REFERENCES.items():
        skill_file = discovered.get(key)
        if skill_file is None:
            fail(f"required skill missing for reference validation: {key}")
        for relative in refs:
            target = skill_file.parent / relative
            if not target.is_file() or not target.read_text(encoding="utf-8").strip():
                fail(f"required reference missing/empty for {key}: {relative}")

    for (scope, skill_name), related in sorted(related_by_skill.items()):
        for related_name in related:
            if related_name.startswith("dev-") and related_name not in paths_by_name:
                print(f"[WARN] related skill is not installed in custom-skills: {scope}/{skill_name} -> {related_name}")

    for name, paths in sorted((n, p) for n, p in paths_by_name.items() if len(p) > 1):
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

    require_terms(breakdown_text, "dev-breakdown", ('skill_view("dev-project-pattern")', "dev-java-guidelines"))
    require_terms(dispatch_text, "dev-workspace-dispatch preflight", ('skill_view("dev-skill-preflight")', "VALIDATED_SKILLS", "REJECTED_SKILLS", "kanban_create.skills"))

    require_terms(workflow_text, "dev-workflow-orchestrate dispatch efficiency", (
        "prepare_dispatch.py", "정확히 한 번", "working-tree 전체 scan을 하지 않는다",
        "kanban_create tool 1회", "kanban_show tool 1회", "hermes project list",
        "Kanban body 임시 파일", "dispatch-efficiency.md",
        "skipped-approved-preservation", "change_summary.py --include", "review_context.py --include",
    ))

    require_terms(dispatch_text, "dev-workspace-dispatch fast path", (
        "--confirmed-dirty", "repository-wide dirty/EOL/untracked 분류를 **생략**",
        "WORKSPACE_CHANGE_SCAN_MODE=skipped-approved-preservation", "*_COUNT=-1",
        "git diff --name-only -z HEAD", "WORKSPACE_CLASSIFICATION_TOTAL_SECONDS",
        'initial_status="blocked"', "kanban_show(board=BOARD, task_id=<CREATED_TASK_ID>)",
        "subscribe_notification.py --board BOARD --task-id <CREATED_TASK_ID>",
        "NOTIFY_STATUS=subscribed + NOTIFY_VERIFIED=true",
        "kanban_unblock(board=BOARD, task_id=<CREATED_TASK_ID>)",
        "board == BOARD", "HERMES_KANBAN_BOARD", "CLI body-file 지원 여부 탐색",
        "CLI fallback을 탐색하지 않고 BLOCK",
    ))

    efficiency_text = (workflow_file.parent / "references" / "dispatch-efficiency.md").read_text(encoding="utf-8")
    require_terms(efficiency_text, "dispatch-efficiency reference", (
        "skipped-approved-preservation", "change_summary.py --include", "review_context.py --include",
        "큰 파일을 임의의 MB threshold로 제외하지 않는다", "hermes project --help",
        "CLI body-file capability probing",
    ))

    for capability in ("dev-java-guidelines", "dev-spring-guidelines", "dev-spring-feature", "dev-spring-data", "dev-spring-test", "dev-api-docs"):
        if f'skill_view("{capability}")' not in implement_text:
            fail(f"dev-implement-plan must explicitly load {capability} via skill_view")

    require_terms(implement_text, "dev-implement-plan scoped summary", (
        "scoped change_summary.py", "Standard Flow에서 `--include` 없이", "--allow-full-scan",
        "tracked와 untracked 모두 Git pathspec", "Changed Files",
    ))
    require_terms(reviewer_text, "dev-code-review scoped review", (
        "review_context.py --include", "Standard Flow에서는 `--include`를 반드시 제공",
        "--allow-full-scan", "tracked와 untracked 모두 Git pathspec", "Java Convention Review Gate",
    ))

    print(f"[PASS] Custom skill contract: {len(discovered)} scoped skills ({len(paths_by_name)} unique names) validated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
