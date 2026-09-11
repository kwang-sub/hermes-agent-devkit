#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

required_skills = (
    "dev-frontend-feature", "dev-typescript-guidelines", "dev-frontend-guidelines",
    "dev-nextjs-feature", "dev-frontend-test", "dev-api-contract", "dev-figma-design", "dev-ui-ux",
)
for name in required_skills:
    path = ROOT / "custom-skills" / "shared" / name / "SKILL.md"
    if not path.is_file() or not path.read_text(encoding="utf-8").strip():
        raise SystemExit(f"missing frontend shared skill: {name}")

pattern = (ROOT / "custom-skills/orchestrator/dev-project-pattern/SKILL.md").read_text(encoding="utf-8")
breakdown = (ROOT / "custom-skills/orchestrator/dev-breakdown/SKILL.md").read_text(encoding="utf-8")
frontend = (ROOT / "custom-skills/shared/dev-frontend-feature/SKILL.md").read_text(encoding="utf-8")
typescript = (ROOT / "custom-skills/shared/dev-typescript-guidelines/SKILL.md").read_text(encoding="utf-8")
typescript_reference_path = ROOT / "custom-skills/shared/dev-typescript-guidelines/references/official-typescript-practices.md"
if not typescript_reference_path.is_file():
    raise SystemExit("TypeScript official practice reference is missing")
typescript_reference = typescript_reference_path.read_text(encoding="utf-8")
react = (ROOT / "custom-skills/shared/dev-frontend-guidelines/SKILL.md").read_text(encoding="utf-8")
react_reference_path = ROOT / "custom-skills/shared/dev-frontend-guidelines/references/official-react-practices.md"
if not react_reference_path.is_file():
    raise SystemExit("React official practice reference is missing")
react_reference = react_reference_path.read_text(encoding="utf-8")
nextjs = (ROOT / "custom-skills/shared/dev-nextjs-feature/SKILL.md").read_text(encoding="utf-8")
nextjs_reference_path = ROOT / "custom-skills/shared/dev-nextjs-feature/references/official-nextjs-practices.md"
if not nextjs_reference_path.is_file():
    raise SystemExit("Next.js official practice reference is missing")
nextjs_reference = nextjs_reference_path.read_text(encoding="utf-8")
figma = (ROOT / "custom-skills/shared/dev-figma-design/SKILL.md").read_text(encoding="utf-8")
figma_script = (ROOT / "custom-skills/shared/dev-figma-design/scripts/figma_context.py").read_text(encoding="utf-8")
stack = (ROOT / "shared/references/stack-capability-skill-guide.md").read_text(encoding="utf-8")

checks = {
    "project pattern": (pattern, ("dev-tech-dispatch", "dev-frontend-feature", "Frontend Capability Hints", "Design Status: DRAFT | APPROVED")),
    "breakdown": (breakdown, ("dev-frontend-feature", "FIGMA_DRIVEN", "CODE_DRIVEN", "dev-api-contract", "dev-figma-design")),
    "frontend entry": (frontend, ("canonical entry", "FIGMA_DRIVEN", "CODE_DRIVEN", "dev-ui-ux", "dev-figma-design", "lazy-load", "dev-typescript-guidelines", "dev-frontend-guidelines", "dev-nextjs-feature")),
    "typescript skill": (typescript, (
        "version: 0.3.0", "Version Gate", "TypeScript 7 Gate", "Strictness Gate", "useUnknownInCatchVariables",
        "noUncheckedSideEffectImports", "Type Design Performance", "Build Performance", "Incremental",
        "Project References", "TypeScript 7 Parallelism", "skipLibCheck", "Performance Investigation", "Review Hotspots",
    )),
    "typescript reference": (typescript_reference, (
        "TypeScript Official Practices", "Version Gate: 5.x / 6.x / 7.x", "TypeScript 7.0 Native Compiler",
        "TypeScript 7.0 Default / Migration Gate", "Additional Safety Options", "Easy-to-Compile Type Design",
        "Build Performance: Incremental", "Build Performance: Project References", "TypeScript 7 Parallel Build Controls",
        "Performance Investigation Before Refactoring", "Project References", "Microsoft TypeScript Wiki: Performance",
    )),
    "react skill": (react, (
        "version: 0.3.0", "Rules of Hooks / `use` 예외", "State Ownership", "`useEffectEvent` (React 19.2+)",
        "Measurement First", "React Compiler 1.0+", "Compiler-aware ESLint", "Transition / Deferred Rendering",
        "`<Activity>` (React 19.2+)", "Performance Evidence", "Review Hotspots",
    )),
    "react reference": (react_reference, (
        "React Official Practices", "Version Gate: React 17/18 / 19 / 19.2+", "Rules of Hooks and the `use` Exception",
        "useEffectEvent", "Measure First: React DevTools / Profiler / Performance Tracks", "React Compiler 1.0+",
        "Compiler-aware ESLint", "Transitions: `useTransition` / `startTransition`", "`useDeferredValue`",
        "`<Activity>` (React 19.2+)", "Primary Official Sources",
    )),
    "nextjs skill": (nextjs, (
        "version: 0.2.0", "Version / Request API Gate", "Server / Client Boundary", "Cache / Revalidation",
        "Mutation / Server Action", "Route Handler / API Boundary", "Proxy / Middleware",
        "React Compiler / Turbopack", "Environment / Secrets", "Review Hotspots",
    )),
    "nextjs reference": (nextjs_reference, (
        "Next.js Official Practices", "Version and Router Gate", "Server and Client Components",
        "Request APIs and Version Differences", "Caching and Revalidation", "Mutations and Server Actions",
        "Proxy / Middleware", "React Compiler and Turbopack", "Primary Official Sources",
    )),
    "figma skill": (figma, ("FIGMA_ACCESS_TOKEN", "FIGMA_OAUTH_TOKEN", "file_content:read", "--preview-out", "read-only")),
    "figma provider": (figma_script, ("https://api.figma.com", "X-Figma-Token", "Authorization", "/v1/files/", "/v1/images/", "HERMES_WRITE_SAFE_ROOT", "MAX_DEPTH = 6")),
    "stack guide": (stack, ("dev-frontend-feature", "dev-typescript-guidelines", "dev-frontend-guidelines", "dev-nextjs-feature", "dev-figma-design", "FIGMA_DRIVEN", "Stack Detection != Skill Loading")),
}
for label, (text, terms) in checks.items():
    missing = [term for term in terms if term not in text]
    if missing:
        raise SystemExit(f"{label} missing terms: {', '.join(missing)}")

if any(term in figma_script for term in ('method="POST"', 'method="PATCH"', 'method="DELETE"')):
    raise SystemExit("Figma adapter must remain read-only")

sample_values = {}
for raw in (ROOT / "sample.env").read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    sample_values[key] = value
compose = (ROOT / "compose.yml").read_text(encoding="utf-8")
for key in ("FIGMA_ACCESS_TOKEN", "FIGMA_OAUTH_TOKEN"):
    if key not in sample_values:
        raise SystemExit(f"sample.env missing {key}")
    if sample_values[key]:
        raise SystemExit(f"sample.env {key} must stay blank")
    if f"{key}: ${{{key}:-}}" not in compose:
        raise SystemExit(f"compose.yml missing {key}")

print("[PASS] Frontend/React19.2/Compiler/TypeScript7/Next.js/Figma capability contract")
