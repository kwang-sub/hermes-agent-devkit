---
name: dev-tech-dispatch
description: managed Repository의 build/dependency evidence에서 사용 기술을 감지하고 Java/Spring/TypeScript/React/Next.js 및 cross-stack capability 후보를 canonical skill 이름으로 매핑하는 orchestrator 전용 read-only resolver.
version: 0.1.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, orchestrator, stack, capability, dispatch, java, spring, typescript, react, nextjs]
    related_skills: [dev-project-pattern, dev-breakdown, dev-java-guidelines, dev-spring-guidelines, dev-typescript-guidelines, dev-frontend-guidelines, dev-nextjs-feature, dev-frontend-test, dev-api-contract, dev-ui-ux]
    requires_tools: [terminal]
---

# dev-tech-dispatch

두 번째 이상의 framework/stack을 지원하기 위한 **기술 감지 + capability name resolver**다.

Workflow를 새로 만들지 않는다. `dev-workflow-orchestrate`, `dev-project-pattern`, `dev-breakdown`, `dev-skill-preflight`의 책임을 대체하지 않는다.

## 책임

1. project root의 최소 build/dependency evidence를 읽어 stack을 감지한다.
2. 감지한 stack에 필요한 baseline capability skill 이름을 canonical name으로 반환한다.
3. task 의미에 따라 추가할 capability 후보를 `dev-project-pattern`/`dev-breakdown`에 제공한다.
4. 설치 여부와 runtime pin 가능 여부는 판단하지 않는다. 최종 검증은 `dev-skill-preflight` 책임이다.

하지 않는 일:

- source/config 수정
- dependency 설치
- architecture 선택
- project 전체 scan
- Kanban 생성
- 비슷한 skill 이름 자동 대체

## Canonical detector

```bash
python3 /opt/custom-skills/orchestrator/dev-tech-dispatch/scripts/detect_capabilities.py \
  --repo "<managed repository>"
```

출력 예:

```text
STACKS=java,spring,typescript,react,nextjs
BASE_SKILLS=dev-java-guidelines,dev-spring-guidelines,dev-typescript-guidelines,dev-frontend-guidelines,dev-nextjs-feature
TEST_SKILLS=dev-frontend-test
UI_SKILL_CANDIDATE=dev-ui-ux
CROSS_STACK_SKILL_CANDIDATE=dev-api-contract
STATUS=pass
```

## Task 의미 기반 추가 규칙

Detector 출력은 project-level baseline이다. 실제 `Applicable Skills`는 Task affected area와 합쳐 결정한다.

```text
Java source
→ dev-java-guidelines

Spring/Spring Boot
→ dev-spring-guidelines

Controller/Service/DTO/Validation/Exception
→ dev-spring-feature

JPA/Repository/QueryDSL/Converter/Paging
→ dev-spring-data

Spring/JPA test
→ dev-spring-test

TypeScript source/config
→ dev-typescript-guidelines

React component/hook/state/browser UI
→ dev-frontend-guidelines

Next.js App Router / Server/Client Component / route handler / metadata
→ dev-nextjs-feature

frontend test/spec/e2e 또는 test dependency가 존재하고 테스트 변경 필요
→ dev-frontend-test

Backend API DTO/response와 frontend type/client를 함께 변경
→ dev-api-contract

layout/component visual/interaction/responsive/accessibility/chart 작업
→ dev-ui-ux

OpenAPI/Swagger/Postman
→ dev-api-docs
```

## 중요한 구분

- `dev-tech-dispatch`는 Orchestrator planning skill이며 Coder/Reviewer runtime pinned capability가 아니다.
- `UI_SKILL_CANDIDATE`는 React/Next.js가 존재한다고 무조건 적용하지 않는다. **보이는 UI/interaction을 실제로 변경할 때만** 적용한다.
- `CROSS_STACK_SKILL_CANDIDATE`도 backend/frontend가 함께 존재한다는 이유만으로 항상 적용하지 않는다. API contract를 Task가 건드릴 때만 적용한다.
- 프로젝트 기존 pattern과 사용자 정책이 capability recommendation보다 우선한다.

## 회귀 검증

```bash
python3 custom-skills/orchestrator/dev-tech-dispatch/tests/test_detect_capabilities.py
```
