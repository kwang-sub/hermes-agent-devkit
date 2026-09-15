#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "custom-skills" / "orchestrator" / "dev-workspace-cleanup"
SKILL = SKILL_ROOT / "SKILL.md"
LIB = SKILL_ROOT / "scripts" / "cleanup_lib.py"
LIST = SKILL_ROOT / "scripts" / "list_worktrees.py"
PREPARE = SKILL_ROOT / "scripts" / "prepare_cleanup.py"
CLEANUP = SKILL_ROOT / "scripts" / "cleanup_workspace.py"
TESTS = SKILL_ROOT / "tests" / "test_workspace_cleanup.py"


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
    listing = read(LIST)
    prepare = read(PREPARE)
    cleanup = read(CLEANUP)
    tests = read(TESTS)

    require(
        skill,
        (
            "name: dev-workspace-cleanup",
            "[Worktree 목록]",
            "[Worktree 선택]",
            "[Worktree 정리 Preview]",
            "[Worktree 정리 승인]",
            "Worktree + 로컬/원격 Branch 정리",
            "github-pr-merged",
            "git-ancestor",
            "CLEANUP_FINGERPRINT",
            "git update-ref -d",
            "--delete-remote",
            "Partial Failure",
            "dev-pr-publish",
        ),
        "dev-workspace-cleanup skill",
    )
    require(
        listing,
        (
            "worktree_snapshot(root)",
            "parse_worktrees(",
            'emit("LINKED_WORKTREES"',
            'emit("SELECTABLE_WORKTREES"',
            'emit("WORKTREES_JSON"',
            "remote_branch_sha",
        ),
        "worktree selection helper",
    )
    require(
        library,
        (
            '["git", "worktree", "list", "--porcelain"]',
            "the primary worktree cannot be removed by dev-workspace-cleanup",
            "worktree contains modified or untracked files",
            "branch still has an open pull request",
            "local HEAD differs from",
            "github-pr-merged",
            "git-ancestor",
            "remote_delete_supported",
            "dev-workspace-cleanup-v1",
        ),
        "cleanup preflight library",
    )
    require(
        prepare,
        (
            'emit("REMOTE_BRANCH"',
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
            "remote branch moved after cleanup approval",
            "cleanup fingerprint changed after approval",
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
            "test_lists_linked_worktree_with_branch_and_remote",
            "test_open_pr_is_blocked",
            "test_merged_pr_allows_squash_style_cleanup_evidence",
            "test_cleanup_can_delete_matching_remote_branch_after_approval",
            "test_fingerprint_change_blocks_cleanup_before_mutation",
            "test_primary_worktree_is_blocked",
            "test_dirty_worktree_is_blocked",
        ),
        "cleanup regression tests",
    )

    print("[PASS] Workspace cleanup list-selection, merge-evidence, exact-ref deletion, remote-branch approval, and no-force safety contract verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
