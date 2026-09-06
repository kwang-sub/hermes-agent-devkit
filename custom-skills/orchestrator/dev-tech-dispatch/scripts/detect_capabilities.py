#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def ordered_add(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def read_text(path: Path) -> str:
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


def detect(repo: Path) -> dict[str, list[str] | str]:
    stacks: list[str] = []
    base_skills: list[str] = []
    test_skills: list[str] = []

    gradle_files = [repo / "build.gradle", repo / "build.gradle.kts"]
    pom = repo / "pom.xml"
    java_build = any(path.is_file() for path in gradle_files) or pom.is_file()
    build_text = "\n".join(read_text(path) for path in [*gradle_files, pom] if path.is_file())

    if java_build:
        ordered_add(stacks, "java")
        ordered_add(base_skills, "dev-java-guidelines")

    spring_markers = (
        "org.springframework.boot",
        "spring-boot",
        "org.springframework",
    )
    if java_build and any(marker in build_text for marker in spring_markers):
        ordered_add(stacks, "spring")
        ordered_add(base_skills, "dev-spring-guidelines")

    deps = package_dependencies(repo)
    has_package = (repo / "package.json").is_file()

    if has_package and ((repo / "tsconfig.json").is_file() or "typescript" in deps):
        ordered_add(stacks, "typescript")
        ordered_add(base_skills, "dev-typescript-guidelines")

    if "react" in deps or "react-dom" in deps:
        ordered_add(stacks, "react")
        ordered_add(base_skills, "dev-frontend-guidelines")

    if "next" in deps:
        ordered_add(stacks, "nextjs")
        ordered_add(base_skills, "dev-nextjs-feature")

    frontend_test_markers = {
        "vitest", "jest", "@testing-library/react", "@testing-library/jest-dom",
        "@playwright/test", "playwright", "cypress",
    }
    if deps.intersection(frontend_test_markers):
        ordered_add(test_skills, "dev-frontend-test")

    has_frontend = any(stack in stacks for stack in ("typescript", "react", "nextjs"))
    has_backend = any(stack in stacks for stack in ("java", "spring"))

    return {
        "stacks": stacks,
        "base_skills": base_skills,
        "test_skills": test_skills,
        "ui_candidate": "dev-ui-ux" if has_frontend else "",
        "cross_stack_candidate": "dev-api-contract" if has_frontend and has_backend else "",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    args = parser.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    if not repo.is_dir():
        print(f"ERROR=repository not found: {repo}")
        return 2

    result = detect(repo)
    print(f"STACKS={','.join(result['stacks'])}")
    print(f"BASE_SKILLS={','.join(result['base_skills'])}")
    print(f"TEST_SKILLS={','.join(result['test_skills'])}")
    print(f"UI_SKILL_CANDIDATE={result['ui_candidate']}")
    print(f"CROSS_STACK_SKILL_CANDIDATE={result['cross_stack_candidate']}")
    print("STATUS=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
