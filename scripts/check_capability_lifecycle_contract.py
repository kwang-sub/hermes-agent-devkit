#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "custom-skills/shared/capability-lifecycle.json"
SHARED = ROOT / "custom-skills/shared"
BREAKDOWN = ROOT / "custom-skills/orchestrator/dev-breakdown/SKILL.md"
IMPLEMENT = ROOT / "custom-skills/coder/dev-implement-plan/SKILL.md"
REVIEW = ROOT / "custom-skills/reviewer/dev-code-review/SKILL.md"
DISPATCH = ROOT / "custom-skills/orchestrator/dev-workspace-dispatch/SKILL.md"
PREFLIGHT = ROOT / "custom-skills/orchestrator/dev-skill-preflight/SKILL.md"
INIT_PROFILES = ROOT / "init-profiles.ps1"

# `canonical entry로`, `canonical runtime entry다`처럼 한국어 조사가 바로 붙을 수 있다.
# 영문 식별자 일부(`entrypoint`)는 오탐하지 않도록 ASCII 식별자만 후행 금지한다.
CANONICAL_MARKER = re.compile(
    r"\bcanonical(?:\s+runtime)?\s+entry(?![A-Za-z0-9_-])",
    re.IGNORECASE,
)
VALID_KINDS = {
    "canonical_entry",
    "domain_entry",
    "contract_entry",
    "critical_companion",
    "cross_stack_companion",
}


def read(path: Path) -> str:
    if not path.is_file():
        raise SystemExit(f"missing required lifecycle file: {path}")
    return path.read_text(encoding="utf-8-sig")


def frontmatter_description(text: str) -> str:
    """Return only the SKILL frontmatter description used for canonical discovery.

    Body text can mention another capability as a "canonical entry" and must not
    cause that support skill itself to be registered as a canonical entry.
    """
    match = re.match(r"\A---\s*\n(?P<body>.*?)\n---\s*(?:\n|\Z)", text, flags=re.DOTALL)
    if not match:
        return ""
    description = re.search(
        r"(?m)^description:\s*(?P<value>.+?)\s*$",
        match.group("body"),
    )
    return description.group("value").strip() if description else ""


def declares_canonical_entry(text: str) -> bool:
    return bool(CANONICAL_MARKER.search(frontmatter_description(text)))


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> int:
    try:
        payload = json.loads(read(REGISTRY))
    except json.JSONDecodeError as exc:
        fail(f"invalid capability lifecycle registry JSON: {exc}")

    if payload.get("version") != 1:
        fail("capability lifecycle registry version must be 1")

    capabilities = payload.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        fail("capability lifecycle registry must contain non-empty capabilities")

    planner = read(BREAKDOWN)
    coder = read(IMPLEMENT)
    reviewer = read(REVIEW)
    dispatch = read(DISPATCH)
    preflight = read(PREFLIGHT)
    init_profiles = read(INIT_PROFILES)

    names: list[str] = []
    for entry in capabilities:
        if not isinstance(entry, dict):
            fail("capability lifecycle entry must be an object")
        name = str(entry.get("name") or "").strip()
        if not re.fullmatch(r"dev-[a-z0-9-]+", name):
            fail(f"invalid capability lifecycle name: {name!r}")
        if name in names:
            fail(f"duplicate capability lifecycle name: {name}")
        names.append(name)

        kind = entry.get("kind")
        if kind not in VALID_KINDS:
            fail(f"{name}: unsupported lifecycle kind: {kind}")

        for flag in ("planner_required", "coder_required", "reviewer_required", "strict_pin"):
            if not isinstance(entry.get(flag), bool):
                fail(f"{name}: {flag} must be boolean")

        skill_path = SHARED / name / "SKILL.md"
        skill_text = read(skill_path)

        if entry["kind"] == "canonical_entry" and not declares_canonical_entry(skill_text):
            fail(
                f"{name}: canonical_entry must declare canonical entry "
                "in SKILL.md frontmatter description"
            )

        if entry["planner_required"] and name not in planner:
            fail(f"{name}: planner routing missing from dev-breakdown")

        # A capability is Coder-connected either through dev-implement-plan lazy-load
        # or through Standard Dispatch pinning/preflight contract.
        if entry["coder_required"] and name not in coder and name not in dispatch:
            fail(f"{name}: coder routing/pinning missing from implement-plan and dispatch")

        if entry["reviewer_required"] and name not in reviewer:
            fail(f"{name}: reviewer mapping missing from dev-code-review")

        if entry["strict_pin"] and not skill_path.is_file():
            fail(f"{name}: strict pinned capability must live in shared skill root")

    # New shared skills that explicitly declare themselves canonical in their
    # frontmatter description must be registered. Body references do not count.
    registered = set(names)
    discovered: set[str] = set()
    for skill_path in sorted(SHARED.glob("dev-*/SKILL.md")):
        skill_text = read(skill_path)
        if declares_canonical_entry(skill_text):
            discovered.add(skill_path.parent.name)
    missing_registry = sorted(discovered - registered)
    if missing_registry:
        fail(
            "canonical shared capabilities missing capability-lifecycle.json registration: "
            + ", ".join(missing_registry)
        )

    preflight_terms = (
        "capability-lifecycle.json",
        "strict_pin=true",
        "--strict",
        "coder",
        "reviewer",
        "dispatch BLOCK",
    )
    missing_preflight = [term for term in preflight_terms if term not in preflight]
    if missing_preflight:
        fail("dev-skill-preflight missing lifecycle strict gate terms: " + ", ".join(missing_preflight))

    dispatch_terms = (
        'skill_view("dev-skill-preflight")',
        "VALIDATED_SKILLS",
        "REJECTED_SKILLS",
        "kanban_create.skills",
    )
    missing_dispatch = [term for term in dispatch_terms if term not in dispatch]
    if missing_dispatch:
        fail("dev-workspace-dispatch missing preflight handoff terms: " + ", ".join(missing_dispatch))

    reviewer_terms = (
        "capability-lifecycle.json",
        "Capability Lifecycle Review Gate",
        "strict_pin=true",
        "dev-infrastructure",
        "dev-data-feature",
        "dev-frontend-feature",
        "dev-api-spec",
    )
    missing_reviewer = [term for term in reviewer_terms if term not in reviewer]
    if missing_reviewer:
        fail("dev-code-review missing lifecycle review terms: " + ", ".join(missing_reviewer))

    mount_terms = (
        '$ContainerSharedSkillsPath',
        'coder = @(',
        'reviewer = @(',
    )
    missing_mount = [term for term in mount_terms if term not in init_profiles]
    if missing_mount:
        fail("init-profiles missing shared capability mount terms: " + ", ".join(missing_mount))

    print(
        "PASS: capability lifecycle contract "
        f"({len(capabilities)} registered, {len(discovered)} canonical shared entries discovered)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
