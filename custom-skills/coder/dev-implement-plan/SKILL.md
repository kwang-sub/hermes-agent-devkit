---
name: dev-implement-plan
description: 승인 계획을 할당 Workspace에서 최소 구현·검증하고 commit/push 없이 reviewer에게 인계한다.
version: 0.6.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, implementation, coder, kanban, workspace, review, fast-flow]
    related_skills: [dev-fast-flow, dev-breakdown, dev-workspace-dispatch, dev-review-cycle, dev-code-review]
    requires_tools: [terminal, kanban_show, kanban_request_review, kanban_block, kanban_heartbeat]
---

# dev-implement-plan

## 실행 계약
1. 먼저 `kanban_show()`로 body, attempts, comments, feedback을 읽는다.
2. `$HERMES_KANBAN_WORKSPACE`에서 `scripts/verify_workspace.py --base-sha <Base SHA>`로 Task Key, approved Workspace/Git root, Expected Branch, dispatch Base SHA resolve 및 HEAD ancestor 관계를 검증한다. mismatch면 수정 전에 BLOCKED다.
3. Goal, Acceptance Criteria, Implementation Tasks, Test Plan, Risks, Expected/Base Branch, Reviewer Profile이 있는지 확인한다.
4. `Flow: FAST` Task라면 실제 source를 수정하기 전에 Fast Flow 범위가 여전히 유효한지 확인한다. 모호한 제품 의도, architecture 결정, public API/DB schema 변경, cross-repository 작업, dependency 변경, materially broader scope가 발견되면 구현을 확장하지 않고 `FAST_FLOW_ESCALATION_REQUIRED`로 `kanban_block`한다.
5. 실제 source/flow/config/tests/pattern을 확인하고 승인 scope를 만족하는 최소 변경만 구현한다. reviewer 재작업이면 blocking finding만 처리한다.
6. 모든 프로그래밍 작업에서 `/opt/data/shared/references/coding-rules.md`를 적용한다. 기존 구현 재사용, Utility/Domain 책임 분류, 최대 2-depth, 의미 있는 documentation, 반복 DB/API/File/Network I/O 여부를 구현 전에 확인한다.
7. Task에 Stack/Capability Skill이 지정되었거나 요청이 해당 전문 기능에 해당하면 해당 Skill의 project detection, 기존 pattern 재사용, stack-specific verification 계약을 추가로 적용한다. 공통 Coding Rules보다 전문 Skill을 우선해 약화하지 않는다.
8. targeted verification부터 실행하고 `git diff --check` 및 `scripts/change_summary.py`로 tracked/untracked/status를 수집한다.
9. 정확한 command/result와 검증된 `BASE_SHA`, residual risk를 기록하고 configured `reviewer`에게 `kanban_request_review`만 호출한 뒤 멈춘다. 구현 완료 상태에서 `kanban_complete` 또는 review 대용 `kanban_block`을 호출하지 않는다.

## Fast Flow escalation

`Flow: FAST`에서 다음 증거를 발견하면 파일을 수정하기 전에 Block한다.

```text
FAST_FLOW_ESCALATION_REQUIRED
- Evidence: <실제 source/config/test에서 확인한 사실>
- Why Fast Flow is no longer safe: <설계/범위/호환성 이유>
- Standard Flow decision needed: <Orchestrator가 확인해야 할 항목>
```

이미 최소 변경을 시작한 뒤 escalation 조건이 드러난 경우에는 추가 변경을 멈추고 현재 변경 상태를 Block summary에 정확히 남긴다. 기존 사용자 변경을 reset/restore/clean/stash하지 않는다.

## 공통 Coding Rules 핵심

- 새 helper/class/function을 만들기 전에 기존 Utility, Service, Policy, Calculator, Validator, Converter, Mapper, Domain Object, Data Access abstraction과 사용 중인 library를 검색하고 적절하면 재사용한다.
- 범용 기술 로직만 Utility로 둔다. Domain Logic은 특정 Domain Object의 책임이면 해당 객체에 두고, 하나의 객체에 귀속하기 어렵다면 DDD에서는 Domain Component를 검토한다. 비DDD에서는 기존 Model 역할과 현재 프로젝트 패턴을 따른다.
- 함수/메서드 실행 block은 기본 최대 2-depth로 유지하며 초과 시 guard clause 또는 의미 있는 책임 단위로 분리한다. 숫자만 맞추기 위한 의미 없는 helper는 만들지 않는다.
- 주요 함수/메서드와 비직관적 흐름에는 목적/이유/처리 순서를 설명하는 프로젝트 표준 documentation을 작성하되 코드 번역형 주석은 만들지 않는다.
- loop/collection pipeline 내부 DB/API/File/Network I/O는 반복 호출/N+1 가능성을 확인하고 기존 프로젝트 패턴에서 batch/bulk 처리 가능성을 검토한다.
- 상세 기준은 `/opt/data/shared/references/coding-rules.md`를 따른다.

## Stack / Capability Skill 확장

전문 Skill은 특정 기술 작업의 세부 절차를 추가한다.

예정 구조:

```text
dev-spring-openapi
dev-spring-validation
dev-jpa-converter
```

Spring 기능은 가능하면 Java/Kotlin을 별도 Skill로 나누지 않고 프로젝트 언어와 convention을 감지해 하나의 Skill에서 처리한다. 언어별 차이가 충분히 큰 경우에만 내부 reference를 분리한다.

전문 Skill 설계 기준은 `/opt/data/shared/references/stack-capability-skill-guide.md`를 따른다.

## 불변식
- 할당 Workspace 밖 수정, branch 전환, 다른 worktree 생성, unrelated refactor/format/upgrade/API-schema 변경 금지.
- secret/raw credential을 source, log, Kanban summary/metadata에 기록 금지.
- commit, push, PR, merge, rebase, cherry-pick, reset, clean, stash, cleanup 금지.
- 필수 검증 불가 또는 plan과 실제 evidence의 설계 충돌은 추측하지 말고 BLOCKED.
- Fast Flow가 실제 evidence상 단순하지 않으면 속도를 위해 scope를 확장하지 않고 Standard Flow escalation을 우선한다.
- CHANGES_REQUESTED는 종료가 아니라 original coder에게 돌아온 retry다. 동일 Workspace에서 blocking finding만 수정하고 다시 `kanban_request_review`한다.

정확성 checklist, retry, handoff metadata와 BLOCKED 형식이 필요하면 `references/implementation-details.md`를 먼저 읽는다.
