---
name: dev-implement-plan
description: 승인된 Kanban 작업을 할당 Workspace에서 최소 구현·검증하고 Fast Flow는 risk에 따라 완료 또는 review, Standard Flow는 reviewer에게 인계한다.
version: 0.9.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, implementation, coder, kanban, workspace, review, fast-flow, capability]
    related_skills: [dev-fast-flow, dev-breakdown, dev-workspace-dispatch, dev-review-cycle, dev-code-review, dev-spring-guidelines, dev-spring-feature, dev-spring-data, dev-spring-test, dev-api-docs]
    requires_tools: [terminal, kanban_show, kanban_request_review, kanban_complete, kanban_block, kanban_heartbeat, skill_view]
---

# dev-implement-plan

Coder worker의 **compact 실행 계약**이다. 상세 구현/검증/risk 기준은 필요할 때만 `references/implementation-details.md`를 읽는다.

## 실행 계약
1. `kanban_show()`로 Task body, attempts, comments, feedback을 읽고 Workspace/Expected Branch/Base SHA를 `scripts/verify_workspace.py`로 검증한다. mismatch면 수정 전에 `BLOCKED`.
2. `Flow: FAST`는 실제 source를 읽은 뒤 Fast Flow 범위를 재확인한다. API/schema/dependency/architecture/transaction/security/concurrency/cross-repo/모호한 요구사항 등 설계 판단이 필요하면 `FAST_FLOW_ESCALATION_REQUIRED`로 `kanban_block`한다.
3. 모든 작업은 `/opt/data/shared/references/coding-rules.md`와 `/opt/data/shared/references/project-pattern-rules.md`를 적용하고 가장 가까운 기존 구현을 기준으로 최소 diff만 만든다.
4. Task의 `Project Pattern Summary`, `Pattern References`, `Applicable Skills`를 재사용한다. 실제 source와 충돌하지 않는 한 프로젝트 전체를 다시 분석하지 않는다.
5. Spring은 실제 evidence로 필요한 Skill만 lazy-load한다. 적용할 때 반드시 해당 본문을 `skill_view()`로 읽는다.
   - Spring 공통 → `skill_view("dev-spring-guidelines")`
   - API/Controller/Service/DTO/Validation/Exception → `skill_view("dev-spring-feature")`
   - JPA/Repository/QueryDSL/Converter/Paging → `skill_view("dev-spring-data")`
   - **테스트 작성/수정** → `skill_view("dev-spring-test")` (단순 테스트 실행만으로는 로드하지 않음)
   - OpenAPI/Swagger/Postman 작업 → `skill_view("dev-api-docs")`
6. targeted verification → `git diff --check` → `scripts/change_summary.py` 순으로 필요한 범위만 검증한다.
7. 구현 후 `Review Risk`를 판정한다.
   - **Standard Flow 또는 CHANGES_REQUESTED 재작업** → 항상 `kanban_request_review`.
   - **Fast Flow + LOW** → 근거와 verification을 기록하고 `kanban_complete`.
   - **Fast Flow + REVIEW_REQUIRED** → `kanban_request_review`.
8. terminal action 하나를 실행한 뒤 즉시 멈춘다. 구현 불가/필수 입력 누락/필수 검증 불가만 `kanban_block`한다.

## Fast Flow Review Risk

`LOW`는 다음을 **모두** 만족할 때만 허용한다.

```text
기존 패턴을 따르는 작은 국소 변경
public API / DB schema / Entity relation 변경 없음
dependency / transaction / security / concurrency 변경 없음
복잡 QueryDSL / Native Query 없음
공통 모듈·architecture 영향 없음
요구사항과 diff가 명확하고 targeted verification PASS
residual risk가 낮으며 reviewer의 독립 판단이 correctness에 실질적으로 필요하지 않음
```

하나라도 불확실하거나 위 위험 영역에 닿으면 `REVIEW_REQUIRED`다. 세부 예시는 `references/implementation-details.md`의 Risk-based Review 절을 읽는다.

## 공통 Coding Rules 핵심
- 기존 abstraction/library/pattern을 먼저 재사용하고 unrelated refactor를 섞지 않는다.
- 함수/메서드 실행 block은 기본 `2-depth`; 반복 I/O/N+1을 확인한다.
- Stack / Capability Skill은 기존 convention을 확장할 뿐 architecture/dependency/common contract를 임의 변경하지 않는다.
- API는 기존 공통 response/error contract를 유지한다.
- JPA 조회는 단순 Method Query → 복잡/동적 QueryDSL → 근거 있는 Native Query 순서다.

## Handoff / Completion Evidence

```text
Pattern References
Applied Capability Skills
Changed Files
Verification Commands / Results
Review Risk: LOW | REVIEW_REQUIRED
Risk Reasons
Residual Risk
```

LOW completion metadata에는 `flow=FAST`, `review_risk=LOW`, 근거와 verification을 남긴다. Reviewer handoff에는 동일 evidence를 보존한다.

## 불변식
- Workspace 밖 수정, branch 전환, 다른 worktree 생성, commit, push, PR, merge, reset, clean, stash 금지.
- secret/raw credential 기록 금지.
- `CHANGES_REQUESTED`는 terminal 상태가 아니며 original coder가 동일 Workspace에서 blocking finding만 수정 후 반드시 재-review한다.
- Standard Flow에서 Coder self-complete 금지.

retry/BLOCKED/검증/risk metadata 세부 형식이 필요하면 `references/implementation-details.md`를 읽는다.