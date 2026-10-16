---
name: dev-lite-review
description: Hermes Lite 직접 개발의 선택적 자체 검증. 변경 diff와 기존 프로젝트 관례, 회귀 테스트, 위험을 점검하되 Kanban 작업 할당·독립 Reviewer 인계·완료 승인 절차는 요구하지 않는다.
version: 0.1.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, lite, review, self-review, code-quality, regression, verification]
    related_skills: [dev-java-guidelines, dev-spring-guidelines, dev-spring-test, dev-frontend-test, dev-official-docs-context]
    requires_tools: [terminal]
---

# dev-lite-review

이 Skill은 Hermes Lite의 **현재 대화형 개발 에이전트**가 사용자가 요청할 때 수행하는 **자체 리뷰**다. Standard Flow의 독립 Reviewer 역할이나 worker-owned Kanban 계약이 아니다.

## 실행 조건

- 사용자 요청: "검토", "리뷰", "테스트 확인", "변경사항 확인" 등
- 또는 실질적 회귀·보안 위험을 가진 변경에서 자체 체크가 필요한 경우
- 단순한 구현 중에는 별도 단계나 승인 Gate를 자동으로 만들지 않는다.

## 최소 절차

1. 먼저 개발 대상 프로젝트의 기존 패턴, 언어/JDK/라이브러리 버전과 사용자 요구사항을 확인한다.
2. Git 프로젝트면 \`git status\`/\`git diff\`를 우선 사용하되 사용자의 기존 미커밋 변경을 구분한다. 자동 reset/stash/cleanup을 하지 않는다.
3. 변경된 코드의 기능 누락, 예외/경계값, 호환성, 보안, 트랜잭션/동시성, 성능, 테스트 회귀 위험을 변경 범위에 맞춰 점검한다.
4. Java/Spring/Frontend/DB 등에 맞는 기존 \`/opt/custom-skills/shared\` capability를 필요할 때만 참조한다.
5. 가능한 최소 범위 테스트부터 실행하고 필요 시 관련 통합/회귀 테스트를 실행한다. 빌드 도구는 기존 Devkit workspace/cache 분리 방식을 유지한다.
6. 사용자에게 **검토 결과, 실제 테스트 명령/결과, 미검증 위험**을 간결하게 보고한다. 발견한 문제를 사용자가 수정 요청하면 같은 세션에서 연속적으로 개선한다.

## 구분

- 이 Skill은 **독립 검증 완료**를 주장할 수 없다. 특히 인증·권한·DB migration·핵심 API 계약 변경은 별도 사람 리뷰 또는 독립 검증을 권장한다.
- \`kanban_show\`, \`kanban_request_review\`, \`kanban_complete\`, \`dev-implement-plan\`, \`dev-review-cycle\`은 필요하지 않다.
- 사용자가 원하면 결함 또는 미완료 항목만 **선택적으로** Kanban에 기록한다. 자동 카드 생성이나 상태 전환은 하지 않는다.

## 출력 예시

- 변경 범위: 파일/기능 요약
- 확인된 결함: 중요도와 재현 근거
- 테스트: 실제 실행한 command, PASS/FAIL, 미실행 이유
- 잔여 위험: 추가 수동/독립 검증이 필요한 내용
- 권장 후속 작업: 사용자 요청이 있는 경우에만 반영
