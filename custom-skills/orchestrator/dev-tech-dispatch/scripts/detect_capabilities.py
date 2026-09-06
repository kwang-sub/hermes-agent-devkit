#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def add(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def package_dependencies(repo: Path) -> set[str]:
    path = repo / "package.json"
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    result: set[str] = set()
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        values = data.get(key, {})
        if isinstance(values, dict):
            result.update(str(name) for name in values)
    return result


def detect(repo: Path) -> dict[str, object]:
    stacks: list[str] = []
    backend_skills: list[str] = []
    frontend_hints: list[str] = []

    gradle = [repo / "build.gradle", repo / "build.gradle.kts"]
    pom = repo / "pom.xml"
    java_build = any(path.is_file() for path in gradle) or pom.is_file()
    build_text = "\n".join(read(path) for path in [*gradle, pom] if path.is_file())

    if java_build:
        add(stacks, "java")
        add(backend_skills, "dev-java-guidelines")
    if java_build and any(marker in build_text for marker in ("org.springframework.boot", "spring-boot", "org.springframework")):
        add(stacks, "spring")
        add(backend_skills, "dev-spring-guidelines")

    deps = package_dependencies(repo)
    has_package = (repo / "package.json").is_file()
    if has_package and ((repo / "tsconfig.json").is_file() or "typescript" in deps):
        add(stacks, "typescript")
        add(frontend_hints, "dev-typescript-guidelines")
    if "react" in deps or "react-dom" in deps:
        add(stacks, "react")
        add(frontend_hints, "dev-frontend-guidelines")
    if "next" in deps:
        add(stacks, "nextjs")
        add(frontend_hints, "dev-nextjs-feature")

    test_markers = {"vitest", "jest", "@testing-library/react", "@testing-library/jest-dom", "@playwright/test", "playwright", "cypress"}
    if deps.intersection(test_markers):
        add(frontend_hints, "dev-frontend-test")

    has_frontend = any(stack in stacks for stack in ("typescript", "react", "nextjs"))
    has_backend = any(stack in stacks for stack in ("java", "spring"))
    return {
        "stacks": stacks,
        "backend_skills": backend_skills,
        "frontend_entry": "dev-frontend-feature" if has_frontend else "",
        "frontend_hints": frontend_hints,
        "ui_candidate": "dev-ui-ux" if has_frontend else "",
        "cross_stack_candidate": "dev-api-contract" if has_frontend and has_backend else "",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect project stacks and canonical capability candidates")
    parser.add_argument("--repo", required=True)
    args = parser.parse_args()
    repo = Path(args.repo).expanduser().resolve()
    if not repo.is_dir():
        print(f"ERROR=repository not found: {repo}")
        return 2
    result = detect(repo)
    print(f"STACKS={','.join(result['stacks'])}")
    print(f"BACKEND_SKILLS={','.join(result['backend_skills'])}")
    print(f"FRONTEND_ENTRY={result['frontend_entry']}")
    print(f"FRONTEND_HINTS={','.join(result['frontend_hints'])}")
    print(f"UI_SKILL_CANDIDATE={result['ui_candidate']}")
    print(f"CROSS_STACK_SKILL_CANDIDATE={result['cross_stack_candidate']}")
    print("STATUS=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
