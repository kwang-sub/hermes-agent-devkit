#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "custom-skills/shared/dev-official-docs-context/SKILL.md"
VERSION_HELPER = ROOT / "custom-skills/shared/dev-official-docs-context/scripts/detect_dependency_versions.py"
CONTEXT7_HELPER = ROOT / "custom-skills/shared/dev-official-docs-context/scripts/context7_docs.py"
FRONTEND = ROOT / "custom-skills/shared/dev-frontend-feature/SKILL.md"
SPRING = ROOT / "custom-skills/shared/dev-spring-feature/SKILL.md"
COMPOSE = ROOT / "compose.yml"
SAMPLE_ENV = ROOT / "sample.env"
UPDATER = ROOT / "update-devkit.ps1"


def read(path: Path) -> str:
    if not path.is_file():
        raise SystemExit(f"missing official-docs contract file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8-sig")


def require(text: str, terms: tuple[str, ...], label: str) -> None:
    missing = [term for term in terms if term not in text]
    if missing:
        raise SystemExit(f"{label} missing terms: {', '.join(missing)}")


def forbid(text: str, terms: tuple[str, ...], label: str) -> None:
    present = [term for term in terms if term in text]
    if present:
        raise SystemExit(f"{label} contains forbidden terms: {', '.join(present)}")


def main() -> int:
    skill = read(SKILL)
    require(skill, (
        "version: 0.1.1", "Version First", "Context7 Hosted MCP Provider",
        "https://mcp.context7.com/mcp", "Default auth: anonymous",
        "resolve-library-id", "query-docs", "EXACT", "COMPATIBLE", "LATEST_ONLY", "LOCAL_ONLY",
        "DEPENDENCY_DECLARATION_COMPATIBILITY", "compiler/typecheck/test/build",
        "API key 생성을 사용자에게 강제하지 않는다", "최대 3회",
    ), "dev-official-docs-context")

    version_helper = read(VERSION_HELPER)
    require(version_helper, (
        "SKIP_DIRS", "package-lock.json", "npm-shrinkwrap.json", "discover_package_roots",
        "multiple package roots found; pass --package-root", "package root must stay inside workspace",
        "RESOLVED_VERSION", "VERSION_SOURCE", "STATUS=pass", "STATUS=blocked",
    ), "dependency version helper")
    forbid(version_helper, ("urllib", "requests", "pip install", "npm install"), "dependency version helper")

    context7 = read(CONTEXT7_HELPER)
    require(context7, (
        'MCP_URL = "https://mcp.context7.com/mcp"',
        'ALLOWED_TOOLS = frozenset({"resolve-library-id", "query-docs"})',
        "streamable_http_client", "streamablehttp_client", "ClientSession",
        '"libraryName": args.library', '"libraryId": args.library_id',
        '"query-docs"', '"resolve-library-id"',
        'CONTEXT7_TRANSPORT=hosted_mcp', 'CONTEXT7_AUTH_MODE=',
        'CONTEXT7_STATUS=unavailable', 'MAX_RESULT_CHARS',
        'return None, "anonymous"', 'Bearer {api_key}',
    ), "Context7 Hosted MCP helper")
    forbid(context7, (
        "https://context7.com/api/v2", "libs/search", "urllib.request", "requests.",
        "subprocess.run", "npx", "npm install", "pip install",
    ), "Context7 Hosted MCP helper")

    frontend = read(FRONTEND)
    require(frontend, (
        "version: 0.3.2", "dev-official-docs-context", 'skill_view("dev-official-docs-context")',
        "External Technology Documentation Gate", "actual resolved version",
        "DEPENDENCY_DECLARATION_COMPATIBILITY", "Documentation Version Match",
    ), "frontend entry")

    spring = read(SPRING)
    require(spring, (
        "version: 0.2.1", "dev-official-docs-context", 'skill_view("dev-official-docs-context")',
        "External SDK / API Documentation Gate", "actual Gradle/Maven resolved dependency version",
        "Context7 version-matched official docs", "Compile Evidence",
    ), "Spring feature")

    compose = read(COMPOSE)
    sample = read(SAMPLE_ENV)
    require(compose, ('CONTEXT7_API_KEY: ${CONTEXT7_API_KEY:-}',), "compose Context7 environment")
    require(sample, ("CONTEXT7_API_KEY=", "anonymous/limited access"), "sample.env Context7 contract")
    for line in sample.splitlines():
        if line.startswith("CONTEXT7_API_KEY=") and line != "CONTEXT7_API_KEY=":
            raise SystemExit("sample.env must never contain a Context7 API key")

    updater = read(UPDATER)
    require(updater, (
        'docker" -Arguments @("compose", "build", "--pull")',
        'docker" -Arguments @("compose", "up", "-d", "--force-recreate")',
        "Profile/skill reconciliation", "Runtime verification",
    ), "update-devkit deployment contract")

    print("[PASS] Official docs / Context7 Hosted MCP capability contract verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
