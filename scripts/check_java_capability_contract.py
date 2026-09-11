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
    skill = ROOT / "custom-skills/shared/dev-java-guidelines/SKILL.md"
    reference = ROOT / "custom-skills/shared/dev-java-guidelines/references/official-java-practices.md"
    common = ROOT / "shared/AGENTS.common.md"
    compat = ROOT / "scripts/verify_latest_hermes_compat.sh"

    require(skill, (
        "version: 0.2.0",
        "Language Feature Stability Gate",
        "Preview / Incubator",
        "Record",
        "Sealed Class / Interface",
        "Pattern Matching / Switch",
        "Optional / Null",
        "Collection Ownership / Mutability",
        "parallelStream()",
        "Virtual Threads",
        "target Java >= 21",
        "Review Hotspots",
    ), failures)
    require(reference, (
        "Oracle Java Language Changes Summary",
        "Oracle Record Classes",
        "Oracle Sealed Classes",
        "Oracle Optional API",
        "OpenJDK JEP 444 Virtual Threads",
        "List.copyOf",
        "Optional.get()",
        "parallelStream()",
    ), failures)
    require(common, (
        "Java Reviewer",
        "Preview/Incubator",
        "record",
        "Optional",
        "mutable collection",
        "parallelStream",
        "virtual thread",
    ), failures)
    require(compat, (
        "/opt/custom-skills/shared/dev-java-guidelines/SKILL.md",
        "/opt/custom-skills/shared/dev-java-guidelines/references/official-java-practices.md",
    ), failures)

    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}")
        return 1
    print("[PASS] Java official-practice capability contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
