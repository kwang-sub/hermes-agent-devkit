#!/usr/bin/env python3
"""Add a bounded entrypoint reminder to actual Kanban worker argv.

This is a prompt delivery adapter, not a tool permission or ownership bypass.
It is applied for both new and resumed workers before spawn.
"""
from __future__ import annotations

MARKER = "DEVKIT_WORKER_STARTUP_V1"


def with_worker_startup(argv: list[str], profile: str) -> list[str]:
    if profile not in {"coder", "reviewer"}:
        return argv
    indices = [index for index, value in enumerate(argv) if value in {"-q", "--query"}]
    if len(indices) != 1 or indices[0] + 1 >= len(argv):
        raise RuntimeError("Kanban worker command must contain exactly one query")
    index = indices[0] + 1
    if MARKER in argv[index]:
        return argv
    skill = "dev-implement-plan" if profile == "coder" else "dev-code-review"
    reminder = (
        f"\n\n[{MARKER}]\n"
        f"할당된 작업만 수행한다. 첫 kanban_show 결과를 재사용하고 skill_view(\"{skill}\")로 현재 실행 계약을 로드한다. "
        "Direct/Standard/Recovery/CHANGES_REQUESTED와 새/재개 세션에 같은 계약을 적용한다. "
        "첫 workspace/source 탐색 전에 문서에 명시된 세션 기록과 context/workspace Gate를 수행한다. "
        "task_session_history.py는 /opt/devkit/bin의 지정 경로·호출법을 사용하며 find/--help를 반복하지 않는다. "
    )
    if profile == "coder":
        reminder += (
            "verify_workspace.py는 skill의 절대 경로로 단독 1회 실행하고 그 전에 git branch/status/rev-parse 또는 소스 읽기를 하지 않는다. "
            "Codex context는 kanban_show로 확인하며 scrub된 ownership 환경변수를 수동 주입하지 않는다. "
        )
    reminder += (
        "Maven은 /usr/local/bin/hermes-maven으로 실행한다(hermes-java ./mvnw도 같은 런처로 위임). "
        "mvn/원본 mvnw/HOME .m2 부재만으로 차단하거나 전체 디스크에서 실행파일·JAR를 찾지 않는다. "
        "Maven 검증은 dev-implement-plan/scripts/maven_verification.py를 사용하고 실제 blocker/evidence를 기록한다. "
        "미확인 세션은 SESSION_HISTORY_BEST_EFFORT_V1을 따르며 승인·보안·실제 검증 요구는 완화하지 않는다."
    )
    result = list(argv)
    result[index] += reminder
    return result
