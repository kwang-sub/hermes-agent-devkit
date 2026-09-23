---
name: dev-frontend-test
description: frontend 변경에서 기존 Vitest/Jest/Testing Library/Storybook/Playwright/Cypress stack을 감지해 functional·component·e2e·design conformance·visual regression 검증을 선택하는 capability skill.
version: 0.3.3
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, frontend, test, storybook, visual, playwright, vitest, jest, cypress, testing-library]
    related_skills: [dev-design-reference, dev-typescript-guidelines, dev-frontend-guidelines, dev-nextjs-feature, dev-ui-ux, dev-node-dependencies]
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

## View Strategy / Platform Verification

`dev-frontend-feature`의 View Strategy가 `BOTH` platform scope를 가지면 Desktop/Mobile 검증 범위를 명시한다.

```text
SHARED
→ 대표 viewport + boundary viewport
→ 동일 behavior/state가 유지되는지 확인

RESPONSIVE
→ Desktop + Mobile viewport 최소 확인
→ layout/order/visibility 변화와 동일 interaction/state 확인

HYBRID
→ common 영역 + desktop 전용 section + mobile 전용 section 각각 확인
→ shared state/API owner가 variant마다 중복 실행되지 않는지 확인

SPLIT_VIEW
→ DesktopView / MobileView를 각각 독립 화면처럼 검증
→ 같은 use case면 동일 business/API contract를 만족하는지 확인
→ navigation/interaction/accessibility가 각 View에서 완결되는지 확인
```

Project에 기존 viewport matrix가 있으면 그대로 사용한다. 없으면 Design Reference/Screen Spec의 승인 viewport를 우선하고, 임의의 device catalog 전체를 테스트하지 않는다.

검증 계획은 다음 형태로 남긴다.

```text
Desktop/Mobile Verification Matrix:
- Desktop <viewport>: <states / interaction / visual mode>
- Mobile <viewport>: <states / interaction / visual mode>
- Shared owner check: <fetch/cache/effect/subscription>
```

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

## Frontend Verification Environment Gate

test/lint/typecheck/build를 선택하기 전에 반드시 환경 Gate evidence를 확보한다.

```bash
python3 /opt/custom-skills/shared/dev-node-dependencies/scripts/node_environment_gate.py \
  --workspace "<Task Workspace>" \
  [--cwd "<package root relative to workspace>"]
```

`FRONTEND_ENVIRONMENT_GATE=BLOCKED`이면 모든 canonical verification을 `NOT_RUN`으로 남기고 즉시 BLOCK한다. source worktree에서 `npm test`, `npm run build`, `npx`, `next build`, `tsc`, 직접 `pnpm run`을 실행해 우회하지 않는다. host/source `.next` 권한 정비나 stale generated type 삭제를 canonical 해결책으로 사용하지 않는다.

## Hermes Node Runtime Isolation

Hermes Agent DevKit의 Node package manager는 pnpm으로 고정한다. Node/pnpm 버전은 별도 Hermes 파일이 아니라 프로젝트 `package.json`의 `devEngines.runtime` / `devEngines.packageManager`를 사용한다.

Windows bind-mounted source에서 frontend 검증을 직접 실행하지 않는다. `node_runtime.py`가 package source를 `/opt/data/node/workspaces/.../source`로 동기화한 뒤 Linux 격리 workspace에서 test/lint/typecheck/build를 실행한다. 내부 상태가 root/다른 UID 소유이면 권한을 자동 보정하며 계속하지 않고 환경 blocker로 중단한다.

```bash
python3 /opt/custom-skills/shared/dev-node-dependencies/scripts/node_runtime.py \
  --workspace "<Task Workspace>" \
  [--cwd "<package root relative to workspace>"] \
  -- pnpm run <script>
```

예:

```bash
python3 /opt/custom-skills/shared/dev-node-dependencies/scripts/node_runtime.py \
  --workspace "$WORKSPACE" \
  --cwd "chagok-frontend" \
  -- pnpm run typecheck

python3 /opt/custom-skills/shared/dev-node-dependencies/scripts/node_runtime.py \
  --workspace "$WORKSPACE" \
  --cwd "chagok-frontend" \
  -- pnpm run build
```

runtime helper 계약:

```text
package source             → Linux isolated workspace로 sync
host node_modules/.next    → sync 제외
host *.tsbuildinfo         → sync 제외
isolated node_modules      → dependency fingerprint 동일 시에만 재사용
package/lock fingerprint 변경 → 기존 isolated node_modules 폐기 + frozen restore
isolated framework output  → 검증 시작마다 초기화
pnpm home/store            → /opt/data/node
동일 Task workspace 명령    → workspace lock으로 직렬화
Node runtime               → package.json devEngines.runtime
pnpm version               → package.json devEngines.packageManager
```

따라서 Windows에서 같은 worktree의 `next dev`가 실행 중이어도 host `.next/dev/types`와 Hermes `.next/types`가 하나의 TypeScript program에 섞이지 않는다. Next.js `distDir` 같은 프로젝트 전용 우회 설정은 필요하지 않다.

isolated `node_modules`가 아직 준비되지 않았거나 dependency fingerprint가 바뀌었다면 `dev-node-dependencies` preflight가 반환한 `RESTORE_WORKDIR`에서 exact `pnpm install --frozen-lockfile`을 Tirith actual guard를 거쳐 실행한다. 성공 후 `RESTORE_MARK_COMMAND`를 실행해 현재 `package.json + pnpm-lock.yaml` fingerprint를 기록한 뒤 검증한다.

dependency 추가는 source package root에서 exact `pnpm add --lockfile-only ...`를 수행해 `package.json`과 `pnpm-lock.yaml`만 갱신한다. 실제 dependency tree는 isolated workspace의 frozen restore가 소유한다.

## Handoff

```text
Skill: dev-frontend-test
Detected test/catalog stack
Verification Modes
View Strategy: SHARED | RESPONSIVE | HYBRID | SPLIT_VIEW | N/A
Desktop/Mobile Verification Matrix
Affected tests/stories/pages
Commands / Results
Frontend Environment Gate: PASS | BLOCKED
Environment Blocker Class: NONE | PROJECT_TOOLCHAIN_MIGRATION_REQUIRED | DEVKIT_RUNTIME_CAPABILITY_MISSING | PROJECT_STRUCTURE_INVALID
Source Verification Fallback: FORBIDDEN
Node Runtime Isolation: PASS | NOT_REQUIRED | BLOCKED
Node Runtime Cache Root: /opt/data/node | NOT_REQUIRED
Node Workspace Lock: PASS | NOT_REQUIRED | BLOCKED
Storybook Catalog: UPDATED | NOT_REQUIRED | NOT_AVAILABLE
Design Conformance: PASS | MANUAL_PASS | FAIL | NOT_RUN | NOT_REQUIRED
Visual Regression: PASS | FAIL | NOT_RUN | NOT_REQUIRED
Human Visual Review: PASS | NOT_RUN | NOT_REQUIRED
Full suite: PASS | NOT_REQUIRED | FAIL_...
Residual risk
```
