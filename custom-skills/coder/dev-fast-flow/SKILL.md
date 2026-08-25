---
name: dev-fast-flow
description: 명확하고 작은 단일 Repository 작업을 Coder 대화에서 Kanban에 self-dispatch하고 worker가 risk에 따라 완료 또는 reviewer 인계한다.
version: 0.2.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, coder, fast-flow, kanban, review, intake]
    related_skills: [dev-implement-plan, dev-code-review, dev-review-cycle]
    requires_tools: [terminal, clarify]
---

# dev-fast-flow

Coder 프로필에 직접 들어온 작고 명확한 작업을 Orchestrator 없이 Kanban worker로 넘기는 **intake/router**다. Interactive Coder는 source를 수정하지 않는다.

```text
User → Coder intake → Kanban → Coder worker
                            ├─ Review Risk LOW → done
                            └─ REVIEW_REQUIRED → Reviewer
```

## 적용 조건
다음을 모두 만족해야 한다.
- managed 단일 Repository가 명확함
- 작은 기존 패턴 기반 변경
- clean current branch
- architecture/product/public API/DB schema/dependency/cross-repo 결정 불필요
- 완료 조건과 검증 방법이 명확함

대표 후보: 작은 버그/null/edge-case, 기존 validation, 로그/메시지, 단순 Repository 수정, 테스트 보완, 문서/주석, 작은 리팩터링.

다음은 Standard Flow로 보낸다: project/workspace 모호성, dirty workspace, 새 branch/worktree, 신규 기능 설계, multi-repo/module 영향, API/schema/dependency/transaction/security/concurrency 정책 결정, 복수 해석 요구사항.

## Intake 계약
`<repo>/.hermes/project.yaml`, clean status, current branch, Base SHA를 확인하고 최소한 다음을 Kanban에 남긴다.

```text
Flow: FAST
Task Key
Goal
Acceptance Criteria
Implementation Tasks
Test Plan
Known Risks
Workspace / Expected Branch / Base SHA
Reviewer Profile
Review Policy: RISK_BASED
```

Task 생성은 `scripts/create_fast_task.py`를 사용한다. 성공 후 Interactive Coder는 멈추고 Gateway가 `dev-implement-plan` worker를 실행한다.

## Worker 결과
- 실제 source에서 Fast Flow 범위를 벗어나면 `FAST_FLOW_ESCALATION_REQUIRED`로 Block.
- 구현/검증 후 `dev-implement-plan`의 Review Risk 기준을 적용.
- `LOW`면 Coder가 근거/verification을 남기고 `kanban_complete`.
- `REVIEW_REQUIRED`면 configured reviewer에게 `kanban_request_review`.
- `CHANGES_REQUESTED` 재작업은 항상 다시 Reviewer에게 보낸다.

## 불변식
- intake 세션은 source를 직접 수정하지 않는다.
- risk 판정 때문에 검증을 생략하지 않는다.
- LOW를 파일 수만으로 판정하지 않는다.
- branch/worktree 생성, dirty 상태 정리, commit/push/PR/merge 금지.
- 애매하면 LOW가 아니라 REVIEW_REQUIRED 또는 Standard Flow를 선택한다.