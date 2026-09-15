#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "custom-skills" / "orchestrator" / "dev-worktree-cleanup"
SKILL = SKILL_ROOT / "SKILL.md"
LIB = SKILL_ROOT / "scripts" / "cleanup_lib.py"
PREPARE = SKILL_ROOT / "scripts" / "prepare_cleanup.py"
CLEANUP = SKILL_ROOT / "scripts" / "cleanup_worktree.py"
TESTS = SKILL_ROOT / "tests" / "test_worktree_cleanup.py"


def read(path: Path) -> str:
    if not path.is_file():
        raise SystemExit(f"[FAIL] missing file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8-sig")


def require(text: str, terms: tuple[str, ...], label: str) -> None:
    missing = [term for term in terms if term not in text]
    if missing:
        raise SystemExit(f"[FAIL] {label} missing required terms: {', '.join(missing)}")


def forbid(text: str, terms: tuple[str, ...], label: str) -> None:
    present = [term for term in terms if term in text]
    if present:
        raise SystemExit(f"[FAIL] {label} contains forbidden terms: {', '.join(present)}")


def main() -> int:
    skill = read(SKILL)
    library = read(LIB)
    prepare = read(PREPARE)
    cleanup = read(CLEANUP)
    tests = read(TESTS)

    require(
        skill,
        (
            "name: dev-worktree-cleanup",
            "read-only cleanup preflight",
            "[Worktree 정리 Preview]",
            "[Worktree 정리 승인]",
            "github-pr-merged",
            "git-ancestor",
            "CLEANUP_FINGERPRINT",
            "git update-ref -d",
            "--delete-remote",
            "Partial Failure",
            "dev-pr-publish",
        ),
        "dev-worktree-cleanup skill",
    )
    require(
        library,
        (
            "the primary worktree cannot be removed",
            "worktree contains modified or untracked files",
            "branch still has an open pull request",
            "local HEAD differs from",
            "github-pr-merged",
            "git-ancestor",
            "remote_delete_supported",
            "dev-worktree-cleanup-v1",
        ),
        "cleanup preflight library",
    )
    require(
        prepare,
        (
            'emit("MERGE_EVIDENCE"',
            'emit("REMOTE_DELETE_AVAILABLE"',
            'emit("CLEANUP_FINGERPRINT"',
        ),
        "cleanup read-only helper",
    )
    require(
        cleanup,
        (
            '"worktree", "remove"',
            '"update-ref", "-d"',
            '"worktree", "prune"',
            'remote branch moved after cleanup approval',
            'cleanup fingerprint changed after approval',
            'emit("STATUS", "partial")',
        ),
        "cleanup mutation helper",
    )
    forbid(
        cleanup,
        (
            "--force",
            "force-with-lease",
            '"branch", "-D"',
            '"reset"',
            '"restore"',
            '"clean"',
            '"stash"',
            "rm -rf",
        ),
        "cleanup mutation helper",
    )
    require(
        tests,
        (
            "test_open_pr_is_blocked",
            "test_merged_pr_allows_squash_style_cleanup_evidence",
            "test_cleanup_can_delete_remote_branch_after_approval",
            "test_fingerprint_change_blocks_cleanup_before_mutation",
            "test_main_worktree_is_blocked",
            "test_dirty_worktree_is_blocked",
        ),
        "cleanup regression tests",
    )

    print("[PASS] Worktree cleanup approval, merge-evidence, exact-ref deletion, and no-force safety contract verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
