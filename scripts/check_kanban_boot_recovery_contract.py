#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/devkit_kanban_boot_recovery.py"
BOOT = ROOT / "docker/cont-init.d/018-devkit-kanban-boot-recovery"
DOCKERFILE = ROOT / "Dockerfile"
COMPOSE = ROOT / "compose.yml"
SAMPLE = ROOT / "sample.env"
RUNTIME_VERIFY = ROOT / "scripts/verify-container-runtime.ps1"


def require(path: Path, terms: tuple[str, ...]) -> None:
    text = path.read_text(encoding="utf-8")
    missing = [term for term in terms if term not in text]
    if missing:
        raise SystemExit(f"{path.relative_to(ROOT)} missing boot-recovery terms: {', '.join(missing)}")


def forbid(path: Path, terms: tuple[str, ...]) -> None:
    text = path.read_text(encoding="utf-8")
    found = [term for term in terms if term in text]
    if found:
        raise SystemExit(f"{path.relative_to(ROOT)} contains forbidden boot-recovery terms: {', '.join(found)}")


def main() -> int:
    require(HELPER, (
        "DEVKIT_CONTAINER_RESTART",
        "PREVIOUS_INSTANTIATION_DEAD_WORKER",
        "DEAD_WORKER_CURRENT_EPOCH",
        "WORKER_FINGERPRINT_UNVERIFIED",
        "ASSIGNEE_PROFILE_UNAVAILABLE",
        "WORKSPACE_UNAVAILABLE",
        "current_instantiation_epoch",
        "kbd._worker_alive",
        "kb.reclaim_task",
        "include_archived=False",
        "--dry-run",
        "--self-test",
    ))
    forbid(HELPER, (
        "UPDATE tasks SET status",
        "subprocess.Popen",
        "spawn_worker(",
        "claim_task(",
        "claim_review_task(",
    ))

    require(BOOT, (
        "HERMES_KANBAN_BOOT_RECOVERY_ENABLED",
        "s6-setuidgid hermes",
        "/opt/devkit/bin/devkit_kanban_boot_recovery.py",
        "helper failed",
    ))

    require(DOCKERFILE, (
        "scripts/devkit_kanban_boot_recovery.py",
        "018-devkit-kanban-boot-recovery",
        "devkit_kanban_boot_recovery.py --self-test",
    ))

    require(COMPOSE, (
        "HERMES_KANBAN_BOOT_RECOVERY_ENABLED: ${HERMES_KANBAN_BOOT_RECOVERY_ENABLED:-true}",
    ))
    require(SAMPLE, (
        "HERMES_KANBAN_BOOT_RECOVERY_ENABLED=true",
    ))
    require(RUNTIME_VERIFY, (
        "Kanban boot recovery helper",
        "devkit_kanban_boot_recovery.py",
    ))

    print("PASS: Kanban boot recovery contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
