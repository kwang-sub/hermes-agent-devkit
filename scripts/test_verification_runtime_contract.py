#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(text: str, terms: tuple[str, ...], label: str) -> None:
    missing = [term for term in terms if term not in text]
    if missing:
        raise SystemExit(f"{label} missing contract terms: {', '.join(missing)}")


def main() -> int:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    require(
        dockerfile,
        (
            "COPY scripts/hermes-diff-check.py /usr/local/lib/hermes-diff-check.py",
            "exec python3 /usr/local/lib/hermes-diff-check.py",
            "/usr/local/bin/hermes-diff-check --help",
        ),
        "Dockerfile diff checker runtime",
    )
    if "COPY --chmod=0755 scripts/hermes-diff-check.py /usr/local/bin/hermes-diff-check" in dockerfile:
        raise SystemExit("Dockerfile must not execute the checked-out Python file by shebang")

    implement = (ROOT / "custom-skills/coder/dev-implement-plan/SKILL.md").read_text(encoding="utf-8")
    require(
        implement,
        (
            "독립 terminal command로 정확히 1회",
            "다른 명령을 `+`, `&&`, `;`, background process 또는 batch 형태로 붙이지 않는다",
            "STATUS=valid",
            "`git status`, `git branch`, `git rev-parse` probe를 실행하지 않는다",
            "임시 wrapper/script 생성",
            "CAPABILITY` blocker",
            "scripts/gradle_verification.py",
        ),
        "dev-implement-plan runtime policy",
    )

    gradle_helper = (ROOT / "custom-skills/coder/dev-implement-plan/scripts/gradle_verification.py").read_text(encoding="utf-8")
    require(
        gradle_helper,
        (
            "HERMES_KANBAN_TASK",
            "HERMES_SESSION_ID",
            "HERMES_GRADLE_BOUNDED_HELPER",
            "SESSION_DIRECT_GRADLE_ALLOWED=false",
            "write_session_guard",
        ),
        "bounded Gradle session guard",
    )

    hermes_java = (ROOT / "scripts/hermes-java").read_text(encoding="utf-8")
    require(
        hermes_java,
        (
            "check_gradle_session_guard",
            "HERMES_GRADLE_BOUNDED_HELPER",
            "HERMES_KANBAN_TASK",
            "HERMES_SESSION_ID",
            "direct Gradle execution is blocked for this Kanban session",
        ),
        "hermes-java Gradle session guard",
    )

    shim = ROOT / "custom-skills/reviewer/sdlc-review/SKILL.md"
    if not shim.is_file():
        raise SystemExit("legacy reviewer compatibility shim is missing")
    shim_text = shim.read_text(encoding="utf-8")
    require(shim_text, ("기존 Kanban Task", "dev-code-review", "신규 Task에서는 사용하지 않는다"), "sdlc-review shim")

    print("[PASS] verification runtime contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
