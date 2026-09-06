#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

required_skills = (
    "dev-frontend-feature",
    "dev-typescript-guidelines",
    "dev-frontend-guidelines",
    "dev-nextjs-feature",
    "dev-frontend-test",
    "dev-api-contract",
    "dev-figma-design",
    "dev-ui-ux",
)
for name in required_skills:
    path = ROOT / "custom-skills" / "shared" / name / "SKILL.md"
    if not path.is_file() or not path.read_text(encoding="utf-8").strip():
        raise SystemExit(f"missing frontend shared skill: {name}")

pattern = (ROOT / "custom-skills/orchestrator/dev-project-pattern/SKILL.md").read_text(encoding="utf-8")
breakdown = (ROOT / "custom-skills/orchestrator/dev-breakdown/SKILL.md").read_text(encoding="utf-8")
frontend = (ROOT / "custom-skills/shared/dev-frontend-feature/SKILL.md").read_text(encoding="utf-8")
figma = (ROOT / "custom-skills/shared/dev-figma-design/SKILL.md").read_text(encoding="utf-8")
figma_script = (ROOT / "custom-skills/shared/dev-figma-design/scripts/figma_context.py").read_text(encoding="utf-8")
stack = (ROOT / "shared/references/stack-capability-skill-guide.md").read_text(encoding="utf-8")

checks = {
    "project pattern": (pattern, ("dev-tech-dispatch", "dev-frontend-feature", "Frontend Capability Hints", "Design Status: DRAFT | APPROVED")),
    "breakdown": (breakdown, ("dev-frontend-feature", "FIGMA_DRIVEN", "CODE_DRIVEN", "dev-api-contract", "dev-figma-design")),
    "frontend entry": (frontend, ("canonical entry", "FIGMA_DRIVEN", "CODE_DRIVEN", "dev-ui-ux", "dev-figma-design", "lazy-load")),
    "figma skill": (figma, ("FIGMA_ACCESS_TOKEN", "FIGMA_OAUTH_TOKEN", "file_content:read", "--preview-out", "read-only")),
    "figma provider": (figma_script, ("https://api.figma.com", "X-Figma-Token", "Authorization", "/v1/files/", "/v1/images/", "HERMES_WRITE_SAFE_ROOT", "MAX_DEPTH = 6")),
    "stack guide": (stack, ("dev-frontend-feature", "dev-figma-design", "FIGMA_DRIVEN", "Stack Detection != Skill Loading")),
}
for label, (text, terms) in checks.items():
    missing = [term for term in terms if term not in text]
    if missing:
        raise SystemExit(f"{label} missing terms: {', '.join(missing)}")

if 'method="POST"' in figma_script or 'method="PATCH"' in figma_script or 'method="DELETE"' in figma_script:
    raise SystemExit("Figma adapter must remain read-only")

sample = (ROOT / "sample.env").read_text(encoding="utf-8")
compose = (ROOT / "compose.yml").read_text(encoding="utf-8")
for key in ("FIGMA_ACCESS_TOKEN", "FIGMA_OAUTH_TOKEN"):
    if f"{key}=" not in sample:
        raise SystemExit(f"sample.env missing {key}")
    if f"{key}: ${{{key}:-}}" not in compose:
        raise SystemExit(f"compose.yml missing {key}")

print("[PASS] Frontend/Figma capability contract")
