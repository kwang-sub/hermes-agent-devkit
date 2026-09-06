---
name: dev-breakdown
description: managed 프로젝트의 실제 코드·stack·기존 project pattern 근거로 한국어 Implementation Plan을 생성하고 canonical capability skill을 선택하며 구현하지 않는 orchestrator 전용 skill.
version: 0.8.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, planning, analysis, breakdown, orchestrator, pattern, stack, capability]
    related_skills: [dev-project-bootstrap, dev-project-pattern, dev-tech-dispatch, dev-skill-preflight, dev-workspace-dispatch, dev-workflow-orchestrate, dev-java-guidelines, dev-spring-guidelines, dev-typescript-guidelines, dev-frontend-guidelines, dev-nextjs-feature, dev-frontend-test, dev-api-contract, dev-ui-ux]
    requires_tools: [terminal, skill_view]
---

# dev-breakdown

요구사항을 coder가 실행 가능한 **근거 기반 한국어 계획**으로 바꾸는 read-only 단계다. repository/source/config를 수정하거나 workspace/branch/Kanban을 만들고 dependency를 설치하거나 commit, push, reset, restore, clean, stash하지 않는다.

## 계약

1. `<repo>/.hermes/project.yaml`을 local automation source로 읽고 Project/Repository/Board/Base/Profiles를 검증한다. 없거나 correctness에 필요한 값이 불일치하면 BLOCKED다.
2. 계획 수립 전에 반드시 `skill_view("dev-project-pattern")`으로 본문을 로드하고 `/opt/data/shared/references/project-pattern-rules.md`, `coding-rules.md`, `implementation-decision-rules.md` 기준과 함께 적용한다.
3. `dev-project-pattern`이 수집한 stack/pattern evidence와 `dev-tech-dispatch` 결과를 재사용해 `Project Pattern Summary`, `Pattern References`, `Applicable Skills`, `Pattern Conflicts`, `Improvement Candidates`를 만든다.
4. `scripts/collect_project_context.sh`와 targeted search로 source, call flow, config, tests, similar code, 필요한 history를 확인한다. 기존 local change는 보존하고 baseline과 구분한다.
5. requirement의 유형, goal, constraints, In/Out of Scope, current findings와 최소 affected areas를 정한다. 코드로 답할 수 없는 product intent는 만들지 않는다.
6. 중요한 가정이 source evidence로 닫히는지 먼저 확인한다. API/schema/dependency/architecture/product 의미에 여러 합리적 선택지가 남으면 임의 결정하지 않고 Open Question/Decision Needed로 남긴다.
7. 기존 project pattern을 우선 유지하되 사용자/Task의 명시 정책과 충돌하면 조용히 기존 방식을 복제하지 않는다. 충돌 사실, 최소 적용 방법, 필요한 결정사항을 계획에 기록한다. 요구사항에 필수적이지 않은 architecture/library/common-contract 개선은 자동 적용하지 않고 Improvement Candidate로 분리한다.
8. 최대 7개의 실행 가능한 Implementation Tasks를 근거·변경·의존성·완료 조건·verification과 함께 순서화한다. 각 task에 필요한 Stack/Capability Skill과 적용 이유를 명시한다.
9. `Applicable Skills`에는 실제 canonical skill 이름만 사용한다. 설치 여부와 runtime pin 가능 여부는 dispatch 직전 `dev-skill-preflight`가 검증한다.
10. 원 요구사항을 testable Acceptance Criteria로 명확히 하고 risk-based Test Plan, Dependencies, Known Risks, Open Questions를 작성한다.
11. P0 blocker가 없고 project/repo·scope·pattern·AC·tasks·test가 확립될 때만 `READY`; 아니면 정확한 질문과 다음 action을 포함해 `BLOCKED`다.

`READY`는 기술적 계획 상태일 뿐 **Plan Approval Gate** 또는 **Workspace / Branch Approval Gate** 통과가 아니다. 승인 전 `dev-workspace-dispatch`를 실행하지 않는다.

## Capability mapping

### Java / Spring

```text
Java
→ dev-java-guidelines

Spring/Spring Boot
→ dev-spring-guidelines

Controller/Service/DTO/Validation/Exception
→ dev-spring-feature

JPA/Repository/DataJPA/QueryDSL/Converter/Paging
→ dev-spring-data

Spring/JPA test
→ dev-spring-test

OpenAPI/Swagger/Postman
→ dev-api-docs
```

Spring/JPA에서는 특히 다음 정책을 계획에 반영한다.

```text
기존 프로젝트 pattern 최대 유지
공통 Response 규격 재사용
단순 JPA 조회 → Spring Data JPA Method Query 우선
복잡/동적 조회 → QueryDSL 우선
Native Query → Method Query/QueryDSL로 해결하기 어려운 근거가 있을 때만
```

### TypeScript / React / Next.js

```text
TypeScript source/type/config
→ dev-typescript-guidelines

React component/hook/state/browser UI
→ dev-frontend-guidelines

Next.js route/page/layout/Server·Client Component/metadata
→ dev-nextjs-feature

frontend test/spec/e2e
→ dev-frontend-test

visual/layout/interaction/responsive/accessibility/chart
→ dev-ui-ux
```

Frontend 계획에서는 새 상태관리/form/data/UI library를 기본값으로 선택하지 않는다. 기존 component/library/platform 기능과 설치 dependency를 먼저 확인한다.

### Full-stack contract

Backend API와 frontend type/client의 method/path/payload/error/nullability 계약을 함께 변경하면:

```text
dev-api-contract
```

를 적용한다.

API 문서 산출물이 필요한 경우 `dev-api-docs`를 추가한다.

## Project Pattern Summary

최소 다음을 포함한다.

```text
Language / Framework / Persistence / Build / Test
Detected Stacks
Pattern References
Package / Naming
Controller / Service / Data structure
Response Contract
Error / Validation Contract
Data Access Convention
Frontend Component / State / Style Convention (해당 시)
Design System Reference (해당 시)
Test Convention
Applicable Skills
Pattern Conflicts
Improvement Candidates (not auto-applied)
```

`Applicable Skills`에는 단순 이름만 적지 말고 적용 이유를 짧게 남긴다.

예:

```text
Applicable Skills:
- dev-java-guidelines: Java version/build/type convention
- dev-spring-data: JPA repository/query change
- dev-typescript-guidelines: frontend API type 변경
- dev-nextjs-feature: App Router page 변경
- dev-api-contract: backend DTO와 frontend client 계약 동시 변경
- dev-ui-ux: dashboard responsive/accessibility 변경
```

## 필수 출력

Task Identity; Project/working tree; Goal/Type/Requirement; Assumptions/Constraints/Out of Scope; **Project Pattern Summary**; Findings; Affected Areas; Implementation Tasks + Applicable Skills; Acceptance Criteria; Automated/Manual/Regression Test Plan; Dependencies; Risks; Open Questions; Dispatch Handoff(Goal/AC/Tasks/Test/Risks/Project Pattern Summary/Pattern References/Applicable Skills/Pattern Conflicts/coder); `READY | BLOCKED`와 이유.

유형별 분석, task priority, risk/API/data checklist, 질문 및 전체 출력 템플릿이 필요하면 `references/planning-details.md`를 먼저 읽는다.
