---
name: dev-implement-plan
description: 승인 계획을 할당 Workspace에서 기존 project pattern과 필요한 stack/capability skill을 적용해 최소 구현·검증하고 commit/push 없이 reviewer에게 인계한다.
version: 0.7.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, implementation, coder, kanban, workspace, review, fast-flow, capability]
    related_skills: [dev-fast-flow, dev-breakdown, dev-workspace-dispatch, dev-review-cycle, dev-code-review, dev-spring-guidelines, dev-spring-feature, dev-spring-data, dev-spring-test, dev-api-docs]
    requires_tools: [terminal, kanban_show, kanban_request_review, kanban_block, kanban_heartbeat]
---

# dev-implement-plan

## 실행 계약
1. 먼저 `kanban_show()`로 body, attempts, comments, feedback을 읽는다.
2. `$HERMES_KANBAN_WORKSPACE`에서 `scripts/verify_workspace.py --base-sha <Base SHA>`로 Task Key, approved Workspace/Git root, Expected Branch, dispatch Base SHA resolve 및 HEAD ancestor 관계를 검증한다. mismatch면 수정 전에 BLOCKED다.
3. Goal, Acceptance Criteria, Implementation Tasks, Test Plan, Risks, Expected/Base Branch, Reviewer Profile이 있는지 확인한다.
4. `Flow: FAST` Task라면 실제 source를 수정하기 전에 Fast Flow 범위가 여전히 유효한지 확인한다. 모호한 제품 의도, architecture 결정, public API/DB schema 변경, cross-repository 작업, dependency 변경, materially broader scope가 발견되면 구현을 확장하지 않고 `FAST_FLOW_ESCALATION_REQUIRED`로 `kanban_block`한다.
5. 모든 프로그래밍 작업에서 `/opt/data/shared/references/coding-rules.md`와 `/opt/data/shared/references/project-pattern-rules.md`를 적용한다. 요구사항과 가장 유사한 기존 구현을 찾아 package/naming/response/error/data/test convention을 확인한 후 최소 diff로 구현한다. reviewer 재작업이면 blocking finding만 처리한다.
6. Task에 `Project Pattern Summary`, `Pattern References`, `Applicable Skills`가 있으면 이를 실제 source와 대조한다. 오래되었거나 불일치하면 source evidence를 우선하되, 승인 scope를 바꿀 정도면 수정하지 말고 BLOCKED한다.
7. Spring/Spring Boot 프로젝트를 실제 build/source evidence로 확인하면 `dev-spring-guidelines`를 기본 적용한다. Task에 Skill이 누락되어도 요청이 명백히 해당하면 다음 capability를 자동 적용한다.
   - Controller/Service/DTO/Validation/Exception/API feature → `dev-spring-feature`
   - JPA/Entity/Repository/DataJPA/QueryDSL/Converter/Paging → `dev-spring-data`
   - Spring/JPA 테스트 → `dev-spring-test`
   - OpenAPI/Swagger/Postman → `dev-api-docs`
8. Spring/JPA 데이터 조회에서는 단순 조회는 Spring Data JPA Method Query를 우선하고, 복잡하거나 동적인 조회는 QueryDSL을 우선한다. Native Query는 Method Query/QueryDSL로 해결하기 어려운 근거가 있을 때만 사용하고 이유를 handoff에 기록한다.
9. API 응답은 프로젝트에 존재하는 공통 응답 규격을 사용한다. 공통 규격이 없는 기존 API를 임의로 새로운 wrapper로 변경하지 않는다.
10. Stack/Capability Skill은 기존 project pattern과 공통 Coding Rules를 확장할 뿐 약화하지 않는다. dependency, architecture, 공통 response/error contract를 임의로 새로 도입하지 않는다.
11. targeted verification부터 실행하고 `git diff --check` 및 `scripts/change_summary.py`로 tracked/untracked/status를 수집한다.
12. 정확한 command/result와 검증된 `BASE_SHA`, 사용한 Pattern References/Capability Skills, residual risk를 기록하고 configured `reviewer`에게 `kanban_request_review`만 호출한 뒤 멈춘다. 구현 완료 상태에서 `kanban_complete` 또는 review 대용 `kanban_block`을 호출하지 않는다.

## Fast Flow escalation

`Flow: FAST`에서 다음 증거를 발견하면 파일을 수정하기 전에 Block한다.

```text
FAST_FLOW_ESCALATION_REQUIRED
- Evidence: <실제 source/config/test에서 확인한 사실>
- Why Fast Flow is no longer safe: <설계/범위/호환성 이유>
- Standard Flow decision needed: <Orchestrator가 확인해야 할 항목>
```

이미 최소 변경을 시작한 뒤 escalation 조건이 드러난 경우에는 추가 변경을 멈추고 현재 변경 상태를 Block summary에 정확히 남긴다. 기존 사용자 변경을 reset/restore/clean/stash하지 않는다.

## Project Pattern 규칙

- 새 helper/class/function을 만들기 전에 기존 Utility, Service, Policy, Calculator, Validator, Converter, Mapper, Domain Object, Data Access abstraction과 사용 중인 library를 검색하고 적절하면 재사용한다.
- 동일/유사 기능의 기존 Controller/Service/Repository/DTO/Entity/Test를 reference로 삼고 새 스타일을 임의 도입하지 않는다.
- 기존 pattern에 개선 필요점이 있더라도 Task에 필수적이지 않으면 구현에 섞지 않는다. `Current Pattern / Observed Problem / Proposed Improvement / Trade-offs`로 handoff에 남긴다.
- 범용 기술 로직만 Utility로 둔다. Domain Logic은 특정 Domain Object의 책임이면 해당 객체에 두고, 하나의 객체에 귀속하기 어렵다면 DDD에서는 Domain Component를 검토한다. 비DDD에서는 기존 Model 역할과 현재 프로젝트 패턴을 따른다.
- 함수/메서드 실행 block은 기본 최대 2-depth로 유지하며 초과 시 guard clause 또는 의미 있는 책임 단위로 분리한다. 숫자만 맞추기 위한 의미 없는 helper는 만들지 않는다.
- 주요 함수/메서드와 비직관적 흐름에는 목적/이유/처리 순서를 설명하는 프로젝트 표준 documentation을 작성하되 코드 번역형 주석은 만들지 않는다.
- loop/collection pipeline 내부 DB/API/File/Network I/O는 반복 호출/N+1 가능성을 확인하고 기존 프로젝트 패턴에서 batch/bulk 처리 가능성을 검토한다.

## Stack / Capability Skill 확장

현재 1차 capability set:

```text
dev-spring-guidelines  # Spring 공통 convention / response / transaction
dev-spring-feature     # Controller / Service / DTO / Validation / Exception
dev-spring-data        # JPA / DataJPA / QueryDSL / Entity / Repository / Converter
dev-spring-test        # Spring/JPA testing
dev-api-docs           # OpenAPI / Swagger / Postman (framework independent)
```

Java/Kotlin은 별도 Spring Skill로 분리하지 않고 실제 project 언어와 convention을 감지한다. 언어별 차이가 큰 경우에만 Skill 내부 reference를 확장한다.

전문 Skill 설계 기준은 `/opt/data/shared/references/stack-capability-skill-guide.md`를 따른다.

## Reviewer handoff evidence

최소 다음을 기록한다.

```text
Pattern References
Preserved Conventions
Applied Capability Skills
Query Strategy (해당 시)
Response Contract (API 작업 시)
Verification Commands / Results
Intentional Deviations
Improvement Deferred
Residual Risk
```

## 불변식
- 할당 Workspace 밖 수정, branch 전환, 다른 worktree 생성, unrelated refactor/format/upgrade/API-schema 변경 금지.
- secret/raw credential을 source, log, Kanban summary/metadata에 기록 금지.
- commit, push, PR, merge, rebase, cherry-pick, reset, clean, stash, cleanup 금지.
- 필수 검증 불가 또는 plan과 실제 evidence의 설계 충돌은 추측하지 말고 BLOCKED.
- Fast Flow가 실제 evidence상 단순하지 않으면 속도를 위해 scope를 확장하지 않고 Standard Flow escalation을 우선한다.
- CHANGES_REQUESTED는 종료가 아니라 original coder에게 돌아온 retry다. 동일 Workspace에서 blocking finding만 수정하고 다시 `kanban_request_review`한다.

정확성 checklist, retry, handoff metadata와 BLOCKED 형식이 필요하면 `references/implementation-details.md`를 먼저 읽는다.
