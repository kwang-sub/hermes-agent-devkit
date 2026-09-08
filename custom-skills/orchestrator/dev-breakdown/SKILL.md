---
name: dev-breakdown
description: managed 프로젝트의 실제 코드·디자인 근거와 기존 project pattern으로 한국어 Implementation Plan을 생성하며 구현하지 않는 orchestrator 전용 skill.
version: 0.9.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, planning, analysis, breakdown, orchestrator, pattern, frontend, figma]
    related_skills: [dev-project-bootstrap, dev-project-pattern, dev-tech-dispatch, dev-skill-preflight, dev-workspace-dispatch, dev-workflow-orchestrate, dev-java-guidelines, dev-frontend-feature]
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
11. Figma URL이 있으면 다음 계약을 계획에 보존한다.

```text
Design Source: FIGMA
Design Status: DRAFT | APPROVED
Figma URL: <selected node URL>
Frontend Mode: FIGMA_DRIVEN | CODE_DRIVEN
```

`APPROVED`만 `FIGMA_DRIVEN`으로 확정한다. `DRAFT` 또는 승인 상태 불명확 시 임의로 구현 기준으로 승격하지 않는다.
12. `Applicable Skills`에 추정 이름을 만들지 않는다. runtime pin 가능 여부는 dispatch 직전 `dev-skill-preflight`가 검증한다.
13. testable Acceptance Criteria와 risk-based Test Plan, Dependencies, Risks, Open Questions를 작성한다.
14. project/repo·scope·pattern·AC·tasks·test·필요한 design approval이 확립될 때만 `READY`, 아니면 `BLOCKED`다.

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

## 기존 Spring/JPA 정책 보존

```text
기존 프로젝트 pattern 최대 유지
공통 Response 규격 재사용
단순 JPA 조회 → Spring Data JPA Method Query 우선
복잡/동적 조회 → QueryDSL 우선
Native Query → 앞 방식으로 해결하기 어려운 근거가 있을 때만
```

## 필수 출력

Task Identity; Project/working tree; Goal/Type/Requirement; Assumptions/Constraints/Out of Scope; **Project Pattern Summary**; Design Source/Status/Frontend Mode(해당 시); Findings; Affected Areas; Implementation Tasks; Applicable Skills; Frontend Capability Hints; Acceptance Criteria; Automated/Manual/Regression Test Plan; Dependencies; Risks; Open Questions; Dispatch Handoff; `READY | BLOCKED`와 이유.

유형별 상세 체크리스트와 출력 템플릿은 `references/planning-details.md`를 필요할 때만 읽는다.
