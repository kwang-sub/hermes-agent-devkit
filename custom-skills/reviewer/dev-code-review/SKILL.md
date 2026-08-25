---
name: dev-code-review
description: 동일 Workspace의 미커밋 구현을 계획/AC 기준으로 독립 검토하고 승인·수정요청·차단한다.
version: 0.4.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, review, reviewer, kanban, quality, verification]
    related_skills: [dev-implement-plan, dev-review-cycle, dev-workspace-dispatch]
    requires_tools: [terminal, kanban_show, kanban_request_changes, kanban_complete, kanban_block, kanban_heartbeat]
---

# dev-code-review

## 실행 계약
1. `kanban_show()`에서 original requirement/plan/AC, coder handoff, attempts/comments를 읽는다.
2. 같은 `$HERMES_KANBAN_WORKSPACE`에서 `scripts/review_context.py --base-branch <Base Branch> --base-sha <Base SHA>`로 dispatch Base SHA/Expected Branch를 검증한다.
3. dispatch Base SHA에 고정된 tracked diff, full status, untracked files, `git diff --check`와 필요한 주변 flow를 read-only로 확인한다. `BASE_BRANCH_DRIFTED`는 별도 metadata로 보고하되 diff 기준을 바꾸지 않는다.
4. Goal/AC/approved scope/correctness/compatibility/security/tests와 coder verification evidence를 비교한다.
5. 모든 프로그래밍 작업에서 `/opt/data/shared/references/coding-rules.md`를 기준으로 기존 구현 재사용, Utility/Domain 책임 배치, 2-depth, documentation, 반복 DB/API/File/Network I/O와 프로젝트 architecture 일관성을 함께 검토한다.
6. Task에 Stack/Capability Skill이 사용되었다면 해당 Skill의 stack-specific Acceptance Criteria, 생성 artifact, project convention 재사용 여부와 verification evidence도 추가로 검토한다.
7. P0/P1이 있으면 `kanban_request_changes`; 없고 evidence가 충분하면 APPROVED `kanban_complete`; 안전한 판단 자체가 불가능하거나 외부 결정이 필요하면 `BLOCKED`로 `kanban_block` 중 정확히 하나만 실행하고 멈춘다.

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

전문 Skill이 사용된 경우 공통 Coding Review Gate에 추가해 해당 Skill의 계약을 검증한다.

예정된 Spring 계열 Skill:

```text
dev-spring-openapi
dev-spring-validation
dev-jpa-converter
```

Reviewer는 최소한 다음을 확인한다.

```text
감지한 stack/version이 실제 project와 일치하는가
기존 project pattern을 재사용했는가
불필요한 dependency를 추가하지 않았는가
Skill이 요구한 artifact/annotation/config/mapping이 실제 코드에 적용됐는가
stack-specific test/verification이 실행됐는가
Java/Kotlin 차이를 기존 project convention에 맞게 처리했는가
```

Stack/Capability Skill 확장 기준은 `/opt/data/shared/references/stack-capability-skill-guide.md`를 따른다.

## 불변식
- Reviewer는 application/test/config source를 수정하지 않는다.
- untracked source/test/config를 누락하지 않고 style/nit만으로 승인을 막지 않는다.
- finding은 file/symbol, evidence, required change, expected verification이 있는 실행 가능한 내용이어야 한다.
- secret/raw credential을 출력하지 않고 commit, push, PR, cleanup하지 않는다.
- 같은 중요한 blocker가 3 review cycle 지속되면 needs_input으로 escalation한다.
- CHANGES_REQUESTED는 terminal 상태가 아니며 Card를 original coder에게 돌려 같은 Workspace의 수정 loop를 계속한다. Reviewer가 직접 고치거나 Orchestrator가 정상 round 사이에 개입하지 않는다.

Severity, checklist, verdict metadata와 escalation 세부 기준이 필요하면 `references/review-details.md`를 먼저 읽는다.
