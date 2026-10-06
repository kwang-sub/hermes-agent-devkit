#!/usr/bin/env python3
"""Add a bounded entrypoint reminder to actual Kanban worker argv.

This is a prompt delivery adapter, not a tool permission or ownership bypass.
It is applied for both new and resumed workers before spawn.
Execution details stay in role skills/shared runtime policy rather than the
Kanban dispatcher prompt.
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
        f"할당된 작업만 수행한다. 첫 kanban_show 결과를 재사용하고 skill_view(\"{skill}\")로 현재 역할 계약을 로드한다. "
        "Direct/Standard/Recovery/CHANGES_REQUESTED와 새/재개 세션에 같은 역할 계약을 적용한다. "
        "source mutation 전에 역할 Skill의 Session History / Worker Context / Workspace Gate를 수행한다. "
        "KANBAN_EXECUTION_BOUNDARY_V1에 따라 Kanban은 WHAT/STATE만 제공하며 launcher, timeout, retry, cache, process cleanup 같은 HOW는 역할 Skill과 canonical runtime/execution 정책에서 결정한다. "
        "Kanban Task body나 startup prompt를 실행정책의 source of truth로 사용하지 않는다."
    )
    result = list(argv)
    result[index] += reminder
    return result
