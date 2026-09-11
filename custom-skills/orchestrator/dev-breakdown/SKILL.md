---
name: dev-breakdown
description: managed 프로젝트의 실제 코드·디자인 근거와 기존 project pattern으로 한국어 Implementation Plan을 생성하며 구현하지 않는 orchestrator 전용 skill.
version: 0.10.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, planning, analysis, breakdown, orchestrator, pattern, frontend, figma, api, spec]
    related_skills: [dev-project-bootstrap, dev-project-pattern, dev-tech-dispatch, dev-skill-preflight, dev-workspace-dispatch, dev-workflow-orchestrate, dev-java-guidelines, dev-frontend-feature, dev-api-spec]
    requires_tools: [terminal, skill_view]
---

# dev-breakdown

요구사항을 Coder가 실행 가능한 **근거 기반 한국어 계획**으로 바꾸는 read-only 단계다. source/config 수정, dependency 설치, workspace/branch/Kanban 생성, commit/push/reset/restore/clean/stash를 하지 않는다.

## 계약

1. `<repo>/.hermes/project.yaml`을 읽고 Project/Repository/Board/Base/Profiles를 검증한다.
2. `skill_view("dev-project-pattern")`으로 전체 pattern 계약을 읽고 Foundation references를 적용한다.
3. project pattern 결과의 Detected Stacks, Pattern References, Design Source, Applicable Skills, Frontend Capability Hints를 재사용한다.
4. targeted search로 source/call flow/config/tests/similar code만 확인하고 repository 전체 재분석을 피한다.
5. Goal/Constraints/In-Out Scope/minimum affected areas를 정한다. product intent를 추측하지 않는다.
6. 중요한 assumption은 source evidence로 닫고, product/architecture/design 승인 결정이 필요하면 Open Question으로 남긴다.
7. 최대 7개 Implementation Tasks를 변경·근거·완료조건·verification과 함께 순서화한다.
8. Java 프로젝트의 Java 변경은 `dev-java-guidelines`, Spring 변경은 기존 `dev-spring-*` capability를 Applicable Skills에 지정한다.
9. **Frontend Task는 `dev-frontend-feature`를 canonical Applicable Skill로 지정한다.** TypeScript/React/Next.js/Test/API/Figma/UI·UX 하위 Skill은 `Frontend Capability Hints`에 이름과 이유를 남기고 시작부터 모두 runtime pin하지 않는다.
10. Backend API와 Frontend가 함께 바뀌는 Task는 Frontend Capability Hints에 `dev-api-contract`를 포함한다.
11. API endpoint 신규/변경/문서화/감사 작업은 `dev-api-spec`을 적용하고 다음을 계획에 명시한다.

```text
API Spec Mode: DESIGN_FIRST | SOURCE_SYNC | AUDIT | NOT_REQUIRED
API Spec Gate: REQUIRED | NOT_REQUIRED
API Spec Status: DRAFT | APPROVED | NOT_REQUIRED
API Spec Path: <planned/existing markdown path | none>
API Spec Source: DESIGN | APPLICATION_SOURCE | MIGRATED_SPEC | none
```

판정 규칙:

```text
신규 endpoint 또는 method/path/request/response/error 의미 변경 → DESIGN_FIRST
기존 endpoint의 누락 Markdown 문서화                     → SOURCE_SYNC
Source ↔ Markdown ↔ OpenAPI 차이 조사                  → AUDIT
API contract 영향 없음                                → NOT_REQUIRED
```

`DESIGN_FIRST`이면 `API Spec Gate: REQUIRED`, 최초 `API Spec Status: DRAFT`다. Orchestrator는 구현 전에 Markdown 형태의 규격 초안을 사용자에게 보여주지만 source를 수정하지 않는다.

`SOURCE_SYNC`는 현재 Application Source를 설명하는 역문서화이므로 별도 API Spec 승인 Gate가 필요하지 않다. 자동 생성 문서는 `Status: DRAFT`, `Documentation Source: APPLICATION_SOURCE`를 유지한다. 기존 API라는 이유만으로 `APPROVED`로 승격하지 않는다.

`AUDIT`은 기본 read-only이며 `IN_SYNC | SOURCE_ONLY | SPEC_ONLY | CONTRACT_MISMATCH` 결과를 계획 Findings에 남긴다. 전체 API 스캔은 사용자가 명시적으로 전체 감사를 요청한 경우에만 허용한다.
12. Figma URL이 있으면 다음 계약을 계획에 보존한다.

```text
Design Source: FIGMA
Design Status: DRAFT | APPROVED
Figma URL: <selected node URL>
Frontend Mode: FIGMA_DRIVEN | CODE_DRIVEN
```

`APPROVED`만 `FIGMA_DRIVEN`으로 확정한다. `DRAFT` 또는 승인 상태 불명확 시 임의로 구현 기준으로 승격하지 않는다.
13. `Applicable Skills`에 추정 이름을 만들지 않는다. runtime pin 가능 여부는 dispatch 직전 `dev-skill-preflight`가 검증한다.
14. testable Acceptance Criteria와 risk-based Test Plan, Dependencies, Risks, Open Questions를 작성한다.
15. project/repo·scope·pattern·AC·tasks·test·필요한 design/API approval이 확립될 때만 `READY`, 아니면 `BLOCKED`다.

## Frontend 계획 규칙

Frontend Task에서는 다음을 명시한다.

```text
Frontend Entry: dev-frontend-feature
Frontend Mode: FIGMA_DRIVEN | CODE_DRIVEN
Package Manager / Framework evidence
Existing Component/Token references
Frontend Capability Hints
Design Source / Status
Affected UI States: loading | empty | error | populated (해당 시)
Responsive scope
API contract impact
Verification plan
```

예:

```text
Applicable Skills:
- dev-frontend-feature: Frontend canonical implementation entry

Frontend Capability Hints:
- dev-typescript-guidelines: API/UI type change
- dev-nextjs-feature: App Router page/component change
- dev-figma-design: APPROVED Figma frame evidence
- dev-ui-ux: responsive/accessibility/chart quality gate
- dev-api-contract: Spring DTO와 frontend type 동시 변경
```

## API 계획 규칙

API 관련 Task에서는 필요할 때 다음을 명시한다.

```text
Applicable Skills:
- dev-api-spec: Markdown API Specification 설계/역문서화/감사
- dev-api-contract: backend/frontend 또는 spec/source contract 검증
- dev-api-docs: OpenAPI/Swagger/Postman 산출물

API Spec Mode: DESIGN_FIRST | SOURCE_SYNC | AUDIT
API Spec Gate: REQUIRED | NOT_REQUIRED
API Spec Status: DRAFT | APPROVED | NOT_REQUIRED
API Spec Path: docs/api/<domain>.md 또는 project-existing path
Audit Result: IN_SYNC | SOURCE_ONLY | SPEC_ONLY | CONTRACT_MISMATCH | NOT_RUN
```

기존 프로젝트의 대상 API가 실제 source에 존재하지만 Markdown이 없으면 `SOURCE_ONLY`로 보고하고, Task 범위 안에서 `SOURCE_SYNC` 문서화를 포함할 수 있다.

## 기존 Spring/JPA 정책 보존

```text
기존 프로젝트 pattern 최대 유지
공통 Response 규격 재사용
단순 JPA 조회 → Spring Data JPA Method Query 우선
복잡/동적 조회 → QueryDSL 우선
Native Query → 앞 방식으로 해결하기 어려운 근거가 있을 때만
```

## 필수 출력

Task Identity; Project/working tree; Goal/Type/Requirement; Assumptions/Constraints/Out of Scope; **Project Pattern Summary**; Design Source/Status/Frontend Mode(해당 시); **API Spec Mode/Gate/Status/Path/Source(해당 시)**; Findings; Affected Areas; Implementation Tasks; Applicable Skills; Frontend Capability Hints; Acceptance Criteria; Automated/Manual/Regression Test Plan; Dependencies; Risks; Open Questions; Dispatch Handoff; `READY | BLOCKED`와 이유.

유형별 상세 체크리스트와 출력 템플릿은 `references/planning-details.md`를 필요할 때만 읽는다.
