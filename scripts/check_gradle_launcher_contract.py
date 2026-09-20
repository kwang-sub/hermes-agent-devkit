#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

COMMON_REQUIRED = (
    "Hermes container 내부의 모든 Gradle 실행은 raw `./gradlew ...` 또는 `gradle ...`을 직접 호출하지 않는다.",
    "`hermes-java ./gradlew ...`",
    "`dev-implement-plan/scripts/gradle_verification_cached.py`",
    "/opt/data/gradle",
)

PROFILE_REQUIRED = {
    ROOT / "custom-skills/orchestrator/dev-direct-flow/SKILL.md": (
        "Orchestrator는 project build/test를 실행하지 않는다",
        "Gradle 재현이 필요하면 Direct 판정을 멈추고 Standard로 전환",
        "`hermes-java ./gradlew ...`",
        "canonical cached verification helper",
    ),
    ROOT / "custom-skills/coder/dev-implement-plan/SKILL.md": (
        "raw `./gradlew ...` 또는 `gradle ...` 직접 실행은 금지",
        "`hermes-java ./gradlew ...`",
        "`gradle_verification_cached.py`",
    ),
    ROOT / "custom-skills/reviewer/dev-code-review/SKILL.md": (
        "raw `./gradlew ...` 또는 `gradle ...` 직접 실행도 금지",
        "canonical cached helper",
    ),
}

MARKDOWN_CONTRACTS = (
    ROOT / "AGENTS.md",
    ROOT / "shared/AGENTS.common.md",
    ROOT / "custom-skills/orchestrator/dev-direct-flow/SKILL.md",
    ROOT / "custom-skills/coder/dev-implement-plan/SKILL.md",
    ROOT / "custom-skills/coder/dev-implement-plan/references/implementation-details.md",
    ROOT / "custom-skills/reviewer/dev-code-review/SKILL.md",
    ROOT / "custom-skills/reviewer/dev-code-review/references/review-details.md",
)

RAW_MARKDOWN_COMMAND = re.compile(r"^\s*(?:\$\s*)?(?:\./gradlew|gradle)(?:\s|$)")
RAW_SHELL_COMMAND = re.compile(
    r"^\s*(?:(?:exec|command|timeout)\s+[^\n]*?\s+)?(?:\./gradlew|gradle)(?:\s|$)"
)
RAW_PYTHON_SUBPROCESS = re.compile(
    r"subprocess\.(?:run|Popen|call|check_call|check_output)\(\s*"
    r"(?:\[|\()\s*['\"](?:\./gradlew|gradle)['\"]",
    re.DOTALL,
)
RAW_PYTHON_OS = re.compile(
    r"os\.(?:system|popen)\(\s*['\"](?:\./gradlew|gradle)(?:\s|['\"])",
    re.DOTALL,
)


def require_terms(path: Path, terms: tuple[str, ...], failures: list[str]) -> str:
    if not path.is_file():
        failures.append(f"missing: {path.relative_to(ROOT)}")
        return ""
    text = path.read_text(encoding="utf-8")
    missing = [term for term in terms if term not in text]
    if missing:
        failures.append(
            f"{path.relative_to(ROOT)} missing Gradle launcher contract: {', '.join(missing)}"
        )
    return text


def check_markdown_commands(failures: list[str]) -> None:
    for path in MARKDOWN_CONTRACTS:
        if not path.is_file():
            failures.append(f"missing: {path.relative_to(ROOT)}")
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if RAW_MARKDOWN_COMMAND.match(line):
                failures.append(
                    f"{path.relative_to(ROOT)}:{line_no} contains executable raw Gradle command: {line.strip()}"
                )


def candidate_runtime_scripts() -> list[Path]:
    roots = (ROOT / "custom-skills", ROOT / "shared" / "scripts", ROOT / "scripts")
    paths: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".sh"}:
                continue
            rel = path.relative_to(ROOT)
            if "tests" in rel.parts or path.name.startswith("test_"):
                continue
            if rel.as_posix() == "scripts/hermes-java":
                continue
            paths.append(path)
    return sorted(paths)


def check_runtime_bypass(failures: list[str]) -> None:
    engine = ROOT / "custom-skills/coder/dev-implement-plan/scripts/gradle_verification.py"
    cached = ROOT / "custom-skills/coder/dev-implement-plan/scripts/gradle_verification_cached.py"
    launcher = ROOT / "scripts/hermes-java"

    engine_text = require_terms(
        engine,
        (
            "default=os.getenv('HERMES_JAVA_LAUNCHER', 'hermes-java')",
            "return [launcher, './gradlew', *args, '--no-daemon', '--console=plain']",
        ),
        failures,
    )
    require_terms(
        cached,
        ('default=os.getenv("HERMES_JAVA_LAUNCHER", "hermes-java")',),
        failures,
    )
    require_terms(
        launcher,
        (
            'workspace_root="$(git rev-parse --show-toplevel',
            'worktree list --porcelain',
            'toolchain_file="$primary_root/.hermes/toolchain.env"',
            'repo_hash="$(printf \'%s\' "$workspace_root" | git hash-object --stdin',
            'gradle_project_cache_root="${HERMES_GRADLE_PROJECT_CACHE_ROOT:-$gradle_root/project-cache}"',
            'gradle_extra_args+=(--project-cache-dir "$project_cache_dir")',
            'export HERMES_GRADLE_BUILD_DIR="$build_dir"',
            'gradle_extra_args+=(--init-script "$build_init_script")',
            'workspace_lock_file="$gradle_lock_root/workspace-${workspace_key}.lock"',
        ),
        failures,
    )

    for path in candidate_runtime_scripts():
        if path == engine:
            continue
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT)
        if path.suffix == ".py":
            if RAW_PYTHON_SUBPROCESS.search(text) or RAW_PYTHON_OS.search(text):
                failures.append(
                    f"{rel} launches Gradle directly instead of hermes-java/canonical helper"
                )
        else:
            for line_no, line in enumerate(text.splitlines(), 1):
                if RAW_SHELL_COMMAND.match(line):
                    failures.append(
                        f"{rel}:{line_no} launches raw Gradle command: {line.strip()}"
                    )

    if engine_text and "hermes-java" not in engine_text:
        failures.append(
            "gradle_verification.py no longer routes through the hermes-java launcher"
        )


def main() -> int:
    failures: list[str] = []

    for path in (ROOT / "AGENTS.md", ROOT / "shared/AGENTS.common.md"):
        require_terms(path, COMMON_REQUIRED, failures)

    for path, terms in PROFILE_REQUIRED.items():
        require_terms(path, terms, failures)

    check_markdown_commands(failures)
    check_runtime_bypass(failures)

    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}")
        return 1

    print("[PASS] Gradle launcher isolation contract: raw project-local Gradle execution is guarded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
