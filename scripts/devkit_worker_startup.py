#!/usr/bin/env python3
"""Add a bounded entrypoint reminder to actual Kanban worker argv.

This is a prompt delivery adapter, not a tool permission or ownership bypass.
It is applied for both new and resumed workers before spawn.
Execution details stay in role skills/shared runtime policy rather than the
Kanban dispatcher prompt.
"""
from __future__ import annotations

MARKER = "DEVKIT_WORKER_STARTUP_V1"

# Historical Kanban cards could pin the retired Reviewer-only name to both
# workers. The Coder cannot resolve a Reviewer-only skill from its role-scoped
# external_dirs, and Hermes rejects unknown --skills before kanban_show.
# Keep the Kanban Task unchanged; normalize ONLY this known legacy CLI pin.
LEGACY_REVIEW_PIN = "sdlc-review"
LEGACY_SKIP_MARKER = "DEVKIT_LEGACY_REVIEW_PIN_SKIP_V1"


def _normalize_legacy_pinned_skills(argv: list[str], profile: str, query_index: int) -> tuple[list[str], bool]:
    """Do not preload the legacy Reviewer-only skill in Coder.

    Other pins, including unknown names, are passed through unchanged so that
    Hermes continues to fail closed. Reviewer keeps its compatibility shim.
    Only CLI options before the -q/--query boundary are examined.
    """
    if profile != "coder":
        return list(argv), False

    normalized: list[str] = []
    skipped = False
    index = 0
    while index < len(argv):
        token = argv[index]
        if index < query_index and token in {"--skills", "-s"} and index + 1 < query_index:
            if argv[index + 1] == LEGACY_REVIEW_PIN:
                skipped = True
                index += 2
                continue
        if index < query_index and token == f"--skills={LEGACY_REVIEW_PIN}":
            skipped = True
            index += 1
            continue
        normalized.append(token)
        index += 1
    return normalized, skipped


def with_worker_startup(argv: list[str], profile: str) -> list[str]:
    if profile not in {"coder", "reviewer"}:
        return argv
    indices = [index for index, value in enumerate(argv) if value in {"-q", "--query"}]
    if len(indices) != 1 or indices[0] + 1 >= len(argv):
        raise RuntimeError("Kanban worker command must contain exactly one query")
    index = indices[0] + 1
    if MARKER in argv[index]:
        return argv
    result, legacy_skipped = _normalize_legacy_pinned_skills(argv, profile, indices[0])
    skill = "dev-implement-plan" if profile == "coder" else "dev-code-review"
    reminder = (
        f"\n\n[{MARKER}]\n"
        f"할당된 작업만 수행한다. 첫 kanban_show 결과를 재사용하고 skill_view(\"{skill}\")로 현재 역할 계약을 로드한다. "
        "Direct/Standard/Recovery/CHANGES_REQUESTED와 새/재개 세션에 같은 역할 계약을 적용한다. "
        "source mutation 전에 역할 Skill의 Session History / Provider별 Worker Context / Workspace Gate를 수행한다. "
        "Codex native shell은 Kanban ownership ENV가 scrub되므로 최초 kanban_show를 Worker Context 근거로 사용하고 Shell 환경변수 검사기를 호출하지 않는다. "
        "KANBAN_EXECUTION_BOUNDARY_V1에 따라 Kanban은 WHAT/STATE만 제공하며 launcher, timeout, retry, cache, process cleanup 같은 HOW는 역할 Skill과 canonical runtime/execution 정책에서 결정한다. "
        "Kanban Task body나 startup prompt를 실행정책의 source of truth로 사용하지 않는다."
    )
    if legacy_skipped:
        reminder += (
            f"\n[{LEGACY_SKIP_MARKER}] "
            "기존 Kanban Task의 Reviewer 전용 sdlc-review 사전 로드는 Coder에서만 제외한다. "
            "Task.skills 원본은 유지하고 Coder는 dev-implement-plan을 따른다. "
            "Reviewer 검토는 필수이며 다른 누락 Skill은 우회하지 않는다."
        )
    query_position = next(i for i, token in enumerate(result) if token in {"-q", "--query"}) + 1
    result[query_position] += reminder
    return result
