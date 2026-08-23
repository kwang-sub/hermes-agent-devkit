---
name: dev-worktree-cleanup
description: Legacy linked worktree만 명시적으로 안전하게 정리한다.
version: 0.2.1
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, git, worktree, cleanup, orchestrator, safety, legacy]
    related_skills: [dev-worktree-dispatch]
    requires_tools: [terminal, kanban_show]
---

# dev-worktree-cleanup

`dev-worktree-dispatch`가 만든 legacy linked external worktree를 안전하게 정리한다.

이 Skill은 **orchestrator / 명시적 사람 제어 완료 단계**에서 사용한다.

`dev-workspace-dispatch`가 인계한 user-approved workspace는 이 Skill의 대상이 아니다. 특히 현재 checkout, 사용자가 지정한 별도 repository root, `Workspace Contract`의 `dir:<approved-workspace>`를 자동 제거하거나 정리하지 않는다.

의도적으로 매우 보수적으로 동작한다.

---

# 1. 현재 Workflow 경계

현재 Git/PR Publication은 아직 구현되지 않았다.

따라서 Reviewer가 `APPROVED`한 Kanban Task에도 미커밋 구현 변경이 남아 있을 수 있다.

그 상태에서는:

```text
cleanup = REFUSE
```

승인되었지만 아직 Git으로 보존되지 않은 코드를 삭제하지 않는다.

향후 Git 단계가 Commit 등으로 작업을 보존했거나, 사용자가 이 Skill 밖에서 해당 작업을 명시적으로 폐기한 경우에만 정상 Cleanup 대상이 될 수 있다.

---

# 2. 사전 조건

정상 Cleanup은 다음을 모두 요구한다.

- 대상이 legacy `dev-worktree-dispatch`가 만든 linked worktree임
- 프로젝트 `.hermes/project.yaml` 존재
- Task Worktree가 설정된 External Path와 일치
- Linked Worktree가 Source Repository 소속
- 예상 Task Branch가 Checkout되어 있음
- Kanban Task 상태가 `done` 또는 `archived`
- Tracked Modification이 **0개**
- Untracked File이 **0개**

이 Skill에는 Force Mode가 없다.

---

# 3. 실행

Source Repository 기준:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/cleanup_worktree.py" \
  --repo "/workspace/dashboard" \
  --task-key "CALC-001" \
  --task-id "t_abcd1234"
```

기본 Branch:

```text
feature/<TASK-KEY>
```

예:

```text
feature/CALC-001
```

이전 규칙으로 생성된 Legacy Worktree를 정리해야 할 때만 명시적으로 다음을 사용할 수 있다.

```bash
--branch "<legacy-or-explicit-branch>"
```

기본적으로 Local Branch는 유지한다.

Worktree 제거가 Unmerged Commit까지 함께 파괴해서는 안 되기 때문이다.

---

# 4. Branch 정리

선택적 안전 삭제:

```bash
--delete-branch-if-merged
```

Helper는 Task Branch가 설정된 Base Branch의 ancestor임을 Git이 증명할 때만 Branch를 삭제한다.

그 외에는:

```text
BRANCH_ACTION=kept-not-merged
```

Force Delete는 하지 않는다.

---

# 5. Idempotency

예상 Worktree Path가 이미 없고 Git Worktree List에도 없으면:

```text
STATUS=already-clean
```

성공한 Idempotent Cleanup으로 처리한다.

---

# 6. Kanban Gate

Helper는 `.hermes/project.yaml`에서 Board를 읽고 다음을 확인한다.

```bash
hermes kanban --board <board> show <task-id> --json
```

허용 상태:

```text
done
archived
```

다른 상태에서는 Cleanup을 막는다.

Orchestration Skill도 Helper 호출 전 `kanban_show`로 사람이 읽을 수 있는 Task 상태를 확인하는 것을 권장한다.

---

# 7. Dirty Worktree

다음 명령 결과가 하나라도 있으면 Cleanup을 거부한다.

```bash
git status --porcelain=v1 --untracked-files=all
```

예:

```text
ERROR: worktree has unpublished/uncommitted changes; cleanup refused
```

다음 명령으로 우회하지 않는다.

```text
git reset --hard
git clean -fd
git worktree remove --force
```

이 명령들은 이 Skill의 범위 밖이다.

---

# 8. Cleanup 동작

모든 Gate가 통과되면:

```text
git worktree remove <target>
git worktree prune
```

그 후 옵션이 지정된 경우에만 Merged Branch를 안전 삭제한다.

Source Checkout은 변경하지 않는다.

---

# 9. 안전 규칙

절대 하지 않는다.

- Dirty Worktree 삭제
- Worktree Force Remove
- Source/Worktree reset 또는 clean
- Unmerged Branch 삭제
- Source Repository 삭제
- `.worktrees` 전체 정리
- Project Metadata 밖의 Task Path 추론
- `dev-workspace-dispatch`의 user-approved workspace 자동 정리

---

# 10. 성공 출력

예:

```text
PROJECT_ID=dashboard
TASK_KEY=CALC-001
TASK_ID=t_abcd1234
WORKTREE_PATH=/workspace/.worktrees/dashboard/CALC-001
BRANCH=feature/CALC-001
KANBAN_STATUS=done
WORKTREE_ACTION=removed
BRANCH_ACTION=kept
STATUS=cleaned
```
