---
name: dev-review
description: Hermes DevKit 직접 개발의 선택적 자체 검증. 변경 diff와 기존 프로젝트 관례, 회귀 테스트, 위험을 점검하되 Kanban 작업 할당·독립 Reviewer 인계·완료 승인 절차는 요구하지 않는다.
version: 0.3.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, core, review, self-review, code-quality, regression, verification]
    related_skills: [dev-project-pattern, dev-java-guidelines, dev-spring-guidelines, dev-spring-test, dev-frontend-test, dev-official-docs-context]
    requires_tools: [terminal]
---

# dev-review

이 Skill은 Hermes DevKit의 **현재 대화형 개발 에이전트**가 사용자가 요청할 때 수행하는 **자체 리뷰**다. Standard Flow의 독립 Reviewer 역할이나 worker-owned Kanban 계약이 아니다.

## 실행 조건

- 사용자 요청: "검토", "리뷰", "테스트 확인", "변경사항 확인" 등
- 또는 실질적 회귀·보안 위험을 가진 변경에서 자체 체크가 필요한 경우
- 단순한 구현 중에는 별도 단계나 승인 Gate를 자동으로 만들지 않는다.

## 최소 절차

1. 먼저 개발 대상 프로젝트의 기존 패턴, 언어/JDK/라이브러리 버전과 사용자 요구사항을 확인한다.
2. Git 프로젝트면 `git status`/`git diff`를 우선 사용하되 사용자의 기존 미커밋 변경을 구분한다. 자동 reset/stash/cleanup을 하지 않는다.
3. 변경된 코드의 기능 누락, 예외/경계값, 호환성, 보안, 트랜잭션/동시성, 성능, 테스트 회귀 위험을 변경 범위에 맞춰 점검한다.
4. Java/Spring/Frontend/DB 등에 맞는 기존 `/opt/custom-skills/shared` capability를 필요할 때만 참조한다.
5. 가능한 최소 범위 테스트부터 실행하고 필요 시 관련 통합/회귀 테스트를 실행한다. 빌드 도구는 기존 Devkit workspace/cache 분리 방식을 유지한다.
6. 사용자에게 **검토 결과, 실제 테스트 명령/결과, 미검증 위험**을 간결하게 보고한다. 발견한 문제를 사용자가 수정 요청하면 같은 세션에서 연속적으로 개선한다.

## 구분

- 이 Skill은 **독립 검증 완료**를 주장할 수 없다. 특히 인증·권한·DB migration·핵심 API 계약 변경은 별도 사람 리뷰 또는 독립 검증을 권장한다.
- `kanban_show`, `kanban_request_review`, `kanban_complete`, `dev-implement-plan`, `dev-review-cycle`은 필요하지 않다.
- 사용자가 원하면 결함 또는 미완료 항목만 **선택적으로** Kanban에 기록한다. 자동 카드 생성이나 상태 전환은 하지 않는다.

## 출력 예시

- 변경 범위: 파일/기능 요약
- 확인된 결함: 중요도와 재현 근거
- 테스트: 실제 실행한 command, PASS/FAIL, 미실행 이유
- 잔여 위험: 추가 수동/독립 검증이 필요한 내용
- 권장 후속 작업: 사용자 요청이 있는 경우에만 반영

## 변경 범위별 DevKit 품질 판정
- 현재 요구사항과 실제 diff를 대조해 P0(보안·데이터 손실·계약 파괴), P1(동작/회귀/트랜잭션 실패), 기타 개선을 구분한다. 프로젝트 규칙을 우선하며 근거 없는 스타일 취향으로 BLOCK하지 않는다.
- Java/JPA: 실제 JDK 문법 호환, Optional·mutable entity·N+1·반복 I/O, 예외 처리·동시성·트랜잭션을 확인한다. 변경한 코드의 운영 로깅 문구는 영어다.
- Java/Kotlin 테스트: `jvm-test-display-name-policy.md`에 따라 신규·변경 JUnit Jupiter 테스트의 한글 `@DisplayName` 누락을 확인한다. 미지원 엔진은 대체 표시명과 사유를 확인하고, 관련 없는 기존 테스트까지 일괄 변경하지 않는다.
- Spring: Controller/Service/DTO/Validation/Error Contract와 책임 혼재, 구조적 변경을 확인한다. DB schema/API는 기존 소비자·데이터와의 호환성을 검증하고 변경 범위에 맞춰 후속 점검한다.
- Frontend: 기존 디자인 Reference/컴포넌트·반응형·접근성·API 계약을 대조한다. 실제 UI/browser 영향을 근거로 검증을 선택하며 일괄 Screenshot/Package Build 강제 금지.
- 검증은 `/opt/data/shared/references/verification-level-policy.md`의 위험별 `STATIC_COMPILE / TARGETED_TEST / PACKAGE_BUILD`를 기준으로 선택한다. 실제 프로젝트 기존 검증 명령을 우선한다.
- Maven/Gradle 검증은 `/opt/devkit/scripts/verification/`의 역할 독립 캐시 helper를 사용할 수 있다. `--scope-path` 변경, 테스트 명령·코드·툴체인 변경, 외부 상태 의존 시 과거 PASS를 그대로 믿지 않는다.
- 검증 명령/결과/미실행 사유, 잔여 위험을 기록한다. 자체 검토를 독립 Reviewer 승인과 동일하게 주장하지 않는다.

## Browser execution boundary — Browser Verification Contract V1
UI 검증은 `dev-frontend-test`의 `Browser execution boundary`와 `scripts/ui_runtime` 관리형 adapter를 사용한다.
브라우저 capability가 없거나 세션 증거가 실패하면 `NOT_EXECUTED`를 보고한다. native dialog의 승인/거절 근거 없이 beforeunload 성공을 주장하지 않는다. 관리형 브라우저 검증 실패를 raw Playwright/CDP 또는 임의 fallback script로 우회하지 않는다. 공식 `native_dialog_response` 근거와 실제 changed behavior를 확인한다.
