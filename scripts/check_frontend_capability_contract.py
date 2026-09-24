#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

required_skills = (
    "dev-frontend-feature", "dev-design-reference", "dev-official-docs-context", "dev-typescript-guidelines", "dev-frontend-guidelines",
    "dev-nextjs-feature", "dev-frontend-test", "dev-node-dependencies", "dev-api-contract", "dev-figma-design", "dev-ui-ux",
)
for name in required_skills:
    path = ROOT / "custom-skills" / "shared" / name / "SKILL.md"
    if not path.is_file() or not path.read_text(encoding="utf-8").strip():
        raise SystemExit(f"missing frontend shared skill: {name}")

pattern = (ROOT / "custom-skills/orchestrator/dev-project-pattern/SKILL.md").read_text(encoding="utf-8")
breakdown = (ROOT / "custom-skills/orchestrator/dev-breakdown/SKILL.md").read_text(encoding="utf-8")
coder = (ROOT / "custom-skills/coder/dev-implement-plan/SKILL.md").read_text(encoding="utf-8")
frontend = (ROOT / "custom-skills/shared/dev-frontend-feature/SKILL.md").read_text(encoding="utf-8")
official_docs = (ROOT / "custom-skills/shared/dev-official-docs-context/SKILL.md").read_text(encoding="utf-8")
node_dependencies = (ROOT / "custom-skills/shared/dev-node-dependencies/SKILL.md").read_text(encoding="utf-8")
node_preflight = (ROOT / "custom-skills/shared/dev-node-dependencies/scripts/node_dependency_preflight.py").read_text(encoding="utf-8")
node_environment_gate_path = ROOT / "custom-skills/shared/dev-node-dependencies/scripts/node_environment_gate.py"
if not node_environment_gate_path.is_file():
    raise SystemExit("Node frontend environment gate is missing")
node_environment_gate = node_environment_gate_path.read_text(encoding="utf-8")
tirith_preflight = (ROOT / "custom-skills/shared/dev-node-dependencies/scripts/tirith_package_preflight.py").read_text(encoding="utf-8")
node_runtime_path = ROOT / "custom-skills/shared/dev-node-dependencies/scripts/node_runtime.py"
node_workspace_path = ROOT / "custom-skills/shared/dev-node-dependencies/scripts/node_workspace.py"
if not node_runtime_path.is_file() or not node_workspace_path.is_file():
    raise SystemExit("Node runtime/workspace isolation helper is missing")
node_runtime = node_runtime_path.read_text(encoding="utf-8")
node_workspace = node_workspace_path.read_text(encoding="utf-8")
design = (ROOT / "custom-skills/shared/dev-design-reference/SKILL.md").read_text(encoding="utf-8")
design_template_path = ROOT / "custom-skills/shared/dev-design-reference/references/screen-spec-template.md"
design_guard_path = ROOT / "custom-skills/shared/dev-design-reference/scripts/screen_spec_guard.py"
if not design_template_path.is_file() or not design_guard_path.is_file():
    raise SystemExit("Design Reference template/guard is missing")
design_template = design_template_path.read_text(encoding="utf-8")
design_guard = design_guard_path.read_text(encoding="utf-8")
frontend_test = (ROOT / "custom-skills/shared/dev-frontend-test/SKILL.md").read_text(encoding="utf-8")
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
    "project pattern": (pattern, (
        "dev-tech-dispatch", "dev-frontend-feature", "dev-design-reference", "Frontend Capability Hints",
        "Frontend Mode: REFERENCE_DRIVEN | CODE_DRIVEN", "Design Source: IMAGE | FIGMA | EXISTING_CODE",
        "Frontend View Architecture Pattern", "Frontend Package Convention", "Existing View Strategy Evidence",
        "Shared Data/State Convention", "Responsive / Breakpoint Source",
        "docs/ui/screens/<screen>/", "Storybook / Visual Test Pattern",
    )),
    "breakdown": (breakdown, (
        "dev-frontend-feature", "REFERENCE_DRIVEN", "CODE_DRIVEN", "dev-design-reference",
        "View Strategy: SHARED | RESPONSIVE | HYBRID | SPLIT_VIEW", "Package / View Plan",
        "Shared Implementation: api | model | state | hooks | common UI", "Desktop/Mobile Verification Matrix",
        "dev-api-contract", "dev-figma-design", "DESIGN_CONFORMANCE", "VISUAL_REGRESSION",
        "Regression Baseline: APPROVED_BROWSER_SCREENSHOT",
        "Frontend Environment Gate: REQUIRED", "BLOCK_AND_SPLIT_MIGRATION",
        "LINUX_ISOLATED_NODE_RUNTIME", "PROJECT_TOOLCHAIN_MIGRATION_REQUIRED",
    )),
    "coder frontend gate": (coder, (
        'skill_view("dev-frontend-feature")', "첫 Node command",
        "node_environment_gate.py", "FRONTEND_ENVIRONMENT_GATE=BLOCKED",
        "PROJECT_TOOLCHAIN_MIGRATION_REQUIRED", "kanban_block",
        "source worktree", "node_runtime.py", "Linux isolated workspace",
    )),
    "frontend entry": (frontend, (
        "canonical entry", "REFERENCE_DRIVEN", "CODE_DRIVEN",
        "View Strategy / Implementation Architecture", "SHARED", "RESPONSIVE", "HYBRID", "SPLIT_VIEW",
        "src/features/<feature>/", "Shared / Split 책임", "API Boundary", "Desktop/Mobile Verification Matrix",
        "Design Source", "IMAGE", "FIGMA", "EXISTING_CODE", "dev-design-reference",
        "OBSERVED", "INFERRED", "UNKNOWN", "Storybook Catalog",
        "DESIGN_CONFORMANCE", "VISUAL_REGRESSION", "dev-ui-ux", "dev-figma-design", "lazy-load",
        "dev-official-docs-context", 'skill_view("dev-official-docs-context")', "External Technology Documentation Gate",
        "dev-typescript-guidelines", "dev-frontend-guidelines", "dev-nextjs-feature", "dev-node-dependencies",
        "DEPENDENCY_DECLARATION_COMPATIBILITY", "Documentation Version Match",
        "Frontend Environment Gate", "node_environment_gate.py",
        "PROJECT_TOOLCHAIN_MIGRATION_REQUIRED", "Source Verification Fallback: FORBIDDEN",
        "patch-package", "별도 승인된 해결 범위",
        "EXTRANEOUS", "analysis_incomplete", "Tirith Package Preflight",
    )),
    "official docs skill": (official_docs, (
        "Version First", "Context7 Hosted MCP Provider",
        "https://mcp.context7.com/mcp", "Default auth: anonymous", "resolve-library-id", "query-docs",
        "EXACT", "COMPATIBLE", "LATEST_ONLY", "LOCAL_ONLY",
        "DEPENDENCY_DECLARATION_COMPATIBILITY", "patch-package 자동 도입/적용",
        "별도 승인된 compatibility 해결 범위", "compiler/typecheck/test/build",
    )),
    "node dependency skill": (node_dependencies, (
        "pnpm 하나만 사용한다", "devEngines.runtime", "devEngines.packageManager",
        "pnpm-lock.yaml", "package-lock.json", "migration blocker", "PACKAGE_MANAGER_ROOT",
        "Frontend Environment Gate", "node_environment_gate.py", "PROJECT_TOOLCHAIN_MIGRATION_REQUIRED",
        "SOURCE_VERIFICATION_POLICY=FORBIDDEN", "source worktree", "fallback",
        "node_dependency_preflight.py", "tirith_package_preflight.py", "analysis_incomplete",
        "TIRITH_PREFLIGHT=allow", "TIRITH_PREFLIGHT=approval_required", "actual Hermes terminal guard",
        "timeout=600", "shell `timeout` wrapper", "Linux named volume의 격리 workspace",
        "RESTORE_WORKDIR", "별도 Hermes 전용 Node version 설정 파일을 만들지 않는다",
    )),
    "node dependency preflight": (node_preflight, (
        "PNPM_LOCKFILE", "LEGACY_LOCKFILES", "os.walk", "SKIP_DIRS",
        "package-lock.json", "pnpm-lock.yaml", "devEngines", "resolve_dev_engines",
        "PACKAGE_MANAGER_ROOT", "LOCKFILE_PRESENT", "legacy package-manager lockfile detected",
        "EXTRANEOUS_PRESENT", "VERIFICATION_PACKAGE_ROOT", "INSTALL_REQUIRED", "INSTALL_WORKDIR",
        "DEPENDENCY_FINGERPRINT", "DEPENDENCIES_READY",
        "RESTORE_REQUIRED", "RESTORE_COMMAND", "RESTORE_WORKDIR", "RESTORE_MARK_COMMAND",
        "INSTALL_TIMEOUT_SECONDS = 600", "STATUS=pass", "STATUS=blocked",
    )),
    "node environment gate": (node_environment_gate, (
        "PNPM_LOCKFILE", "LEGACY_LOCKFILES", "devEngines.runtime", "devEngines.packageManager",
        "packageManager conflicts with DevKit pnpm-only contract", "pnpm-lock.yaml is required",
        "FRONTEND_ENVIRONMENT_GATE=PASS", "FRONTEND_ENVIRONMENT_GATE=BLOCKED",
        "PROJECT_TOOLCHAIN_MIGRATION_REQUIRED", "DEVKIT_RUNTIME_CAPABILITY_MISSING",
        "SOURCE_VERIFICATION_POLICY=FORBIDDEN", "VERIFICATION_RUNTIME=node_runtime.py",
    )),
    "tirith package preflight": (tirith_preflight, (
        "analysis_incomplete", "daemon", "start", "--detach", "daemon-recheck-pass", "daemon-recheck-fail",
        "approval_required", "Hermes terminal guard remains authoritative", "do not execute install",
    )),
    "node runtime": (node_runtime, (
        "prepare_isolated_package", "validate_project_environment",
        "NODE_RUNTIME_SOURCE_PACKAGE_ROOT", "NODE_RUNTIME_CWD", "NODE_RUNTIME_ENVIRONMENT_GATE=PASS",
        "NODE_RUNTIME_SOURCE_VERIFICATION_POLICY=FORBIDDEN", "NODE_RUNTIME_BLOCKER_CLASS",
        "pnpm_home", "pnpm_store", "devEngines", "packageManager.name must be 'pnpm'",
        "fcntl.flock", "validate_pnpm_command", "timed out waiting for Node workspace lock",
        "linux-isolated-workspace;workspace-serialized",
    )),
    "node workspace": (node_workspace, (
        'HERMES_NODE_ROOT", "/opt/data/node"', "GENERATED_NAMES", "PRESERVE_DEST_NAMES",
        '"node_modules"', '".next"', '".test-build"', '".tsbuildinfo"',
        "_assert_owned_by_current_user", "internal Node state owner mismatch",
        "prepare_isolated_package", "isolated_package_root", "NODE_WORKSPACE_SYNC=ready",
    )),
    "design reference": (design, (
        "Design Source", "IMAGE", "FIGMA", "DRAFT", "REFERENCE", "APPROVED",
        "STRUCTURE", "VISUAL", "HIGH", "OBSERVED", "INFERRED", "UNKNOWN",
        "docs/ui/screens/<screen>/", "reference.png", "screen-spec.md", "Normalized Design Evidence",
        "screen_spec_guard.py", "dev-figma-design",
    )),
    "design template": (design_template, (
        "status: APPROVED", "source: IMAGE", "reference: ./reference.png", "fidelity: VISUAL",
        "view_strategy: <SHARED | RESPONSIVE | HYBRID | SPLIT_VIEW>", "## View Strategy", "## 구현 구조",
        "Shared Implementation", "Split Implementation", "Verification Matrix",
        "## 상태", "## 반응형", "## Interaction / Navigation", "## Unknown / Open Question", "## Acceptance Criteria",
    )),
    "design guard": (design_guard, (
        "ALLOWED_STATUS", "DRAFT", "REFERENCE", "APPROVED", "ALLOWED_SOURCE",
        "IMAGE", "FIGMA", "ALLOWED_FIDELITY", "STRUCTURE", "VISUAL", "HIGH",
        "ALLOWED_VIEW_STRATEGY", "SHARED", "RESPONSIVE", "HYBRID", "SPLIT_VIEW", "UNSPECIFIED",
        "SCREEN_SPEC_STATUS=pass", "VIEW_STRATEGY=", "IMAGE reference not found", "FIGMA reference must be",
    )),
    "frontend test": (frontend_test, (
        "Storybook", "Playwright", "FUNCTIONAL", "COMPONENT", "E2E",
        "View Strategy / Platform Verification", "Desktop/Mobile Verification Matrix", "Shared owner check",
        "VISUAL_CONFORMANCE", "VISUAL_REGRESSION", "Design Conformance", "Visual Regression",
        "Approved Implementation", "Browser Screenshot Golden", "toHaveScreenshot",
        "NOT_AVAILABLE", "자동 설치하지 않는다", "Frontend Verification Environment Gate",
        "node_environment_gate.py", "SOURCE_VERIFICATION_POLICY", "Hermes Node Runtime Isolation", "node_runtime.py",
        "/opt/data/node", "workspace lock", "devEngines.runtime", "devEngines.packageManager",
        "Linux 격리 workspace", "host node_modules/.next", "dependency fingerprint",
        "RESTORE_MARK_COMMAND", "검증 시작마다 초기화", "Tirith actual guard",
    )),
    "typescript skill": (typescript, (
        "Version Gate", "TypeScript 7 Gate", "Strictness Gate", "useUnknownInCatchVariables",
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
        "Rules of Hooks / `use` 예외", "State Ownership", "`useEffectEvent` (React 19.2+)",
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
        "Version Lane", "Measure First", "Client JS Budget", "Bundle Analysis / Package Optimization",
        "Lazy Loading / Dynamic Import", "Navigation / Prefetch / Streaming", "Instant Navigation",
        "Data Fetching / Waterfall", "Cache / Revalidation / Cache Components", "Image Optimization",
        "Font Optimization", "Third-party Script Optimization", "Turbopack Dev / Build Performance",
        "CI `.next/cache`", "Memory Investigation", "Web Vitals", "Performance Evidence", "Review Hotspots",
    )),
    "nextjs reference": (nextjs_reference, (
        "Next.js Official Practices", "Current Version / Support Gate", "Measure in Production Mode",
        "Bundle Analysis", "Package Import Optimization", "Lazy Loading and Dynamic Import",
        "Data Fetching and Waterfalls", "Cache Components / Caching / Revalidation", "Instant Navigation",
        "Image Optimization", "Font Optimization", "Third-party Scripts", "React Compiler", "Turbopack",
        "File System Cache", "Memory", "Build Performance / CI Cache", "Web Vitals / Runtime Monitoring",
        "Performance Investigation Order", "Primary Official Sources",
    )),
    "figma skill": (figma, (
        "dev-design-reference", "DRAFT", "REFERENCE", "APPROVED",
        "Normalized Evidence", "FIGMA_ACCESS_TOKEN", "FIGMA_OAUTH_TOKEN", "file_content:read", "--preview-out", "read-only",
    )),
    "figma provider": (figma_script, (
        "https://api.figma.com", "X-Figma-Token", "Authorization", "/v1/files/", "/v1/images/", "HERMES_WRITE_SAFE_ROOT", "MAX_DEPTH = 6",
    )),
    "stack guide": (stack, (
        "dev-frontend-feature", "dev-design-reference", "dev-official-docs-context", "dev-typescript-guidelines", "dev-frontend-guidelines",
        "dev-nextjs-feature", "dev-node-dependencies", "dev-figma-design", "REFERENCE_DRIVEN", "CODE_DRIVEN",
        "실제 installed/resolved version", "DEPENDENCY_DECLARATION_COMPATIBILITY", "EXTRANEOUS", "analysis_incomplete", "Tirith",
        "DESIGN_CONFORMANCE", "VISUAL_REGRESSION", "Storybook", "Stack Detection != Skill Loading",
        "Frontend Node environment boundary", "node_environment_gate.py",
        "PROJECT_TOOLCHAIN_MIGRATION_REQUIRED", "source worktree", "patch-package",
    )),
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
for key in ("FIGMA_ACCESS_TOKEN", "FIGMA_OAUTH_TOKEN", "CONTEXT7_API_KEY"):
    if key not in sample_values:
        raise SystemExit(f"sample.env missing {key}")
    if sample_values[key]:
        raise SystemExit(f"sample.env {key} must stay blank")
    if f"{key}: ${{{key}:-}}" not in compose:
        raise SystemExit(f"compose.yml missing {key}")

print("[PASS] Frontend reference-driven/official-docs/Node dependency/runtime isolation/Image/Figma/Storybook/Playwright capability contract")
