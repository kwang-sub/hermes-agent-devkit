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
CODER_DETAILS = ROOT / "custom-skills/coder/dev-implement-plan/references/implementation-details.md"
CODER_ENV_GATE = ROOT / "custom-skills/coder/dev-implement-plan/scripts/verify_worker_context.py"
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
    source = require(REFERENCE, POLICY)
    for heading in (
        "## 1. Kanban이 소유하는 WHAT / STATE",
        "## 2. Kanban이 소유하지 않는 HOW",
        "## 3. Worker startup adapter",
        "## 4. Workflow / Execution 계층",
    ):
        if heading not in source:
            raise AssertionError(f"{REFERENCE.relative_to(ROOT)} missing section: {heading}")


def check_startup_adapter() -> None:
    source = require(STARTUP, POLICY)
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


def check_provider_context_gate() -> None:
    """Prevent a Codex shell ENV probe from silently returning to Coder flows."""
    require(CODER,
        "WORKER_CONTEXT_PROVIDER_GATE_V2",
        "openai-codex",
        "kanban_show",
        "current_run_id",
        "worker_context",
        "Codex native shell에서",
        "verify_worker_context.py",
        "--worker-provider",
        "WORKER_CONTEXT_BLOCKER=WRONG_VERIFICATION_PATH",
        "CHANGES_REQUESTED",
    )
    require(CODER_DETAILS,
        "WORKER_CONTEXT_PROVIDER_GATE_V2",
        "openai-codex",
        "verify_worker_context.py",
        "WORKER_CONTEXT_PROVIDER_UNVERIFIED",
        "WRONG_VERIFICATION_PATH",
        "kanban_show",
    )
    require(CODER_ENV_GATE,
        "--worker-provider",
        "HERMES_DELEGATED_CHILD_CONTEXT",
        "WrongVerificationPath",
        "WORKER_CONTEXT_BLOCKER=WRONG_VERIFICATION_PATH",
    )
    reminder = read(STARTUP)
    if "Codex native shell" not in reminder or "kanban_show" not in reminder:
        raise AssertionError("Worker startup must remind Codex of the upstream context route")
    if "verify_worker_context.py" in reminder or "HERMES_KANBAN_TASK=" in reminder:
        raise AssertionError("Worker startup must not grant or probe Kanban ownership in shell")


def check_contract_consumers() -> None:
    for path in (DISPATCH, WORKFLOW, CODER, REVIEWER, CYCLE, AGENTS):
        require(path, POLICY)

    for path in (DISPATCH, WORKFLOW, CODER, REVIEWER, CYCLE):
        if "kanban-execution-boundary.md" not in read(path):
            raise AssertionError(f"{path.relative_to(ROOT)} must reference the canonical boundary document")

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
    check_provider_context_gate()
    check_contract_consumers()
    print("PASS: Kanban owns WHAT/STATE; role/runtime execution owns HOW")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
