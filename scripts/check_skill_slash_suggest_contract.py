#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "shared/references/skill-slash-suggest-policy.json"
PATCH = ROOT / "scripts/patch_hermes_skill_slash_suggest.py"
DOCKERFILE = ROOT / "Dockerfile"

PUBLIC_ENTRY_SKILLS = {
    "dev-direct-flow",
    "dev-fast-flow",
    "dev-project-bootstrap",
    "dev-workflow-orchestrate",
    "dev-api-spec",
    "dev-api-docs",
    "dev-data-feature",
    "dev-frontend-feature",
    "dev-spring-feature",
    "dev-spring-refactor",
}

REQUIRED_INTERNAL = {
    "dev-implement-plan",
    "dev-breakdown",
    "dev-project-pattern",
    "dev-project-resolve",
    "dev-skill-preflight",
    "dev-tech-dispatch",
    "dev-workspace-dispatch",
    "dev-code-review",
    "dev-api-contract",
    "dev-data-modeling",
    "dev-db-schema",
    "dev-db-query",
    "dev-db-migration",
    "dev-db-performance",
    "dev-design-reference",
    "dev-figma-design",
    "dev-frontend-guidelines",
    "dev-frontend-test",
    "dev-nextjs-feature",
    "dev-spring-data",
    "dev-spring-test",
    "dev-typescript-guidelines",
    "dev-ui-ux",
}


def skill_names() -> set[str]:
    names: set[str] = set()
    for skill_md in (ROOT / "custom-skills").rglob("SKILL.md"):
        text = skill_md.read_text(encoding="utf-8")
        for line in text.splitlines()[:20]:
            if line.startswith("name:"):
                names.add(line.split(":", 1)[1].strip())
                break
    return names


def main() -> int:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    hidden = set(policy.get("hidden_skills") or [])
    existing = skill_names()

    missing_internal = sorted(REQUIRED_INTERNAL - hidden)
    if missing_internal:
        raise SystemExit("internal slash policy missing: " + ", ".join(missing_internal))

    accidentally_hidden_public = sorted(PUBLIC_ENTRY_SKILLS & hidden)
    if accidentally_hidden_public:
        raise SystemExit("public entry skills hidden from slash suggestions: " + ", ".join(accidentally_hidden_public))

    unknown = sorted(hidden - existing)
    if unknown:
        raise SystemExit("slash policy references missing skills: " + ", ".join(unknown))

    patch = PATCH.read_text(encoding="utf-8")
    for term in (
        "DEVKIT_SLASH_SUGGEST_V1",
        "metadata.hermes.slash_suggest",
        "HERMES_SLASH_SUGGEST_POLICY",
        "hidden_skills",
        'info.get("slash_suggest", True)',
    ):
        if term not in patch:
            raise SystemExit(f"slash suggestion patch missing contract term: {term}")

    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    for term in (
        "patch_hermes_skill_slash_suggest.py --self-test",
        "patch_hermes_skill_slash_suggest.py --hermes-root /opt/hermes",
        "DEVKIT_SLASH_SUGGEST_V1",
    ):
        if term not in dockerfile:
            raise SystemExit(f"Dockerfile missing slash suggestion integration: {term}")

    print(
        f"[PASS] Slash suggestion policy: public={len(PUBLIC_ENTRY_SKILLS)} "
        f"hidden={len(hidden)}; runtime/direct dispatch remains outside the filter contract"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
