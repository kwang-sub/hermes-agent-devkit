#!/usr/bin/env python3
"""Enforce the Kanban WHAT/STATE versus runtime HOW responsibility boundary."""
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY = "KANBAN_EXECUTION_BOUNDARY_V1"
REFERENCE = ROOT / "shared/references/kanban-execution-boundary.md"
STARTUP = ROOT / "scripts/devkit_worker_startup.py"
PATCH = ROOT / "scripts/patch_hermes_kanban_session_affinity.py"
DISPATCH = ROOT / "custom-skills/orchestrator/dev-workspace-dispatch/SKILL.md"
WORKFLOW = ROOT / "custom-skills/orchestrator/dev-workflow-orchestrate/SKILL.md"
CODER = ROOT / "custom-skills/coder/dev-implement-plan/SKILL.md"
REVIEWER = ROOT / "custom-skills/reviewer/dev-code-review/SKILL.md"
CYCLE = ROOT / "custom-skills/coder/dev-review-cycle/SKILL.md"
AGENTS = ROOT / "AGENTS.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def require(path: Path, *terms: str) -> str:
    source = read(path)
    missing = [term for term in terms if term not in source]
    if missing:
        raise AssertionError(f"{path.relative_to(ROOT)} missing boundary terms: {missing}")
    return source


def check_reference() -> None:
    require(
        REFERENCE,
        POLICY,
        "WHAT / STATE",
        "Kanban이 소유하지 않는 HOW",
        "실제 executable / launcher / wrapper 경로",
        "timeout 기본값",
        "retry 횟수",
        "process group TERM/KILL/reap",
        "cache / repository / store",
        "Worker startup adapter",
        "Task status/body/comment",
        "Execution Policy",
    )


def check_startup_adapter() -> None:
    source = require(
        STARTUP,
        POLICY,
        "Kanban은 WHAT/STATE만 제공",
        "역할 Skill과 canonical runtime/execution 정책",
    )
    forbidden = (
        "/usr/local/bin/hermes-maven",
        "maven_verification.py",
        "maven_verification_cached.py",
        "gradle_verification.py",
        "gradle_verification_cached.py",
        "node_runtime.py",
        "/opt/data/maven",
        "/opt/data/gradle",
        "hermes-java ./mvnw",
        "compile 300",
        "verify 600",
    )
    leaked = [term for term in forbidden if term in source]
    if leaked:
        raise AssertionError(f"worker startup leaked runtime HOW: {leaked}")

    spec = importlib.util.spec_from_file_location("devkit_worker_startup_boundary_test", STARTUP)
    if spec is None or spec.loader is None:
        raise AssertionError("cannot load worker startup adapter")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    base = ["hermes", "chat", "-q", "work kanban task t_demo"]
    coder = module.with_worker_startup(base, "coder")
    reviewer = module.with_worker_startup(base, "reviewer")
    untouched = module.with_worker_startup(base, "orchestrator")

    coder_query = coder[coder.index("-q") + 1]
    reviewer_query = reviewer[reviewer.index("-q") + 1]
    if POLICY not in coder_query or 'skill_view("dev-implement-plan")' not in coder_query:
        raise AssertionError("coder startup does not delegate to role contract")
    if POLICY not in reviewer_query or 'skill_view("dev-code-review")' not in reviewer_query:
        raise AssertionError("reviewer startup does not delegate to role contract")
    if untouched != base:
        raise AssertionError("non-worker profile must not be mutated")
    if module.with_worker_startup(coder, "coder") != coder:
        raise AssertionError("worker startup adapter must remain idempotent")


def check_contract_consumers() -> None:
    require(
        DISPATCH,
        POLICY,
        "kanban-execution-boundary.md",
        "Task body는 WHAT/STATE",
        "실제 실행법은 역할 Skill과 shared runtime/execution 정책",
    )
    require(
        WORKFLOW,
        POLICY,
        "Plan Approval",
        "launcher path, timeout, retry, cache, process cleanup",
        "역할 Skill/공통 Execution 계층",
    )
    require(CODER, POLICY, "Kanban은 WHAT/STATE의 source of truth", "canonical runtime/execution 정책")
    require(REVIEWER, POLICY, "Kanban에서 requirement/AC/state/evidence", "canonical runtime/execution 정책")
    require(CYCLE, POLICY, "runtime HOW는 Kanban state에서 읽지 않는다")
    require(AGENTS, POLICY, "Kanban은 WHAT/STATE", "Task body나 worker startup prompt")

    patch_source = read(PATCH)
    for leaked in (
        "/usr/local/bin/hermes-maven",
        "maven_verification.py",
        "gradle_verification.py",
        "node_runtime.py",
    ):
        if leaked in patch_source:
            raise AssertionError(f"Kanban dispatcher patch contains runtime HOW: {leaked}")


def main() -> int:
    check_reference()
    check_startup_adapter()
    check_contract_consumers()
    print("PASS: Kanban owns WHAT/STATE; role/runtime execution owns HOW")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
