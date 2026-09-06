---
name: dev-frontend-test
description: frontend 변경에서 프로젝트가 이미 사용하는 Vitest/Jest/Testing Library/Playwright/Cypress 등 test stack을 감지하고 가장 가까운 affected test와 최소 회귀 검증을 선택하는 capability skill.
version: 0.1.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, frontend, test, vitest, jest, playwright, cypress, testing-library]
    related_skills: [dev-typescript-guidelines, dev-frontend-guidelines, dev-nextjs-feature, dev-ui-ux]
    requires_tools: [terminal]
---

# dev-frontend-test

Frontend test/verification 전용 capability다.

## 탐지 우선순위

`package.json` scripts/dependencies와 기존 test 파일을 확인해 실제 stack을 따른다.

```text
Vitest / Jest
Testing Library
Playwright
Cypress
기타 프로젝트 고유 runner
```

새 test library를 편의를 위해 추가하지 않는다.

## 변경별 기본 선택

```text
순수 함수/hook/state logic
→ unit test

component interaction/rendering
→ 기존 component test

form/validation/accessibility behavior
→ interaction + accessible query 중심 test

routing/server-client integration
→ 기존 integration/page test

critical user journey
→ 기존 e2e가 있을 때 affected e2e
```

snapshot만으로 behavior correctness를 대체하지 않는다.

## Verification Budget

- affected spec/test부터 실행한다.
- 여러 test를 runner가 지원하면 한 invocation으로 묶는다.
- 동일 scope PASS를 단순 확신 확보용으로 반복하지 않는다.
- 전체 suite는 Task/risk/AC에서 필요할 때 implementation stable 이후 실행한다.
- 실패가 unrelated인지 판단하려면 changed scope와 direct impact evidence를 먼저 본다.

## Handoff

```text
Skill: dev-frontend-test
Detected test stack
Affected tests
Commands / Results
Full suite: PASS | NOT_REQUIRED | FAIL_...
Residual risk
```
