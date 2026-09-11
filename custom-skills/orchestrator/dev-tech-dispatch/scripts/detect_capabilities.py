#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Iterable


DETECTOR_VERSION = "3"
MAX_MANIFEST_DEPTH = 3
SKIP_DIRS = {
    ".git", ".hermes", ".worktrees", ".gradle", ".idea", ".vscode",
    "node_modules", "build", "dist", ".next", "target", "out", "coverage",
}
EXACT_MANIFEST_NAMES = {
    "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts",
    "gradle.properties", "pom.xml", "package.json", "package-lock.json",
    "pnpm-lock.yaml", "pnpm-workspace.yaml", "yarn.lock", "bun.lockb", "bun.lock",
}

KOTLIN_MARKERS = (
    'kotlin("jvm")', "kotlin('jvm')",
    'kotlin("plugin.spring")', "kotlin('plugin.spring')",
    'kotlin("plugin.jpa")', "kotlin('plugin.jpa')",
    "org.jetbrains.kotlin.jvm",
    "org.jetbrains.kotlin.plugin.spring",
    "org.jetbrains.kotlin.plugin.jpa",
    "kotlin-maven-plugin",
)
JAVA_EXPLICIT_PATTERNS = (
    r'id\s*\(\s*["\']java["\']\s*\)',
    r'id\s+["\']java["\']',
    r'(?m)^\s*java\s*$',
    r'java-library',
    r'maven-compiler-plugin',
)
SPRING_MARKERS = (
    "org.springframework.boot", "spring-boot", "org.springframework",
)


def add(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def is_manifest_name(name: str) -> bool:
    return name in EXACT_MANIFEST_NAMES or (
        name.startswith("tsconfig") and name.endswith(".json")
    ) or name == "libs.versions.toml"


def discover_inputs(repo: Path) -> list[Path]:
    """Return bounded build/dependency manifests for root or small monorepos.

    Source trees are never scanned for technology inference. Only manifest names
    up to MAX_MANIFEST_DEPTH are considered and common generated/vendor roots
    are pruned before descent.
    """
    repo = repo.resolve()
    found: list[Path] = []

    for root_text, dirs, files in os.walk(repo):
        root = Path(root_text)
        try:
            relative = root.relative_to(repo)
        except ValueError:
            continue
        depth = len(relative.parts)

        dirs[:] = sorted(
            name for name in dirs
            if name not in SKIP_DIRS and not name.startswith(".")
        )
        if depth >= MAX_MANIFEST_DEPTH:
            dirs[:] = []

        for name in sorted(files):
            if is_manifest_name(name):
                found.append(root / name)

    return sorted(found, key=lambda path: path.relative_to(repo).as_posix())


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def package_dependencies(paths: Iterable[Path]) -> set[str]:
    result: set[str] = set()
    for path in paths:
        if path.name != "package.json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for key in ("dependencies", "devDependencies", "peerDependencies"):
            values = data.get(key, {})
            if isinstance(values, dict):
                result.update(str(name) for name in values)
    return result


def fingerprint(repo: Path, inputs: list[Path] | None = None) -> dict[str, object]:
    repo = repo.resolve()
    manifests = inputs if inputs is not None else discover_inputs(repo)
    digest = hashlib.sha256()
    digest.update(f"detector:{DETECTOR_VERSION}\0".encode("utf-8"))

    relative_inputs: list[str] = []
    for path in manifests:
        relative = path.relative_to(repo).as_posix()
        relative_inputs.append(relative)
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        try:
            with path.open("rb") as handle:
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
        except OSError:
            digest.update(b"<unreadable>")
        digest.update(b"\0")

    return {
        "detector_version": DETECTOR_VERSION,
        "fingerprint": "sha256:" + digest.hexdigest(),
        "inputs": relative_inputs,
    }


def detect(repo: Path) -> dict[str, object]:
    repo = repo.resolve()
    manifests = discover_inputs(repo)
    fp = fingerprint(repo, manifests)

    stacks: list[str] = []
    backend_skills: list[str] = []
    frontend_hints: list[str] = []

    jvm_manifests = [
        path for path in manifests
        if path.name in {
            "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts",
            "gradle.properties", "pom.xml", "libs.versions.toml",
        }
    ]
    build_files = [
        path for path in manifests
        if path.name in {"build.gradle", "build.gradle.kts", "pom.xml"}
    ]
    jvm_text = "\n".join(read(path) for path in jvm_manifests)

    has_kotlin = any(marker in jvm_text for marker in KOTLIN_MARKERS)
    has_explicit_java = any(
        re.search(pattern, jvm_text, flags=re.IGNORECASE)
        for pattern in JAVA_EXPLICIT_PATTERNS
    )
    # Preserve the legacy detector behavior for JVM build manifests with no
    # Kotlin evidence. Once Kotlin is explicit, Java is reported only when the
    # manifest also carries explicit Java/maven-compiler evidence.
    has_java = bool(build_files) and (not has_kotlin or has_explicit_java)
    has_spring = bool(build_files) and any(marker in jvm_text for marker in SPRING_MARKERS)

    if has_java:
        add(stacks, "java")
        add(backend_skills, "dev-java-guidelines")
    if has_kotlin:
        add(stacks, "kotlin")
        add(backend_skills, "dev-kotlin-guidelines")
    if has_spring:
        add(stacks, "spring")
        add(backend_skills, "dev-spring-guidelines")

    package_files = [path for path in manifests if path.name == "package.json"]
    deps = package_dependencies(package_files)
    has_tsconfig = any(
        path.name.startswith("tsconfig") and path.name.endswith(".json")
        for path in manifests
    )
    if package_files and (has_tsconfig or "typescript" in deps):
        add(stacks, "typescript")
        add(frontend_hints, "dev-typescript-guidelines")
    if "react" in deps or "react-dom" in deps:
        add(stacks, "react")
        add(frontend_hints, "dev-frontend-guidelines")
    if "next" in deps:
        add(stacks, "nextjs")
        add(frontend_hints, "dev-nextjs-feature")

    test_markers = {
        "vitest", "jest", "@testing-library/react", "@testing-library/jest-dom",
        "@playwright/test", "playwright", "cypress",
    }
    if deps.intersection(test_markers):
        add(frontend_hints, "dev-frontend-test")

    has_frontend = any(stack in stacks for stack in ("typescript", "react", "nextjs"))
    has_backend = any(stack in stacks for stack in ("java", "kotlin", "spring"))
    return {
        **fp,
        "stacks": stacks,
        "backend_skills": backend_skills,
        "frontend_entry": "dev-frontend-feature" if has_frontend else "",
        "frontend_hints": frontend_hints,
        "ui_candidate": "dev-ui-ux" if has_frontend else "",
        "cross_stack_candidate": "dev-api-contract" if has_frontend and has_backend else "",
    }


def print_text(result: dict[str, object], *, fingerprint_only: bool) -> None:
    print(f"DETECTOR_VERSION={result['detector_version']}")
    print(f"STACK_FINGERPRINT={result['fingerprint']}")
    print(f"STACK_INPUTS={','.join(result['inputs'])}")
    if not fingerprint_only:
        print(f"STACKS={','.join(result['stacks'])}")
        print(f"BACKEND_SKILLS={','.join(result['backend_skills'])}")
        print(f"FRONTEND_ENTRY={result['frontend_entry']}")
        print(f"FRONTEND_HINTS={','.join(result['frontend_hints'])}")
        print(f"UI_SKILL_CANDIDATE={result['ui_candidate']}")
        print(f"CROSS_STACK_SKILL_CANDIDATE={result['cross_stack_candidate']}")
    print("STATUS=pass")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detect bounded project stacks and canonical capability candidates"
    )
    parser.add_argument("--repo", required=True)
    parser.add_argument("--fingerprint-only", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    if not repo.is_dir():
        if args.json_output:
            print(json.dumps({"status": "blocked", "error": f"repository not found: {repo}"}))
        else:
            print(f"ERROR=repository not found: {repo}")
        return 2

    result = fingerprint(repo) if args.fingerprint_only else detect(repo)
    if args.json_output:
        print(json.dumps({**result, "status": "pass"}, ensure_ascii=False))
    else:
        print_text(result, fingerprint_only=args.fingerprint_only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
