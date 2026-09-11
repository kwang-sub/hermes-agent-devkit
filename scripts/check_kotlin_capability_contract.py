#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(path: Path, terms: tuple[str, ...], failures: list[str]) -> None:
    if not path.is_file():
        failures.append(f"{path.relative_to(ROOT)} missing")
        return
    text = path.read_text(encoding="utf-8")
    missing = [term for term in terms if term not in text]
    if missing:
        failures.append(f"{path.relative_to(ROOT)} missing: {', '.join(missing)}")


def main() -> int:
    failures: list[str] = []

    skill = ROOT / "custom-skills/shared/dev-kotlin-guidelines/SKILL.md"
    detector = ROOT / "custom-skills/orchestrator/dev-tech-dispatch/scripts/detect_capabilities.py"
    detector_test = ROOT / "custom-skills/orchestrator/dev-tech-dispatch/tests/test_detect_capabilities.py"
    dispatch = ROOT / "custom-skills/orchestrator/dev-tech-dispatch/SKILL.md"
    pattern = ROOT / "custom-skills/orchestrator/dev-project-pattern/SKILL.md"
    breakdown = ROOT / "custom-skills/orchestrator/dev-breakdown/SKILL.md"
    common = ROOT / "shared/AGENTS.common.md"
    compat = ROOT / "scripts/verify_latest_hermes_compat.sh"

    require(skill, (
        "Stable", "Experimental", "`!!`", "data class", "value class",
        "sealed", "Context parameters", "Explicit backing fields",
        "kotlin-spring", "kotlin-jpa", "Annotation Use-site Target",
        "Coroutine / Flow", "GlobalScope", "KSP", "kapt", "JSpecify",
        "Java + Kotlin Mixed Project", "dev-spring-guidelines", "dev-spring-data",
    ), failures)
    require(detector, (
        'DETECTOR_VERSION = "4"', '"kotlin"', 'dev-kotlin-guidelines',
        'org.jetbrains.kotlin.jvm', 'kotlin-maven-plugin',
        'org.jetbrains.kotlin.plugin.spring', 'org.jetbrains.kotlin.plugin.jpa',
    ), failures)
    require(detector_test, (
        "test_kotlin_only", "test_kotlin_spring", "test_kotlin_spring_jpa",
        "test_java_kotlin_mixed", "test_maven_kotlin", "test_kotlin_frontend_monorepo",
    ), failures)
    require(dispatch, (
        "Kotlin", "dev-kotlin-guidelines", "STACKS=kotlin,spring",
        "STACKS=java,kotlin,spring",
    ), failures)
    require(pattern, (
        "Kotlin → dev-kotlin-guidelines", "Java + Kotlin",
    ), failures)
    require(breakdown, (
        "Kotlin 프로젝트의 Kotlin 변경", "dev-kotlin-guidelines",
    ), failures)
    require(common, (
        "## JVM 언어 capability", 'skill_view("dev-kotlin-guidelines")',
        "Entity `data class`", "GlobalScope", "Java + Kotlin mixed project",
    ), failures)
    require(compat, (
        "/opt/custom-skills/shared/dev-kotlin-guidelines/SKILL.md",
    ), failures)

    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}")
        return 1

    print("[PASS] Kotlin first-class capability contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
