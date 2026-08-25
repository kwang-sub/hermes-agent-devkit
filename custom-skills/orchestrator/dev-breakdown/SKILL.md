---
name: dev-breakdown
description: managed 프로젝트의 실제 코드 근거와 기존 project pattern으로 한국어 Implementation Plan을 생성하며 구현하지 않는 orchestrator 전용 skill.
version: 0.5.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, planning, analysis, breakdown, orchestrator, pattern]
    related_skills: [dev-project-bootstrap, dev-project-pattern, dev-workspace-dispatch, dev-workflow-orchestrate]
    requires_tools: [terminal, skill_view]
---

# dev-breakdown

요구사항을 coder가 실행 가능한 **근거 기반 한국어 계획**으로 바꾸는 read-only 단계다. repository/source/config를 수정하거나 workspace/branch/Kanban을 만들고 dependency를 설치하거나 commit, push, reset, restore, clean, stash하지 않는다.

## 계약
1. `<repo>/.hermes/project.yaml`을 local automation source로 읽고 Project/Repository/Board/Base/Profiles를 검증한다. 없거나 correctness에 필요한 값이 불일치하면 BLOCKED다.
2. 계획 수립 전에 반드시 `skill_view("dev-project-pattern")`으로 `dev-project-pattern` 본문을 로드하고 `/opt/data/shared/references/project-pattern-rules.md` 기준과 함께 적용한다. Skill metadata/description만 보고 전체 계약을 추측하지 않는다.
3. project instruction, build/dependency, source 구조와 요청에 가장 가까운 기존 구현을 확인해 `Project Pattern Summary`, `Pattern References`, `Applicable Skills`, `Pattern Conflicts`, `Improvement Candidates`를 만든다.
4. `scripts/collect_project_context.sh`와 targeted search로 source, call flow, config, tests, similar code, 필요한 history를 확인한다. 기존 local change는 보존하고 baseline과 구분한다.
5. requirement의 유형, goal, constraints, In/Out of Scope, current findings와 최소 affected areas를 정한다. 코드로 답할 수 없는 product intent는 만들지 않는다.
6. 기존 project pattern을 우선 유지하되 사용자/Task의 명시 정책과 충돌하면 조용히 기존 방식을 복제하지 않는다. 충돌 사실, 최소 적용 방법, 필요한 결정사항을 계획에 기록한다. 요구사항에 필수적이지 않은 architecture/library/common-contract 개선은 자동 적용하지 않고 Improvement Candidate로 분리한다.
7. 최대 7개의 실행 가능한 Implementation Tasks를 근거·변경·의존성·완료 조건·verification과 함께 순서화한다. 각 task에 필요한 Stack/Capability Skill이 있으면 이름을 명시한다.
8. Spring/Spring Boot 프로젝트에서는 `dev-spring-guidelines`를 기본 applicable skill로 지정한다. Controller/Service/DTO/Validation/Exception 변경은 `dev-spring-feature`, JPA/Repository/DataJPA/QueryDSL/Converter는 `dev-spring-data`, Spring/JPA 테스트는 `dev-spring-test`, OpenAPI/Swagger/Postman은 `dev-api-docs`를 추가 지정한다. 이 단계에서는 Coder 전용 capability Skill을 실행하지 않고 이름과 적용 이유만 계획에 보존한다.
9. 원 요구사항을 testable Acceptance Criteria로 명확히 하고 risk-based Test Plan, Dependencies, Known Risks, Open Questions를 작성한다.
10. P0 blocker가 없고 project/repo·scope·pattern·AC·tasks·test가 확립될 때만 `READY`; 아니면 정확한 질문과 다음 action을 포함해 `BLOCKED`다.

`READY`는 기술적 계획 상태일 뿐 **Plan Approval Gate** 또는 **Workspace / Branch Approval Gate** 통과가 아니다. 승인 전 `dev-workspace-dispatch`를 실행하지 않는다.

## Project Pattern Summary

최소 다음을 포함한다.

```text
Language / Framework / Persistence / Build / Test
Pattern References
Package / Naming
Controller / Service / Data structure
Response Contract
Error / Validation Contract
Data Access Convention
Test Convention
Applicable Skills
Pattern Conflicts
Improvement Candidates (not auto-applied)
```

`Applicable Skills`에는 단순 이름만 적지 말고 적용 이유를 짧게 남긴다.

```text
Applicable Skills:
- dev-spring-guidelines: Spring Boot project common convention
- dev-spring-feature: Controller/Service/DTO API feature change
- dev-spring-data: JPA repository/query change
```

Spring/JPA에서는 특히 다음 정책을 계획에 반영한다.

```text
기존 프로젝트 pattern 최대 유지
공통 Response 규격 재사용
단순 JPA 조회 → Spring Data JPA Method Query 우선
복잡/동적 조회 → QueryDSL 우선
Native Query → Method Query/QueryDSL로 해결하기 어려운 근거가 있을 때만
OpenAPI/Postman → dev-api-docs (Spring 전용 skill로 취급하지 않음)
```

## 필수 출력
Task Identity; Project/working tree; Goal/Type/Requirement; Assumptions/Constraints/Out of Scope; **Project Pattern Summary**; Findings; Affected Areas; Implementation Tasks + Applicable Skills; Acceptance Criteria; Automated/Manual/Regression Test Plan; Dependencies; Risks; Open Questions; Dispatch Handoff(Goal/AC/Tasks/Test/Risks/Project Pattern Summary/Pattern References/Applicable Skills/Pattern Conflicts/coder); `READY | BLOCKED`와 이유.

유형별 분석, task priority, risk/API/data checklist, 질문 및 전체 출력 템플릿이 필요하면 `references/planning-details.md`를 먼저 읽는다.
