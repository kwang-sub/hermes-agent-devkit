---
name: dev-frontend-test
description: frontend 변경에서 기존 Vitest/Jest/Testing Library/Storybook/Playwright/Cypress stack을 감지해 functional·component·e2e·design conformance·visual regression 검증을 선택하는 capability skill.
version: 0.2.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, frontend, test, storybook, visual, playwright, vitest, jest, cypress, testing-library]
    related_skills: [dev-design-reference, dev-typescript-guidelines, dev-frontend-guidelines, dev-nextjs-feature, dev-ui-ux]
    requires_tools: [terminal]
---

# dev-frontend-test

Frontend test/verification 전용 capability다. 기존 project stack을 우선하며 test/catalog 도구를 검증 편의로 자동 도입하지 않는다.

## 탐지 우선순위

`package.json` scripts/dependencies와 기존 test/story 파일을 확인한다.

```text
Vitest / Jest
Testing Library
Storybook
Playwright
Cypress
기타 프로젝트 고유 runner
```

## Verification Mode

```text
FUNCTIONAL
COMPONENT
E2E
VISUAL_CONFORMANCE
VISUAL_REGRESSION
```

한 Task에서 필요한 mode만 사용한다.

## 변경별 기본 선택

```text
순수 함수/hook/state logic
→ FUNCTIONAL

component interaction/rendering
→ COMPONENT

form/validation/accessibility behavior
→ COMPONENT + accessible query 중심

routing/server-client integration
→ 기존 integration/page test

critical user journey
→ 기존 e2e가 있을 때 E2E

Approved IMAGE/Figma reference 기반 첫 구현
→ VISUAL_CONFORMANCE 후보

승인된 구현의 시각 회귀 보호
→ VISUAL_REGRESSION 후보
```

snapshot만으로 behavior correctness를 대체하지 않는다.

## Storybook Catalog

Storybook이 이미 설치돼 있고 project가 story를 사용하는 경우 다음을 우선 catalog한다.

```text
재사용 가능한 공용 component
독립적으로 이해 가능한 화면 component
여러 상태를 가진 component
chart/form 등 시각·상태 검증 가치가 큰 component
```

모든 작은 wrapper에 story를 만들지 않는다.

Design/Screen Spec에 실제로 필요한 상태가 있으면 project convention에 맞춰 예를 들어:

```text
Default
Loading
Empty
Error
Selected
Disabled
Positive / Negative
```

등을 표현한다.

Storybook이 없으면 `NOT_AVAILABLE`로 남기고 자동 설치하지 않는다.

## VISUAL_CONFORMANCE

목적은 **Approved Design Reference와 최초 구현의 의도 일치 확인**이다.

```text
Design Reference
- ChatGPT/디자이너 PNG
- Screenshot
- Figma approved frame/preview

Rendered Target
- Storybook story
- 실제 page/component
```

확인 대상:

```text
정보 구조
영역/요소 배치
상대적 크기/spacing
주요 typography/color
visual hierarchy
viewport별 승인된 responsive 구조
```

Reference가 이미지면 font rasterization, antialiasing, browser/OS 차이로 완전 pixel equality를 기본 요구하지 않는다.

기존 Playwright/visual matcher가 있으면 project threshold/mask/stable fixture를 사용한다. 최초 conformance 결과가 애매하면 자동 PASS로 확정하지 않고 Human Visual Review evidence를 요구한다.

```text
Design Conformance: PASS | MANUAL_PASS | FAIL | NOT_RUN | NOT_REQUIRED
```

## VISUAL_REGRESSION

장기 regression baseline은 **승인된 실제 browser rendering screenshot**이다.

```text
Approved Implementation
→ Browser Screenshot Golden
→ 이후 Current Rendering과 비교
```

Design Reference PNG를 regression golden과 동일시하지 않는다.

Playwright `toHaveScreenshot` 등 기존 visual mechanism이 있으면 다음을 안정화한다.

```text
고정 viewport
결정적인 test data
font loading
animation/transition 비활성 또는 안정화
시간/랜덤/네트워크 변동 통제
필요한 dynamic region mask
```

baseline update는 의도된 visual change 근거가 있을 때만 한다. 실패를 없애기 위해 snapshot을 무조건 갱신하지 않는다.

```text
Visual Regression: PASS | FAIL | NOT_RUN | NOT_REQUIRED
```

## Playwright / Storybook dependency 정책

```text
이미 존재
→ 기존 config/script/convention 재사용

없음
→ 이번 Task 검증 편의만으로 자동 설치하지 않음
→ manual rendered review 또는 기존 test stack 사용
→ 도입 필요 시 별도 dependency 결정
```

## Verification Budget

- affected spec/story/page부터 확인한다.
- 여러 test를 runner가 지원하면 한 invocation으로 묶는다.
- 동일 scope PASS를 단순 확신 확보용으로 반복하지 않는다.
- 전체 suite/build/e2e는 Task/risk/AC에서 필요할 때 implementation stable 이후 실행한다.
- visual conformance와 visual regression이 목적이 다르다면 결과도 별도로 기록한다.

## Handoff

```text
Skill: dev-frontend-test
Detected test/catalog stack
Verification Modes
Affected tests/stories/pages
Commands / Results
Storybook Catalog: UPDATED | NOT_REQUIRED | NOT_AVAILABLE
Design Conformance: PASS | MANUAL_PASS | FAIL | NOT_RUN | NOT_REQUIRED
Visual Regression: PASS | FAIL | NOT_RUN | NOT_REQUIRED
Human Visual Review: PASS | NOT_RUN | NOT_REQUIRED
Full suite: PASS | NOT_REQUIRED | FAIL_...
Residual risk
```
