---
name: dev-breakdown
description: managed 프로젝트의 실제 코드 근거로 한국어 Implementation Plan을 생성하며 구현하지 않는 orchestrator 전용 skill.
version: 0.3.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, planning, analysis, breakdown, orchestrator]
    related_skills: [dev-project-bootstrap, dev-workspace-dispatch, dev-workflow-orchestrate]
    requires_tools: [terminal]
---

# dev-breakdown

요구사항을 coder가 실행 가능한 **근거 기반 한국어 계획**으로 바꾸는 read-only 단계다. repository/source/config를 수정하거나 workspace/branch/Kanban을 만들고 dependency를 설치하거나 commit, push, reset, restore, clean, stash하지 않는다.

## 계약
1. `<repo>/.hermes/project.yaml`을 local automation source로 읽고 Project/Repository/Board/Base/Profiles를 검증한다. 없거나 correctness에 필요한 값이 불일치하면 BLOCKED다.
2. `scripts/collect_project_context.sh`와 targeted search로 source, call flow, config, tests, similar code, 필요한 history를 확인한다. 기존 local change는 보존하고 baseline과 구분한다.
3. requirement의 유형, goal, constraints, In/Out of Scope, current findings와 최소 affected areas를 정한다. 코드로 답할 수 없는 product intent는 만들지 않는다.
4. 최대 7개의 실행 가능한 Implementation Tasks를 근거·변경·의존성·완료 조건·verification과 함께 순서화한다.
5. 원 요구사항을 testable Acceptance Criteria로 명확히 하고 risk-based Test Plan, Dependencies, Known Risks, Open Questions를 작성한다.
6. P0 blocker가 없고 project/repo·scope·AC·tasks·test가 확립될 때만 `READY`; 아니면 정확한 질문과 다음 action을 포함해 `BLOCKED`다.

`READY`는 기술적 계획 상태일 뿐 **Plan Approval Gate** 또는 **Workspace / Branch Approval Gate** 통과가 아니다. 승인 전 `dev-workspace-dispatch`를 실행하지 않는다.

## 필수 출력
Task Identity; Project/working tree; Goal/Type/Requirement; Assumptions/Constraints/Out of Scope; Findings; Affected Areas; Implementation Tasks; Acceptance Criteria; Automated/Manual/Regression Test Plan; Dependencies; Risks; Open Questions; Dispatch Handoff(Goal/AC/Tasks/Test/Risks/coder); `READY | BLOCKED`와 이유.

유형별 분석, task priority, risk/API/data checklist, 질문 및 전체 출력 템플릿이 필요하면 `references/planning-details.md`를 먼저 읽는다.
