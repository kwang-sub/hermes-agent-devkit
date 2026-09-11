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
    guidelines = ROOT / "custom-skills/shared/dev-spring-guidelines/SKILL.md"
    reference = ROOT / "custom-skills/shared/dev-spring-guidelines/references/official-spring-practices.md"
    feature = ROOT / "custom-skills/shared/dev-spring-feature/SKILL.md"
    data = ROOT / "custom-skills/shared/dev-spring-data/SKILL.md"
    tests = ROOT / "custom-skills/shared/dev-spring-test/SKILL.md"
    review = ROOT / "custom-skills/reviewer/dev-code-review/SKILL.md"
    compat = ROOT / "scripts/verify_latest_hermes_compat.sh"

    require(guidelines, (
        "version: 0.2.0",
        "Version Compatibility Gate",
        "Dependency Injection",
        "constructor injection",
        "@ConfigurationProperties",
        "self-invocation",
        "RuntimeException",
        "ProblemDetail",
        "MVC / WebFlux / Reactive Boundary",
        "RestClient",
        "WebClient",
        "HTTP Service Client",
        "HandlerMethodValidationException",
        "JSpecify",
        "ReactiveTransactionManager",
        "Review Hotspots",
    ), failures)
    require(reference, (
        "Spring Framework / Spring Boot 공식 Reference",
        "constructor injection",
        "@ConfigurationProperties",
        "AOP proxy",
        "RuntimeException / Error",
        "MethodArgumentNotValidException",
        "HandlerMethodValidationException",
        "RFC 9457",
        "RestClient",
        "WebClient",
        "HTTP Service Client",
        "JSpecify",
        "ReactiveTransactionManager",
        "Project Convention First",
    ), failures)
    require(feature, (
        "version: 0.2.0",
        "Validation",
        "MethodArgumentNotValidException",
        "HandlerMethodValidationException",
        "@Transactional",
        "self-invocation",
        "ProblemDetail",
        "Validation Mode: OBJECT | METHOD | BOTH | NONE",
    ), failures)
    # Existing user-specific persistence and test policy must remain intact.
    require(data, (
        "1. Spring Data JPA Method Query",
        "2. QueryDSL",
        "3. Native Query",
        "N+1",
        "collection fetch join + paging",
    ), failures)
    require(tests, (
        "@SpringBootTest",
        "@WebMvcTest",
        "@DataJpaTest",
        "모든 변경을 무조건 `@SpringBootTest`로 검증하지 않는다",
        "validation/error response 변경",
    ), failures)
    require(review, (
        "dev-spring-guidelines",
        "dev-spring-feature",
        "dev-spring-data",
        "dev-spring-test",
        "Stack / Capability Review Gate",
    ), failures)
    require(compat, (
        "/opt/custom-skills/shared/dev-spring-guidelines/SKILL.md",
        "/opt/custom-skills/shared/dev-spring-guidelines/references/official-spring-practices.md",
        "/opt/custom-skills/shared/dev-spring-feature/SKILL.md",
    ), failures)

    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}")
        return 1
    print("[PASS] Spring official-practice capability contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
