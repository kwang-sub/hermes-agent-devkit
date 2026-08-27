---
name: dev-fast-flow
description: 명확하고 작은 단일 Repository 작업을 Coder 대화에서 Kanban에 self-dispatch하고 worker가 risk에 따라 완료 또는 reviewer 인계한다.
version: 0.3.0
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
- current branch에서 작업 가능
- 기존 변경이 있으면 그대로 보존하며 작업 가능
- architecture/product/public API/DB schema/dependency/cross-repo 결정 불필요
- 완료 조건과 검증 방법이 명확함

대표 후보: 작은 버그/null/edge-case, 기존 validation, 로그/메시지, 단순 Repository 수정, 테스트 보완, 문서/주석, 작은 리팩터링.

다음은 Standard Flow로 보낸다: project/workspace 모호성, 기존 변경을 안전하게 보존하기 어려움, 새 branch/worktree, 신규 기능 설계, multi-repo/module 영향, API/schema/dependency/transaction/security/concurrency 정책 결정, 복수 해석 요구사항.

## Fast Intake Budget
Intake의 책임은 **구현 분석이 아니라 eligibility 판정과 dispatch**다.

- 사용자가 대상 파일/클래스를 명시했고 작은 로컬 변경이면 repository-wide `find`/`grep`부터 수행하지 않는다.
- docs/comment/log/message/null/validation처럼 Fast 적합성이 명확한 작업은 대상 존재 여부와 요구사항 명확성만 확인한다.
- 구현 세부사항, dependency 흐름, 테스트 내부 구현 분석은 `dev-implement-plan` worker의 책임이다.
- `create_fast_task.py`가 수행하는 `project.yaml`, branch, Base SHA, effective dirty baseline 검사를 사전에 중복 실행하지 않는다.
- 정상 경로에서는 `create_fast_task.py` 자체를 읽거나 분석하지 않는다. 스크립트가 실패했을 때만 오류 원인에 필요한 최소 범위를 확인한다.
- 직전 대화에서 동일 요청의 source 분석과 Fast Flow 적합성 판정이 완료됐다면 그 결과를 Goal/Acceptance/Implementation/Test Plan으로 재사용하고 source를 다시 조사하지 않는다.
- dispatch 성공 후 Interactive Coder는 추가 source 조사 없이 종료한다.

## Verification Mode
Task 생성 시 변경 성격에 맞는 최소 검증 모드를 명시한다.

- `DOCS`: Markdown/문서 등 실행 코드 미변경. scoped change verification만 수행한다.
- `COMPILE`: JavaDoc/주석 등 실행 의미를 바꾸지 않는 source 변경. 프로젝트 compile 검증을 기본으로 한다.
- `TARGETED_TEST`: 실행 로직 변경. 관련 targeted test를 기본으로 한다.

사용자가 더 강한 검증을 명시하면 그 요구를 우선한다. 변경 성격이 불분명하면 `TARGETED_TEST`를 선택한다.

## Intake 계약
`<repo>/.hermes/project.yaml`, current branch, Base SHA와 effective Git changes는 `scripts/create_fast_task.py`가 검증/계산한다. Interactive Coder가 같은 검사를 수동으로 재현하지 않는다.

Windows Host bind mount에서는 Host checkout의 CRLF와 Linux Git의 LF index 비교 때문에 raw `git status`가 대량 `M`을 표시할 수 있다. 따라서 raw status의 modified-file 개수만으로 dirty 여부를 판정하거나 사용자에게 중단 확인을 요청하지 않는다.

Effective change 규칙:
- unstaged tracked: `git diff --ignore-cr-at-eol`에서 남는 변경만 실제 변경
- staged: 항상 실제 변경
- untracked: 항상 실제 변경
- CRLF/LF 차이만 있는 tracked 파일: EOL-only noise로 기록하되 dirty baseline에서는 제외

Kanban에는 최소한 다음을 남긴다.

```text
Flow: FAST
Task Key
Verification Mode
Goal
Acceptance Criteria
Implementation Tasks
Test Plan
Known Risks
Workspace / Expected Branch / Base SHA
Workspace dirty at dispatch
Ignored tracked EOL-only changes at dispatch
Pre-existing effective changes
Reviewer Profile
Review Policy: RISK_BASED
```

Task 생성은 `scripts/create_fast_task.py`를 사용한다. 스크립트는 workspace를 Git `safe.directory`로 idempotent하게 등록한다. 기존 effective 변경은 baseline으로 기록할 뿐 stash/reset/clean/restore하지 않는다. 성공 후 Interactive Coder는 멈추고 Gateway가 `dev-implement-plan` worker를 실행한다.

동일 Base SHA에서도 요청 spec(title/goal/acceptance/implementation/test/risk/verification mode)이 다르면 별도 request fingerprint를 사용해 후속 작업을 새 Task로 생성한다. 정확히 같은 요청의 재시도는 같은 idempotency key를 유지한다.

## Worker 결과
- 실제 source에서 Fast Flow 범위를 벗어나면 `FAST_FLOW_ESCALATION_REQUIRED`로 Block.
- 구현/검증 후 `dev-implement-plan`의 Review Risk 기준을 적용.
- `LOW`면 Coder가 근거/verification을 남기고 `kanban_complete`.
- `REVIEW_REQUIRED`면 configured reviewer에게 `kanban_request_review`.
- `CHANGES_REQUESTED` 재작업은 항상 다시 Reviewer에게 보낸다.

## 불변식
- intake 세션은 source를 직접 수정하지 않는다.
- intake에서 worker 수준의 상세 source 분석을 선행하지 않는다.
- 기존 사용자 변경을 덮어쓰거나 reset/restore/clean/stash하지 않는다.
- raw `git status`의 EOL noise를 사용자 변경으로 오인하지 않는다.
- risk 판정 때문에 검증을 생략하지 않는다.
- LOW를 파일 수만으로 판정하지 않는다.
- branch/worktree 생성, commit/push/PR/merge 금지.
- 애매하면 LOW가 아니라 REVIEW_REQUIRED 또는 Standard Flow를 선택한다.
