# dev-worktree-cleanup v0.2.1

legacy `dev-worktree-dispatch`가 만든 linked external worktree만 안전하게 제거하는 Orchestrator Skill입니다.

`dev-workspace-dispatch`가 인계한 user-approved workspace는 자동 정리하지 않습니다.

## 변경점

- 신규 기본 Branch 계약을 `feature/<TASK-KEY>`로 변경
- `--branch`는 Legacy Worktree 정리를 위해 유지
- Dirty/Untracked Worktree 삭제 거부, Kanban Terminal Gate, Safe Branch Delete 로직은 그대로 유지
- 문서 한글화

현재 Git/PR 단계가 없으므로 Reviewer 승인 직후 Worktree가 Dirty라면 Cleanup 거부가 정상입니다.
