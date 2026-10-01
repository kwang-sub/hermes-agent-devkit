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

    require(
        ROOT / "shared/references/coding-rules.md",
        (
            "코드 로그 메시지는 영어로 작성한다",
            "logger.info",
            "console.error",
            "Reviewer",
            "공통 Coding Rule 위반",
        ),
        failures,
    )
    require(
        ROOT / "shared/AGENTS.common.md",
        (
            "코드 내부 운영/개발 로그 메시지",
            "영어로 작성한다",
            "비영어 logging message",
        ),
        failures,
    )
    require(
        ROOT / "custom-skills/reviewer/dev-code-review/SKILL.md",
        (
            "logging call",
            "비영어 자연어 로그 메시지",
            "로그 언어 Gate",
        ),
        failures,
    )

    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}")
        return 1

    print("[PASS] English code logging policy contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
