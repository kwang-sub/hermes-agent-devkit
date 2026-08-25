---
name: dev-code-review
description: 동일 Workspace의 미커밋 구현을 계획/AC와 project pattern/stack capability 계약 기준으로 독립 검토하고 승인·수정요청·차단한다.
version: 0.6.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, review, reviewer, kanban, quality, verification, capability]
    related_skills: [dev-implement-plan, dev-review-cycle, dev-workspace-dispatch]
    requires_tools: [terminal, skill_view, kanban_show, kanban_request_changes, kanban_complete, kanban_block, kanban_heartbeat]
---

# dev-code-review

## 실행 계약
1. `kanban_show()`에서 original requirement/plan/AC, Project Pattern Summary, Pattern References, Applicable Skills, Pattern Conflicts, coder handoff, attempts/comments를 읽는다.
2. 같은 `$HERMES_KANBAN_WORKSPACE`에서 `scripts/review_context.py --base-branch <Base Branch> --base-sha <Base SHA>`로 dispatch Base SHA/Expected Branch를 검증한다.
3. dispatch Base SHA에 고정된 tracked diff, full status, untracked files, `git diff --check`와 필요한 주변 flow를 read-only로 확인한다. `BASE_BRANCH_DRIFTED`는 별도 metadata로 보고하되 diff 기준을 바꾸지 않는다.
4. Goal/AC/approved scope/correctness/compatibility/security/tests와 coder verification evidence를 비교한다.
5. 모든 프로그래밍 작업에서 `/opt/data/shared/references/coding-rules.md`와 `/opt/data/shared/references/project-pattern-rules.md`를 기준으로 기존 구현 재사용, Utility/Domain 책임 배치, 2-depth, documentation, 반복 DB/API/File/Network I/O와 프로젝트 architecture/convention 일관성을 함께 검토한다.
6. Task의 `Applicable Skills`와 Coder handoff의 `Applied Capability Skills`를 합쳐 중복 제거하고, Reviewer 프로필에서 사용 가능한 capability Skill은 각각 `skill_view("<skill-name>")`으로 본문을 로드한 뒤 그 계약을 검증한다. metadata/description만 보고 규칙을 추측하지 않는다. Reviewer 프로필에 해당 Skill이 설치되지 않아 로드할 수 없으면 Task의 보존된 contract와 Coder evidence를 기준으로 검토하고, correctness 판단에 핵심 세부 규칙이 없어 안전하게 판단할 수 없을 때만 BLOCKED한다.
7. diff가 명백한 Spring/JPA/API-docs 작업인데 Applicable/Applied Skills에서 빠졌다면 누락 자체를 evidence로 기록하고 해당 capability 계약을 가능한 범위에서 추가 검토한다.
8. P0/P1이 있으면 `kanban_request_changes`; 없고 evidence가 충분하면 APPROVED `kanban_complete`; 안전한 판단 자체가 불가능하거나 외부 결정이 필요하면 `BLOCKED`로 `kanban_block` 중 정확히 하나만 실행하고 멈춘다.

## Project Pattern Review Gate

- 새 코드가 가장 가까운 기존 Controller/Service/Repository/DTO/Entity/Test 패턴과 불필요하게 다르지 않은지 확인한다.
- package/layer/naming/response/error/test convention 차이가 요구사항 또는 명시 정책으로 설명되는지 확인한다.
- 기존 pattern 개선을 핑계로 unrelated architecture/library/common-contract 변경을 섞지 않았는지 확인한다.
- Coder handoff의 `Pattern References`, `Preserved Conventions`, `Intentional Deviations`, `Improvement Deferred`를 실제 diff와 대조한다.

## Common Coding Review Gate

- 기존 Utility, Service, Policy, Calculator, Validator, Converter, Mapper, Domain Object, Data Access abstraction 또는 library를 재사용할 수 있는데 중복 구현하지 않았는지 확인한다.
- 범용 Utility와 Domain Logic이 올바른 책임 위치에 있는지 확인한다.
- DDD 프로젝트에서는 Domain Object 자신의 행위를 불필요하게 Domain Service로 밀어내지 않았는지, 비DDD 프로젝트에서는 기존 Model 역할과 다른 modeling style을 갑자기 도입하지 않았는지 확인한다.
- 함수/메서드 block depth가 기본 2-depth를 반복적으로 넘는다면 guard clause/책임 분리가 필요한 실제 유지보수 문제인지 확인한다.
- 주요 함수/메서드와 비직관적 흐름에 목적/이유를 설명하는 프로젝트 표준 documentation이 있으며 코드 번역형 또는 실제 동작과 다른 주석이 없는지 확인한다.
- loop/collection pipeline 내부 DB/API/File/Network I/O에 불필요한 반복 호출이나 N+1 위험이 없는지 확인한다.
- 기존 Constant/Enum/Validator/Converter/Mapper 등 공통 abstraction을 중복 구현하지 않았는지 확인한다.
- 이 항목들은 취향 기반 style gate가 아니며 실제 프로젝트 pattern, correctness, maintainability, performance에 의미 있는 경우에만 Blocking Finding으로 사용한다.

## Stack / Capability Review Gate

현재 1차 capability set:

```text
dev-spring-guidelines
dev-spring-feature
dev-spring-data
dev-spring-test
dev-api-docs
```

### Spring 공통

- 실제 Spring/Spring Boot version과 언어가 Coder evidence와 일치하는지 확인한다.
- API 작업은 프로젝트의 기존 공통 Response/Error contract를 유지했는지 확인한다.
- Controller/Service/DTO/Validation/Exception이 기존 프로젝트 구조와 일관적인지 확인한다.
- 요구사항에 없는 dependency/architecture/common response 변경이 없는지 확인한다.

### JPA / Data

Query strategy가 다음 우선순위를 지켰는지 확인한다.

```text
단순 조회 → Spring Data JPA Method Query
복잡/동적 조회 → QueryDSL
Native Query → 앞 두 방식으로 해결하기 어려운 근거가 있을 때만
```

- Native Query가 사용되었다면 Method Query와 QueryDSL이 부적합한 근거가 handoff에 있는지 확인한다.
- QueryDSL dependency가 없는 프로젝트에 승인 없이 새 dependency를 추가하지 않았는지 확인한다.
- mapping/fetch/join/paging/N+1/Converter 변경은 실제 persistence test 또는 타당한 verification evidence가 있는지 확인한다.

### Test

- 프로젝트가 쓰는 JUnit/Kotest/Mockito/MockK 등의 기존 stack과 style을 유지했는지 확인한다.
- 실제 persistence behavior를 과도한 mock으로만 검증하거나 모든 것을 `@SpringBootTest`로 처리하지 않았는지 위험에 따라 판단한다.
- bug fix의 회귀 테스트와 API validation/error contract 테스트가 필요한 경우 존재하는지 확인한다.

### API Docs

- `dev-api-docs`는 Spring 전용이 아님을 전제로 실제 source contract와 문서가 일치하는지 확인한다.
- Spring OpenAPI에서는 기존 SpringDoc 설정을 재사용했는지, `@Tag`, `@Operation`, error example/group/customizer 패턴이 프로젝트 및 reference 정책과 일관적인지 확인한다.
- 예시 프로젝트의 `ResponseEntity<DTO>`를 강제로 복사하지 않고 대상 프로젝트 공통 response wrapper schema를 반영했는지 확인한다.
- Postman collection에 실제 secret/token이 포함되지 않았는지 확인한다.
- OpenAPI와 Postman을 둘 다 만든 경우 request/response/error/auth contract가 서로 어긋나지 않는지 확인한다.

Stack/Capability Skill 확장 기준은 `/opt/data/shared/references/stack-capability-skill-guide.md`를 따른다.

## Reviewer Evidence

Verdict에 최소 다음을 남긴다.

```text
Reviewed Pattern References
Applicable / Applied Capability Skills
Capability Skills Loaded via skill_view (가능한 경우)
Contract Mismatches
Verification Evidence Reviewed
Residual Risk
```

## 불변식
- Reviewer는 application/test/config source를 수정하지 않는다.
- untracked source/test/config를 누락하지 않고 style/nit만으로 승인을 막지 않는다.
- finding은 file/symbol, evidence, required change, expected verification이 있는 실행 가능한 내용이어야 한다.
- secret/raw credential을 출력하지 않고 commit, push, PR, cleanup하지 않는다.
- 같은 중요한 blocker가 3 review cycle 지속되면 needs_input으로 escalation한다.
- CHANGES_REQUESTED는 terminal 상태가 아니며 Card를 original coder에게 돌려 같은 Workspace의 수정 loop를 계속한다. Reviewer가 직접 고치거나 Orchestrator가 정상 round 사이에 개입하지 않는다.

Severity, checklist, verdict metadata와 escalation 세부 기준이 필요하면 `references/review-details.md`를 먼저 읽는다.
