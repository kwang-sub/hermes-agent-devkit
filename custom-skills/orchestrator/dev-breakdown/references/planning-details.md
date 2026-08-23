# 상세 정책 보존본

이 문서는 compact entrypoint 이전의 `custom-skills/orchestrator/dev-breakdown/SKILL.md` 전체 내용을 보존한다. compact 문서가 지시하는 상황에 필요한 절만 적용한다. 아래 원본의 YAML frontmatter는 참조 정보이며 중첩 skill 선언이 아니다.

---

---
name: dev-breakdown
description: 현재 Hermes 프로젝트와 실제 코드베이스를 근거로 소프트웨어 요구사항을 분석하고, coder에게 전달 가능한 구현 계획을 생성한다. 이 Skill은 계획/분석만 수행하며 구현하지 않는다.
version: 0.2.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, planning, analysis, breakdown, orchestrator]
    related_skills: [dev-project-bootstrap, dev-workspace-dispatch, dev-workflow-orchestrate]
    requires_tools: [terminal]
---

# dev-breakdown

개발 요구사항을 분석하여 **구현 가능한 계획**으로 변환한다.

이 Skill은 **orchestrator 전용**이며 계획 및 코드 분석만 담당한다. 실제 구현은 하지 않는다.

결과는 이후 다음 흐름의 계약으로 사용된다.

```text
dev-breakdown
        ↓
사용자 Plan 승인
        ↓
dev-workspace-dispatch
        ↓
Kanban
        ↓
coder
        ↓
dev-implement-plan
```

## 핵심 규칙

요청 문구만 보고 일반적인 Task List를 만들지 않는다.

먼저 실제 프로젝트, 관련 Source Code, Test, Configuration, 필요하면 Git History를 읽고, 요구사항을 만족하는 **가장 작은 근거 기반 Plan**을 작성한다.

이 Skill은 Repository를 수정하지 않는다.

`READY`는 **기술적으로 구현 가능한 Plan이 준비됨**을 뜻할 뿐, 사용자의 구현 승인까지 완료되었다는 의미가 아니다. `dev-workflow-orchestrate`는 반드시 별도의 Plan Approval Gate를 수행해야 한다.

---

# 1. 사용 시점

다음에 사용한다.

- Feature 구현 계획
- Bug Fix 계획
- Refactoring 계획
- 개발 관점의 운영/Runtime 변경 계획
- API/Data/Schema 변경 계획
- 사용자 또는 Jira 요구사항을 Coding Task로 변환

다음에는 사용하지 않는다.

- 실제 Source Code 구현
- Workspace 준비
- Kanban Task 생성
- commit/push/PR
- 파괴적인 Repository Cleanup
- 소프트웨어 구현 범위가 없는 순수 Business Domain 분석

---

# 2. 필요한 프로젝트 상태

프로젝트는 `dev-project-bootstrap`으로 관리되는 상태여야 한다.

기대 메타데이터:

```text
<repo>/.hermes/project.yaml
```

존재하면 가장 먼저 읽고 다음의 Canonical Local Automation Metadata로 사용한다.

- Project ID
- Repository Path
- Kanban Board
- Default Base Branch
- Workspace Policy
- Orchestrator/Coder/Reviewer Profile
- Resolver Metadata
- 보존된 Source-specific Metadata가 있다면 해당 정보

메타데이터가 없거나 불일치하면:

- 프로젝트 설정을 조용히 추측하지 않는다.
- Bootstrap/Ensure가 필요함을 보고한다.
- Correctness에 영향을 주는 메타데이터가 없으면 Dispatch-ready Plan을 만들지 않는다.

---

# 3. 입력

요구사항은 다음에서 올 수 있다.

- 사용자 Text Request
- `dev-work-intake`가 정규화한 Jira Work Item
- Bug Report
- Feature Request
- Improvement Proposal
- Refactoring Request

가능한 사실 정보는 모두 사용한다.

- Task/Jira Key
- Summary
- Description
- Acceptance Criteria
- Comments
- Component / Label
- Linked Issue / Dependency
- Technical Constraint
- Explicit Non-goal

Issue Key만 있고 실제 Issue 내용이 없다면 Requirement를 만들어내지 않는다. Jira 조회/정규화는 `dev-work-intake`의 책임이다.

---

# 4. 작업 유형 분류

Code Exploration 전에 Primary Type을 분류한다.

## Feature

중점 확인:

- User Flow
- Data Flow
- API/UI Boundary
- Existing Similar Behavior
- Backward Compatibility
- Observable Completion Criteria

## Bug

다음 순서로 분석한다.

```text
reproduction
→ failing behavior
→ likely execution path
→ root-cause evidence
→ minimal fix boundary
→ regression verification
```

실패 Path 근거를 찾기 전에 추측성 Fix를 계획하지 않는다.

## Refactoring

중점 확인:

- 현재의 구체적 문제
- 유지해야 할 Invariant
- Change Boundary
- Compatibility
- Regression Risk
- 동작 보존을 증명하는 Test

"Cleaner code"만으로는 Refactoring 사유가 충분하지 않다.

## Operations / Runtime Change

중점 확인:

- Current Configuration/State
- Prerequisite
- Execution Step
- Rollback
- Verification Signal
- Environment-specific Risk

## Documentation / Development Process

중점 확인:

- Target Audience
- Source of Truth
- Artifact Structure
- Validation / Review Criteria

여러 유형이 섞여 있으면 Primary Type을 정하고 Secondary Work를 별도로 드러낸다.

---

# 5. Read-only 프로젝트 탐색

먼저 Helper를 실행한다.

```bash
bash "${HERMES_SKILL_DIR}/scripts/collect_project_context.sh"
```

이 Helper는 Read-only 탐색으로 다음을 출력한다.

- Current Directory
- Repository Root
- Current Branch
- `.hermes/project.yaml`
- Current Git Status
- Top-level Project Structure
- Detected Build Files
- Detected Test Directories
- Recent Git Commits

이후 필요한 범위만 Targeted Exploration한다.

## 탐색 우선순위

1. Project Context / `.hermes/project.yaml`
2. Requirement Keyword와 Domain Term
3. Entry Point: Controller/API/UI/Job/Listener
4. Service/Use-case Layer
5. Persistence/Domain/Model Layer
6. Configuration
7. Tests
8. Similar Implementation
9. Intent 파악에 필요한 경우 Git History/Blame

사용 가능한 Read-only Command 예:

```bash
rg -n "<term>" .
git grep -n "<term>"
git log --oneline --decorate -n 20
git log -S"<symbol-or-text>" --oneline --all
git log -G"<regex>" --oneline --all
git show <commit> -- <path>
git blame <path>
git status --short
```

파괴적 명령은 실행하지 않는다.

---

# 6. Working Tree 상태 인지

Source Checkout에 이미 사용자 변경이 있을 수 있으므로 항상 확인한다.

```bash
git status --short
```

규칙:

- 기존 변경을 reset/restore/clean/stash/commit/modify하지 않는다.
- 기존 변경이 현재 Task의 일부라고 가정하지 않는다.
- 수정된 파일이 계획 대상과 겹치면 그 사실을 명시한다.
- Repository Baseline Evidence와 Uncommitted Local State를 구분한다.
- Local Change 때문에 Base가 모호해지면 `BLOCKED` 또는 필요한 결정을 명시한다.

나중에 Dispatch될 Implementation Workspace와 Branch 전략은 사용자 승인으로 확정하며, 기존 Local Change가 있으면 승인 전에 명시한다.

---

# 7. Evidence-first 분석

각 변경 제안마다 Repository 근거를 식별한다.

좋은 예:

```text
AuditLogListController delegates filtering to AuditLogListService.
AuditLogSearchCond already contains date/user filters.
The repository implementation builds the QueryDSL predicate.
Existing tests cover date filtering but not the requested condition.
```

피해야 할 예:

```text
This probably belongs in the controller.
We should add a new service because that is cleaner.
```

코드에서 결정할 수 없는 세부사항은 만들어내지 말고 Open Question으로 표시한다.

---

# 8. 영향 범위 식별

가장 작은 예상 영향 영역을 정한다.

확인 가능한 경우 각 영역에 다음을 포함한다.

- File/Path
- Class/Component
- Method/Function
- Responsibility
- 영향받는 이유
- Direct / Indirect Impact

확신 수준을 구분한다.

```text
Confirmed
Likely
Possible / requires verification
```

근처 파일이라는 이유만으로 영향 파일 목록을 부풀리지 않는다.

---

# 9. Scope 정의

명확하게 구분한다.

## In Scope

요구사항 충족에 필요한 변경.

## Out of Scope

의도적으로 제외하는 항목.

예:

- 관계없는 Refactoring
- Dependency Upgrade
- Formatting Cleanup
- 인접 Bug
- Architecture Redesign
- 미래 확장성만을 위한 변경
- 관계없는 Test Modernization

## Follow-up Candidates

분석 중 발견했지만 현재 Requirement에 필수는 아닌 개선사항.

Follow-up Candidate를 Implementation Plan에 섞지 않는다.

---

# 10. Implementation Task 작성

추상적인 Phase가 아니라 실행 가능한 Task를 만든다.

각 Task는 독립적으로 이해/검증 가능한 크기를 선호한다. 대략 30분~2시간은 Heuristic일 뿐 억지로 분할하지 않는다.

최대:

```text
7 implementation tasks
```

7개보다 더 필요하면:

- 일관된 Module/Repository Boundary로 그룹화하거나
- 원 Issue 분할을 제안한다.

각 Task 필수 정보:

- Task Name
- Purpose
- Evidence / Affected Symbols
- Change
- Preconditions / Dependencies
- Completion Criteria
- Verification
- Priority

Priority:

- `P0`: 구현을 막는 필수 선행조건/모호성
- `P1`: 요청 결과에 필수
- `P2`: 안전한 완료에 필요한 품질/안정성 작업
- `P3`: Optional Follow-up, 일반적으로 Coder Dispatch에서 제외

Task Name은 Action-oriented하게 작성한다.

좋은 예:

```text
Extend audit-log search condition with the new filter
Apply the condition in the existing QueryDSL predicate
Add regression coverage for filtered and unfiltered requests
```

나쁜 예:

```text
Backend changes
Fix service
Testing
```

---

# 11. Acceptance Criteria

Requirement를 외부 또는 기술적으로 검증 가능한 조건으로 변환한다.

Acceptance Criteria는:

- 구체적
- Test 가능
- 가능한 경우 구현 방식과 독립적
- 원 Request와 연결됨

예:

```text
Given <condition>, the API returns only records matching <filter>.
When the new filter is omitted, existing query behavior remains unchanged.
Invalid values follow the project's existing validation/error behavior.
```

사용자/Jira가 요청하지 않은 Product Requirement를 새로 만들지 않는다.

Source에 이미 Acceptance Criteria가 있으면 의미를 보존하고 Test 가능성만 명확히 한다.

---

# 12. Test / Verification Plan

Risk 기반 검증을 작성한다.

가능한 경우 다음 우선순위를 사용한다.

1. Targeted Regression/Unit/Integration Test
2. Directly Affected Package/Module Test
3. Static/Type/Lint Check
4. Build/Package
5. 필요한 경우에만 Broader Suite

Bug Fix는 다음 흐름을 선호한다.

```text
reproduce
→ regression test fails
→ implementation
→ regression test passes
→ related tests pass
```

API/Data 변경 시 관련 있는 항목을 검토한다.

- Compatibility
- Null/Optional Behavior
- Validation
- Serialization
- Database/Schema Effect
- Transaction/Locking
- Existing Data
- Rollback

검증을 구분한다.

```text
Automated verification
Manual verification
Regression verification
```

Project Build Configuration에서 확인하지 않은 Command가 존재한다고 가정하지 않는다.

---

# 13. Risk 분석

관련 있는 Risk만 다룬다.

가능한 범주:

- Backward Compatibility
- API Contract
- DB Migration/Data
- Transaction Boundary
- Concurrency
- Idempotency/Retry
- Security/Auth
- Performance
- Cache/State
- Cross-module Coupling
- Deployment/Rollback
- Existing Uncommitted Changes

각 의미 있는 Risk는 다음 형식으로 기록한다.

```text
Risk
Impact
Mitigation / verification
```

적용되지 않는 Generic Risk 문구를 채우지 않는다.

---

# 14. Dependency와 순서

명시적으로 식별한다.

- Prerequisite Task
- Cross-task Dependency
- Cross-repository Dependency
- External Decision
- Schema/Config Dependency
- Linked Jira Issue Dependency

Implementation Task는 실행 가능한 순서로 정렬한다.

하나의 Requirement가 여러 Repository에 걸치면 하나의 Coding Task인 것처럼 숨기지 않는다. Repository 단위 분할과 Dependency Order를 제시해 Orchestrator가 이후 별도 Workspace/Kanban Task로 처리할 수 있게 한다.

현재 `dev-workflow-orchestrate v0.1.x`는 단일 Repository 실행을 기본으로 하므로 Multi-repo는 자동 Dispatch하지 않고 사용자 선택/분할이 필요하다.

---

# 15. Open Question / BLOCKED 규칙

Local Exploration으로 답할 수 있는 질문은 사용자에게 묻지 않는다.

Correctness에 결정이 필요한 다음 상황에서는 `BLOCKED`로 표시한다.

- 서로 호환되지 않는 Requirement Interpretation
- Target Repository를 결정할 수 없음
- Public API Compatibility 결정 필요
- 파괴적인 Schema/Data 동작이 정의되지 않음
- 사용자 Local Change를 포함해야 하는데 의도가 불명확함
- 필수 External Dependency/Version이 불명확함

각 Question에는 다음을 포함한다.

```text
Question
Why it matters
Available choices
Recommended default, if a safe default exists
```

Non-blocking Uncertainty는 Open Questions에 남길 수 있지만 Dispatch Readiness에 그 상태를 반영한다.

---

# 16. Dispatch Readiness

Plan 마지막은 다음 중 하나여야 한다.

## READY

다음을 모두 만족할 때만 사용한다.

- Project/Repository가 확정됨
- Requirement가 구현 가능함
- P0 Blocker가 없음
- 영향 범위를 충분히 이해함
- Acceptance Criteria가 Test 가능함
- Implementation Task가 실행 가능함
- Test Plan이 있음

**중요:** `READY`는 Plan 품질 상태다. Workspace 준비 승인이 아니다. 사용자의 Plan Approval 이후에만 `dev-workspace-dispatch`를 실행한다.

## BLOCKED

아직 구현을 Dispatch하면 안 될 때 사용한다.

정확한 Blocker와 필요한 다음 Action을 설명한다.

`dev-breakdown`은 Workspace Dispatch나 Kanban Task를 만들지 않는다.

---

# 17. 출력 형식

다음 형식을 유지한다.

```text
# Implementation Plan

## 1. Task Identity
- Task/Jira Key:
- Suggested Kanban Title:
- Suggested Task Slug:

## 2. Project
- Project ID:
- Repository:
- Base Branch:
- Kanban Board:
- Working Tree State:

## 3. Goal
- ...

## 4. Work Type
- Feature / Bug / Refactoring / Operations / Documentation
- Reason:

## 5. Requirement Summary
- ...

## 6. Assumptions and Constraints
- ...

## 7. Out of Scope
- ...

## 8. Current-State Findings
- Entry points:
- Relevant flow:
- Existing patterns:
- Existing tests:
- Git/history findings:
- Pre-existing local changes:

## 9. Affected Areas
1. [Confirmed/Likely] `<path>` — `<class/function>`
   - Reason:
   - Expected change:

## 10. Implementation Tasks
1. [P1] <action-oriented task name>
   - Purpose:
   - Evidence / affected symbols:
   - Change:
   - Depends on:
   - Completion criteria:
   - Verification:

## 11. Acceptance Criteria
- AC1:
- AC2:

## 12. Test Plan
### Automated
- ...

### Manual
- ...

### Regression
- ...

## 13. Dependencies
- ...

## 14. Risks
- Risk:
  - Impact:
  - Mitigation:

## 15. Open Questions
- None
or
- Question:
  - Why it matters:
  - Options:
  - Recommended:

## 16. Dispatch Handoff
- Recommended Assignee: `<coder profile from project metadata>`
- Suggested Branch: `feature/<TASK-KEY>` or current approved branch
- Approved Workspace: `<user-approved git workspace>`
- Plan Summary for Kanban:
  - Goal:
  - Acceptance Criteria:
  - Implementation Tasks:
  - Test Plan:
  - Dependencies:
  - Known Risks:

## 17. Dispatch Readiness
- READY / BLOCKED
- Reason:
```

Coder가 다시 기본 Architecture를 탐색하지 않아도 될 만큼 충분히 상세하게 작성하되, 대형 Source File이나 관계없는 Search Result를 그대로 덤프하지 않는다.

---

# 18. 안전 규칙

Repository 기준 Read-only Skill이다.

다음은 하지 않는다.

- Source File 수정
- Configuration 수정
- Workspace 준비
- Branch 생성
- Kanban Task 생성
- Commit
- Push
- Reset/Restore/Clean/Stash
- Dependency Install
- Migration 실행
- Runtime Service 변경

Planning 단계에서는 Read-only Build/Test도 보통 필요하지 않다. 분석 품질을 실질적으로 높이고 Runtime State를 예상치 못하게 변경하지 않는 경우에만 Command를 실행한다.

---

# 19. 성공 기준

좋은 Breakdown은 다른 Agent가 기본 Architecture를 다시 조사하지 않고 구현을 시작할 수 있게 한다.

최종 Plan은 다음 질문에 답해야 한다.

1. 정확히 무엇을 변경해야 하는가?
2. 왜 해당 위치가 영향을 받는가?
3. 무엇은 변경하면 안 되는가?
4. 어떤 순서로 구현해야 하는가?
5. 각 부분을 어떻게 검증하는가?
6. 무엇이 깨질 수 있는가?
7. 기술적으로 Dispatch 가능한가?
8. 사용자에게 승인받아야 할 Plan이 명확하게 제시되었는가?
