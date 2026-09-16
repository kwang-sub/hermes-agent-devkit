#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "custom-skills" / "orchestrator" / "git-workspace-cleanup"
SKILL = SKILL_ROOT / "SKILL.md"
WORKTREE_ONLY = SKILL_ROOT / "scripts" / "worktree_only.py"
LIST = SKILL_ROOT / "scripts" / "list_worktrees.py"
PREPARE = SKILL_ROOT / "scripts" / "prepare_cleanup.py"
CLEANUP = SKILL_ROOT / "scripts" / "cleanup_workspace.py"
LEGACY_TESTS = SKILL_ROOT / "tests" / "test_workspace_cleanup.py"
TRACKED_TESTS = SKILL_ROOT / "tests" / "test_tracked_branch_cleanup.py"


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
    if (ROOT / "custom-skills/orchestrator/dev-workspace-cleanup").exists():
        raise SystemExit("[FAIL] legacy dev-workspace-cleanup directory must be removed")

    skill = read(SKILL)
    worktree_only = read(WORKTREE_ONLY)
    listing = read(LIST)
    prepare = read(PREPARE)
    cleanup = read(CLEANUP)
    legacy_tests = read(LEGACY_TESTS)
    tracked_tests = read(TRACKED_TESTS)

    require(skill, (
        "name: git-workspace-cleanup", "/git-workspace-cleanup", "linked worktree 목록",
        "[Worktree 선택]", "[Worktree 정리 Preview]", "[Worktree 정리 승인]",
        "Tracked Previous Branch", "삭제 Branch:", "worktree-and-tracked-branch",
        "TRACKED_BRANCH_CLEANUP_ALLOWED=true", "TRACKED_PREVIOUS_BRANCH",
        "HEAD reflog", "GitHub merged PR + exact PR head SHA", "git-ancestor",
        "--delete-tracked-branch", "--delete-remote", "git update-ref -d",
        "git-pr-publish", "Preview에 이름을 표시하지 않은 branch 삭제",
    ), "git-workspace-cleanup skill")

    require(listing, (
        "worktree_snapshot(root)", "parse_worktrees(", "resolve_remote_head",
        "add_process_safe_directory", 'emit("LINKED_WORKTREES"',
        'emit("SELECTABLE_WORKTREES"', 'emit("WORKTREES_JSON"', "CLEANUP_SCOPE_HINT",
    ), "worktree selection helper")

    require(worktree_only, (
        "WorktreeOnlyInspection", "_previous_checkout_branch", '"git", "reflog", "show"',
        "checkout: moving from", "tracked_previous_branch", "tracked_previous_head_sha",
        "tracked_previous_merge_evidence", "tracked_previous_cleanup_allowed",
        "tracked_previous_remote_delete_available", "github_pull_requests",
        "branch_is_ancestor", "git-workspace-cleanup-worktree-only-v2",
        "the primary worktree cannot be removed by git-workspace-cleanup",
    ), "base-worktree previous-branch tracking")

    require(prepare, (
        "try_inspect_base_worktree", '"worktree-and-tracked-branch"',
        'emit("TRACKED_PREVIOUS_BRANCH"', 'emit("TRACKED_PREVIOUS_HEAD_SHA"',
        'emit("TRACKED_PREVIOUS_MERGE_EVIDENCE"',
        'emit("TRACKED_PREVIOUS_REMOTE_DELETE_AVAILABLE"',
        'emit("TRACKED_PREVIOUS_REASON"', 'emit("TRACKED_REFLOG_MESSAGE"',
        'emit("CLEANUP_FINGERPRINT"',
    ), "cleanup read-only helper")

    require(cleanup, (
        '"--delete-tracked-branch"', "tracked previous branch is not proven safe for deletion",
        '"update-ref", "-d"', '"worktree", "remove"', '"worktree", "prune"',
        "tracked local branch moved after cleanup approval",
        "tracked remote branch moved after cleanup approval",
        "push_delete_named_branch", "preserved-base", "cleanup fingerprint changed after approval",
    ), "cleanup mutation helper")

    forbid(cleanup, (
        "--force-with-lease", '"branch", "-D"', '"reset"', '"restore"',
        '"clean"', '"stash"', "rm -rf", '"config", "--global", "--add", "safe.directory"',
    ), "cleanup mutation helper")

    require(legacy_tests, (
        "test_lists_linked_worktree_with_branch_and_remote",
        "test_base_branch_linked_worktree_is_ready_for_worktree_only_cleanup",
        "test_cleanup_can_delete_matching_remote_branch_after_approval",
        "test_primary_worktree_is_blocked", "test_dirty_worktree_is_blocked",
    ), "existing cleanup regression tests")

    require(tracked_tests, (
        "test_preflight_tracks_previous_merged_branch_from_head_reflog",
        "test_worktree_only_choice_preserves_tracked_branch",
        "test_approved_tracked_local_branch_is_deleted_by_exact_sha",
        "test_approved_tracked_remote_branch_is_deleted_but_base_is_preserved",
        "test_unmerged_previous_branch_is_not_offered_for_deletion",
    ), "tracked previous branch regression tests")

    print("[PASS] git-workspace-cleanup list/selection + reflog previous-branch preview/approval + exact-ref/no-force contract verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
