---
name: dev-fast-flow
description: Coder 대화에서 DIRECT/FAST/STANDARD_REQUIRED를 판정하고 FAST 선택 시 Kanban에 self-dispatch하며 worker가 risk에 따라 완료 또는 reviewer 인계한다.
version: 0.4.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, coder, fast-flow, direct, kanban, review, intake]
    related_skills: [dev-direct-flow, dev-implement-plan, dev-code-review, dev-review-cycle]
    requires_tools: [terminal, clarify]
---

# dev-fast-flow

Interactive Coder의 개발 요청을 `DIRECT | FAST | STANDARD_REQUIRED`로 분류하는 **execution router**다. FAST를 선택한 경우에만 Kanban worker로 self-dispatch한다.

```text
User → Coder execution gate
        ├─ DIRECT → Interactive Coder 직접 수행
        ├─ FAST → Kanban → Coder worker
        │                    ├─ Review Risk LOW → done
        │                    └─ REVIEW_REQUIRED → Reviewer
        └─ STANDARD_REQUIRED → Orchestrator 안내 → STOP
```

## EXECUTION SAFETY GATE — MUST RUN FIRST
이 Gate는 다른 Skill 로드, plan 생성, source read/grep/find, build/test보다 먼저 판정한다.

1. 현재 세션에 실제 Kanban Task ID가 있고 worker로 실행된 세션인가?
   - YES: 할당된 Task를 수행한다. 아래 Interactive Gate를 다시 묻지 않는다.
   - NO: Interactive Coder로 간주하고 2번으로 진행한다.
2. 사용자의 요청을 최소 정보만으로 `DIRECT | FAST | STANDARD_REQUIRED` 후보로 분류한다.
   - DIRECT 후보: 대상이 명확한 초소형 저위험 변경. 대체로 1~3개 파일, 기존 패턴 그대로, API/schema/dependency/DB/transaction/security/concurrency/common architecture 영향 없음, 짧은 검증으로 충분함.
   - FAST 후보: managed 단일 Repository/current branch의 작은 기존 패턴 기반 작업이지만 별도 worker 격리/추적이 유리함. 범위가 불명확하거나 여러 호출 흐름 분석이 먼저 필요하면 DIRECT보다 FAST를 우선한다.
   - STANDARD_REQUIRED: 신규 기능/설계, multi-module/repo, API/request/response schema, DB schema, dependency, transaction/security/concurrency/common architecture 정책 결정, 복수 해석 요구사항.
3. 현재 사용자 메시지에 명시적인 실행 선택이 있는가?
   - DIRECT 승인 예: `직접 수정`, `DIRECT로 진행`, `바로 수정`.
   - FAST 승인 예: `FAST Flow로 진행`, `칸반으로 진행`, `/dev-fast-flow ...`.
   - Standard 요청: `Standard Flow로 진행`, `/dev-standard-flow ...`는 Coder 직접 실행 승인이 아니다. `STANDARD_REQUIRED`로 안내하고 Orchestrator에서 진행하도록 말한 뒤 STOP한다.
   - 명시적 선택이 없으면 `clarify`로 가능한 선택지를 제시하고 즉시 STOP한다.
4. `clarify` 선택지는 판정 결과에 따라 최소화한다.
   - DIRECT 가능 + FAST 가능: `직접 수정`, `FAST Flow로 진행`, `분석만 진행`, `취소`. DIRECT 또는 FAST 중 하나를 Recommended로 표시한다.
   - FAST만 가능: `FAST Flow로 진행`, `분석만 진행`, `취소`.
   - STANDARD_REQUIRED: 실행 선택지를 묻지 않고 Orchestrator에서 Standard Flow로 진행해야 한다고 안내하고 STOP한다.
5. 다음은 실행 승인으로 절대 간주하지 않는다.
   - 동일 요청의 반복
   - 요청 문구 수정/보완
   - 추가 요구사항 전달
   - 파일 재첨부 또는 `@file` 재지정
   - 질문/요청의 재입력
6. 승인 대기 중 5번 유형의 메시지가 오면 최신 요구사항으로만 갱신하고 다시 `clarify`한 뒤 STOP한다. 암묵적 동의를 추론하지 않는다.
7. 승인 전 Interactive turn에서 허용되는 실행 action은 `clarify` 하나뿐이다. `clarify` 전후로 Spring/Gradle/구현 capability Skill 로드, plan/read/grep/find/write/patch/build/test/Kanban create를 실행하지 않는다.
8. DIRECT 선택 시 `dev-direct-flow` 계약으로 전환해 현재 Interactive Coder가 직접 구현한다. FAST 선택 시 아래 Fast Intake 계약에 따라 dispatch만 수행하고 STOP한다.

## DIRECT 판정 기준
다음을 모두 만족할 때만 DIRECT를 제시한다.

- managed 단일 Repository와 대상 파일/영역이 명확함
- current workspace/current branch 유지 가능
- 예상 변경이 대체로 1~3개 파일의 초소형 변경
- 기존 프로젝트 패턴 그대로 적용 가능
- public API/request/response schema, DB schema, dependency 변경 없음
- transaction/security/concurrency/common architecture/complex query 영향 없음
- 별도 Reviewer가 필요할 정도의 위험 없음
- compile 또는 짧은 targeted test로 충분히 검증 가능

대표 후보: 오타/Javadoc/주석, 로그/메시지, 명백한 null/조건문 오류, 작은 validation/test/Markdown 수정.

범위가 불명확하거나 기존/신규 흐름 비교처럼 여러 호출 경로를 먼저 분석해야 하면 DIRECT보다 FAST를 우선한다. 실제 source 확인 후 DIRECT 범위를 벗어나면 `DIRECT_FLOW_ESCALATION_REQUIRED: FAST | STANDARD`로 중단한다.

## FAST 적용 조건
다음을 모두 만족해야 한다.
- managed 단일 Repository가 명확함
- 작은 기존 패턴 기반 변경
- current branch에서 작업 가능
- 기존 변경이 있으면 그대로 보존하며 작업 가능
- architecture/product/public API/DB schema/dependency/cross-repo 결정 불필요
- 완료 조건과 검증 방법이 명확함

대표 후보: 작은 버그/null/edge-case, 기존 validation, 로그/메시지, 단순 Repository 수정, 테스트 보완, 문서/주석, 작은 리팩터링.

다음은 Standard Flow 대상이다: project/workspace 모호성, 기존 변경을 안전하게 보존하기 어려움, 새 branch/worktree, 신규 기능 설계, multi-repo/module 영향, API/schema/dependency/transaction/security/concurrency 정책 결정, 복수 해석 요구사항.

사용자가 `/dev-fast-flow`를 명시적으로 호출했더라도 eligibility 규칙을 우회하지 않는다. 요청 문장 자체에 HTTP payload/request/response 구조 변경, public API contract 변경, DB schema 변경, dependency 변경이 명시되어 있으면 source 사전 분석 없이 `STANDARD_REQUIRED`로 판정하고 Orchestrator에서 진행하도록 안내한다.

## Fast Intake Budget
FAST intake의 책임은 **구현 분석이 아니라 eligibility 판정과 dispatch**다.

- 사용자가 대상 파일/클래스를 명시했고 작은 로컬 변경이면 repository-wide `find`/`grep`부터 수행하지 않는다.
- docs/comment/log/message/null/validation처럼 Fast 적합성이 명확한 작업은 대상 존재 여부와 요구사항 명확성만 확인한다.
- 구현 세부사항, dependency 흐름, 테스트 내부 구현 분석은 `dev-implement-plan` worker의 책임이다.
- `create_fast_task.py`가 수행하는 `project.yaml`, branch, Base SHA, effective dirty baseline 검사를 사전에 중복 실행하지 않는다.
- 정상 경로에서는 `create_fast_task.py --help` 또는 스크립트 source read를 실행하지 않는다. Skill에 정의된 canonical invocation을 바로 사용하고, 스크립트가 실패했을 때만 오류 원인에 필요한 최소 범위를 확인한다.
- 직전 대화에서 동일 요청의 source 분석과 Fast Flow 적합성 판정이 완료됐다면 그 결과를 Goal/Acceptance/Implementation/Test Plan으로 재사용하고 source를 다시 조사하지 않는다.
- dispatch 성공 후 Interactive Coder는 추가 source 조사 없이 종료한다.

## Verification Mode
Task 생성 시 변경 성격에 맞는 최소 검증 모드를 명시한다.

- `DOCS`: Markdown/문서 등 실행 코드 미변경. scoped change verification만 수행한다.
- `COMPILE`: JavaDoc/주석 등 실행 의미를 바꾸지 않는 source 변경. 프로젝트 compile 검증을 기본으로 한다.
- `TARGETED_TEST`: 실행 로직 변경. 관련 targeted test를 기본으로 한다.

사용자가 더 강한 검증을 명시하면 그 요구를 우선한다. 변경 성격이 불분명하면 `TARGETED_TEST`를 선택한다.

Test Plan은 구현 중 반복 실행 목록이 아니라 **최종 verification contract**로 작성한다. 같은 stack의 여러 targeted test는 가능한 한 하나의 build invocation으로 묶을 수 있게 기록하고, frontend/backend 각각 필요한 최소 검증만 적는다.

## Fast Intake 계약
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
- 일반 개발 요청은 명시적 실행 방식 선택 전 구현을 시작하지 않는다.
- 동일 요청 반복은 승인으로 해석하지 않는다.
- 승인 대기 turn은 `clarify` 후 반드시 STOP한다.
- DIRECT는 Kanban 없이 Interactive Coder가 직접 수행하되 초소형·저위험 범위를 넘으면 즉시 escalation한다.
- Interactive FAST는 dispatch-only이며 source 수정/테스트를 하지 않는다.
- STANDARD_REQUIRED는 Coder가 직접 실행하지 않고 Orchestrator로 안내한다.
- intake에서 worker 수준의 상세 source 분석을 선행하지 않는다.
- 기존 사용자 변경을 덮어쓰거나 reset/restore/clean/stash하지 않는다.
- raw `git status`의 EOL noise를 사용자 변경으로 오인하지 않는다.
- risk 판정 때문에 검증을 생략하지 않는다.
- LOW를 파일 수만으로 판정하지 않는다.
- branch/worktree 생성, commit/push/PR/merge 금지.
