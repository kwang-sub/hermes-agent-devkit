# dev-workflow-orchestrate v0.1.1

Orchestrator의 **개발 Workflow 최상위 진입점**입니다.

사용자는 Jira Ticket 또는 일반 Text Request로 시작할 수 있습니다.

## 전체 흐름

```text
Jira Ticket / Text Request
        ↓
Common Work Item
        ↓
Project 결정
        ↓
[Human Gate #1]
Resolver가 추론한 경우 사용자 Project 승인
        ↓
dev-breakdown
        ↓
[Human Gate #2]
모든 Implementation Plan 사용자 승인
        ↓
dev-workspace-dispatch
        ↓
current approved branch 또는 feature/<TASK-KEY>
        ↓
coder ↔ reviewer
        ↓
APPROVED / BLOCKED
```

## 승인 규칙

### Project Gate

```text
사용자가 정확한 Managed Project를 직접 지정
→ Gate #1 생략

Resolver가 Project를 추론
→ RESOLVED_SINGLE이어도 반드시 사용자 확인
```

### Plan Gate

```text
dev-breakdown = READY
→ 아직 Dispatch 금지
→ 사용자에게 Plan 제시
→ 승인 후 Dispatch
```

## Workspace / Branch

```text
Task Key: CALC-001
Branch: feature/CALC-001
Workspace: 사용자 승인 Git workspace
```

Task 제목이나 설명은 Branch에 붙이지 않습니다.

## Git 경계

현재 Workflow는 commit/push/PR/merge를 수행하지 않습니다.

Reviewer 승인 후에도 Workspace를 자동 Cleanup하지 않습니다.

## 설치

External Skill Directory:

```text
/opt/custom-skills/orchestrator/dev-workflow-orchestrate
```

또는 Profile Skill 영역:

```text
/opt/data/profiles/orchestrator/skills/dev-workflow-orchestrate
```
