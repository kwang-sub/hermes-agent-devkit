# dev-worktree-dispatch v0.4.1 (deprecated)

> Legacy linked-worktree migration 전용입니다. 신규 Dispatch에는 `dev-workspace-dispatch`를 사용하십시오.

기존 `dev-breakdown`의 `READY` 계획을 외부 Worktree와 Kanban Task로 Dispatch하던 호환성용 orchestrator Skill입니다.

## v0.4.0 변경점

요청된 변경만 반영했습니다.

- Branch 기본 규칙을 `wt/<task-key>`에서 `feature/<TASK-KEY>`로 변경
- Task 제목 slug를 Branch에 붙이지 않음
- 사용자 Plan 승인 전 Dispatch 금지 규칙 명시
- 기존 `--branch` 인자는 호환성 확인용으로 유지하지만 `feature/<TASK-KEY>`와 다르면 실패
- 기존 외부 상대경로 Worktree, Kanban 생성/검증, 재시도 안전성 로직은 유지
- 문서 한글화

## Branch / Worktree

```text
Task Key: CALC-001
Branch: feature/CALC-001
Worktree: /workspace/.worktrees/mini-calculator/CALC-001
```

## Helper

```bash
python3 "${HERMES_SKILL_DIR}/scripts/prepare_dispatch.py" \
  --task-key "CALC-001"
```

예상 핵심 출력:

```text
TASK_KEY=CALC-001
BRANCH=feature/CALC-001
STATUS=prepared
```

## 주의

이 Skill은 코드를 구현하거나 commit/push하지 않습니다.
