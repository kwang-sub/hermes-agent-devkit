---
name: dev-lite-session
description: Hermes Lite 기본 대화형 개발 정책. Orchestrator와 Kanban 할당 없이 직접 구현·검증하며 Kanban은 선택적으로 기록한다.
version: 0.1.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, lite, direct, interactive, kanban-optional]
    related_skills: [dev-lite-review, dev-java-guidelines, dev-spring-guidelines, dev-spring-test, dev-official-docs-context]
    requires_tools: [terminal]
---

# dev-lite-session

Hermes Lite에서 새 대화 세션을 시작할 때 자동으로 읽는 기본 동작 정책이다.

## 직접 개발
- 사용자의 현재 대화형 Hermes 에이전트가 요구사항 분석 → 코드 수정 → 적절한 테스트 → 결과 확인 → 재수정을 담당한다.
- Orchestrator 승인, Kanban 카드 생성·할당, Coder/Reviewer worker 실행은 선행 조건이 아니다. Flow 전용 스킬을 자동 호출하지 않는다.
- 변경 범위나 영향이 커지면 사용자와 직접 논의한다. 인증·권한, DB 마이그레이션, 삭제 등 위험 작업은 명시적 승인 없이 수행하지 않는다.
- 사용자의 구현 중 추가 지시와 완료 후 수정 요청을 같은 세션에서 반영한다.

## 선택적 Kanban
- 중요한 작업·미완료 항목은 사용자가 요청했을 때 기록하고, 자동으로 새 카드를 생성하거나 dispatch하지 않는다.
- 기존 카드/메모리를 읽고 참고할 수 있으나 Standard Flow worker가 점유 중인 카드의 소유권·진행 상태를 임의 변경하지 않는다.
- Kanban 기능 장애 때문에 일반 코드 개발을 중단하지 않는다. 사용자가 요청한 기록이 실패하면 실패를 명시한다.

## 개발 규칙과 검증
- 대상 프로젝트에 이미 존재하는 AGENTS.md/관례/빌드 설정이 소스 변경의 기준이다. Standard Flow를 명시적으로 선택하지 않았다면 역할 기반 승인·인계 계약은 Lite에 적용하지 않는다.
- Java/Spring/Kotlin/Frontend/DB에 해당하는 shared capability 스킬을 필요한 경우에만 불러온다. 모든 스킬 본문을 한꺼번에 읽지 않는다.
- 기존 Devkit의 Docker Workspace·JDK·Maven·Gradle·Node·pnpm 격리 방식을 유지한다.
- 실질적 테스트를 실행하고 통과/실패/미실행 이유를 보고한다. `dev-lite-review`는 선택적 자체 검토이므로 독립 Reviewer와 동일하게 표현하지 않는다.
- 변경 내용은 최소화하고 기존 코드·파일 및 미커밋 변경을 보존한다. Git commit/push/PR/merge는 사용자가 요청할 때만 수행한다.

사용자의 최종 판단을 존중하며, 프로젝트의 기존 보안·품질 기준은 완화하지 않는다.
