---
name: dev-frontend-feature
description: Frontend 작업의 canonical entry point로 승인된 Design Reference 또는 기존 코드 기준을 TypeScript·React/Next.js·UI/UX·API contract·test capability와 조합한다.
version: 0.4.1
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, frontend, feature, design-reference, image, figma, ui, ux, typescript, react, nextjs]
    related_skills: [dev-design-reference, dev-official-docs-context, dev-typescript-guidelines, dev-frontend-guidelines, dev-nextjs-feature, dev-frontend-test, dev-node-dependencies, dev-api-contract, dev-figma-design, dev-ui-ux]
    requires_tools: [terminal, skill_view]
---

# dev-frontend-feature

Frontend 구현/검토의 canonical entry다. 실제 Task에 필요한 하위 capability만 lazy-load하며 Design Source 자체와 구현 기술을 분리한다.

## Frontend Mode

```text
REFERENCE_DRIVEN
- IMAGE 또는 FIGMA Reference가 있음
- dev-design-reference로 Normalized Design Evidence를 먼저 확보
- APPROVED는 구현 기준, REFERENCE는 방향 참고, DRAFT는 planning only

CODE_DRIVEN
- authoritative external Design Reference가 없음
- 현재 project component/token/style/화면이 source of truth
```

기존 `FIGMA_DRIVEN`은 호환 개념상 `REFERENCE_DRIVEN + Design Source=FIGMA`로 해석한다. 신규 Task에서는 `REFERENCE_DRIVEN`을 canonical 표현으로 사용한다.

## Design Source

```text
IMAGE
FIGMA
EXISTING_CODE
```

IMAGE와 FIGMA의 차이는 provider 단계에서만 다루고 이후 Coder/Reviewer는 Normalized Design Evidence를 공통 계약으로 사용한다.

## View Strategy / Implementation Architecture

Desktop/Web과 Mobile이 함께 범위에 들어오면 구현 전에 화면 단위 `View Strategy`를 확정한다.

```text
SHARED
- 동일한 정보 구조와 interaction
- viewport 차이가 작고 공통 component tree를 그대로 사용

RESPONSIVE
- 동일한 use case / 정보 구조 / 상태 흐름
- layout, order, visibility, size가 breakpoint에 따라 달라짐
- CSS media/container query와 기존 responsive utility를 우선

HYBRID
- 화면 shell/data/state는 공유
- 일부 section만 desktop/mobile 전용 presentation 필요

SPLIT_VIEW
- 정보 우선순위, navigation, interaction, content density 또는 user journey가 의미 있게 다름
- desktop/mobile presentation tree를 분리하되 data/business layer는 기본적으로 공유
```

화면 전체 전략을 기본값으로 하고 특정 section만 다른 전략이 필요하면 `Section Override`와 이유를 남긴다. 단순히 reference 이미지가 다르다는 이유만으로 `SPLIT_VIEW`를 선택하지 않고 정보 구조, interaction, state lifecycle, accessibility, data requirement 차이를 근거로 판단한다.

### 기본 Package / Folder 구조

프로젝트에 기존 feature/package convention이 있으면 그것을 우선한다. 기존 convention이 없을 때만 다음을 기본 구현 구조로 사용한다.

```text
src/features/<feature>/
├─ api/          # API client/query definition
├─ model/        # domain-facing frontend types / view model
├─ state/        # shared client state (필요한 경우만)
├─ hooks/        # shared orchestration/data hooks
└─ ui/
   ├─ common/    # desktop/mobile 공통 presentation
   ├─ desktop/   # desktop 전용 presentation
   └─ mobile/    # mobile 전용 presentation
```

빈 directory를 기계적으로 만들지 않는다. 프로젝트가 `components/`, `modules/`, `app/`, `pages/` 등 다른 convention을 사용하면 위 책임을 해당 구조에 매핑하고 unrelated package migration을 하지 않는다.

Next.js route/page component는 가능한 한 route binding과 화면 composition에 집중하고, feature-specific state/data/presentation 책임을 route 파일에 누적하지 않는다.

### Shared / Split 책임

기본 공유 대상:

```text
API client / query key / cache contract
request / response type
domain-facing model
business rule / formatter / selector
data-fetching hook
shared client state
validation rule
analytics event meaning
```

기본 분리 후보:

```text
layout composition
desktop/mobile navigation
interaction affordance
content density
platform-specific gesture / control
viewport별 presentation-only component
```

규칙:

- layout 차이만으로 API/hook/state를 복제하지 않는다.
- `desktopApi`, `mobileApi`, `desktopStore`, `mobileStore`를 UI 차이만으로 만들지 않는다.
- shared data hook 안에 presentation breakpoint 분기를 넣지 않는다.
- platform-specific hook은 gesture, keyboard, pointer/touch 등 실제 interaction 차이가 있을 때만 둔다.
- Desktop/Mobile variant가 같은 server state를 사용하면 fetch/query/cache owner를 공유하고 각 View에서 다시 요청하지 않는다.
- 두 View가 동시에 mount될 수 있는 구조에서 effect/subscription/analytics가 중복 실행되지 않도록 owner를 한 곳에 둔다.

### Strategy별 구현 규칙

```text
SHARED
→ 하나의 component tree
→ 공통 style/token 사용

RESPONSIVE
→ 하나의 semantic/component tree 우선
→ CSS media/container query 또는 project responsive utility로 layout 조정
→ 전체 화면을 JS viewport 분기로 교체하지 않음

HYBRID
→ shared screen/container + common UI
→ 필요한 section만 ui/desktop | ui/mobile로 분리
→ data/state owner는 shared layer 유지

SPLIT_VIEW
→ thin screen coordinator
→ DesktopView / MobileView를 명시적으로 분리
→ API/model/state/business logic은 기본 공유
→ 각 View 내부에서 동일 fetch/effect를 독립 소유하지 않음
```

SSR/SSG framework에서는 client viewport 값 때문에 server initial markup과 hydration 결과가 달라지는 구조를 만들지 않는다. viewport 기반 runtime 분기가 필요한 경우 기존 framework/project pattern을 확인하고 client boundary 또는 CSS 기반 전략을 선택한 근거를 남긴다.

### API Boundary

Desktop과 Mobile 화면 구성이 다르다는 사실만으로 Backend Response를 두 화면의 모든 필드를 합친 superset DTO로 만들지 않는다.

```text
동일 use case / 동일 resource
→ 기존 또는 하나의 shared API contract 우선
→ frontend selector / view model로 화면별 shape 생성

다른 use case / 다른 authorization / 큰 data-volume 또는 latency 차이
→ 별도 API contract 후보
→ dev-api-spec / dev-api-contract로 독립 판단
```

UI 구성 차이를 API endpoint 분리 근거로 사용하지 않는다. 반대로 실제 use case나 성능 요구가 다른데 하나의 비대한 응답으로 억지 통합하지 않는다.

### Planning / Handoff 필수 필드

Desktop/Mobile이 범위에 포함된 Frontend Task는 다음을 Plan과 Coder handoff에 남긴다.

```text
View Strategy: SHARED | RESPONSIVE | HYBRID | SPLIT_VIEW
View Strategy Rationale:
Platform Scope: DESKTOP | MOBILE | BOTH
Section Overrides: <section=strategy | NONE>
Package / View Plan:
Shared Implementation:
Split Implementation:
API Impact: NONE | SHARED_CONTRACT | CONTRACT_CHANGE
Responsive / Breakpoint Source:
Desktop/Mobile Verification Matrix:
```

## Coder 실행 순서

```text
1. Frontend package root 확인 후 Frontend Environment Gate 실행
2. Gate PASS 후 stack/package manager/version 확인
3. 외부 SDK/API·version-sensitive config/type 오류가 scope면 dev-official-docs-context Gate
4. dependency mutation이 실제 scope면 dev-node-dependencies mutation preflight
5. REFERENCE_DRIVEN | CODE_DRIVEN 결정
6. REFERENCE_DRIVEN이면 dev-design-reference load
7. Screen Spec / Design Evidence와 기존 component/token/style/API/test/package pattern 대조
8. Desktop/Mobile 범위면 View Strategy와 Package / View Plan 확정
9. Shared / Split 책임과 API Impact 확정
10. 필요한 하위 capability만 lazy-load
11. IMPLEMENTATION_SCOPE_READY 확정
12. 최소 변경 구현
13. 의미 있는 stateful/shared UI면 기존 Storybook catalog 갱신 검토
14. UI 변경이면 dev-ui-ux quality gate
15. affected test/typecheck/lint/build + Desktop/Mobile verification matrix 수행
16. handoff evidence 기록
```

## Frontend Environment Gate

모든 Node 기반 Frontend Task는 dependency 변경 여부와 무관하게 첫 Node command 전에 다음 Gate를 통과해야 한다.

```bash
python3 /opt/custom-skills/shared/dev-node-dependencies/scripts/node_environment_gate.py \
  --workspace "<Task Workspace>" \
  [--cwd "<package root relative to workspace>"]
```

정상 계약은 `pnpm + devEngines.runtime + devEngines.packageManager + pnpm-lock.yaml`이다. npm/yarn/bun 선언 또는 legacy lockfile, pnpm 계약 미완성은 구현 오류가 아니라 다음 환경 blocker로 분류한다.

```text
FRONTEND_ENVIRONMENT_GATE=BLOCKED
BLOCKER_CLASS=PROJECT_TOOLCHAIN_MIGRATION_REQUIRED
```

이 경우 현재 기능 Task에서 package manager migration을 암묵적으로 수행하지 않고 작업을 BLOCK한다. 특히 worker는 검증을 계속하기 위해 Windows/source worktree에서 `npm`, `npx`, `next`, `tsc`, 직접 `pnpm run`을 fallback으로 실행하지 않는다. source worktree의 `.next` 권한 수정·삭제를 반복해 canonical 검증을 우회하지도 않는다.

Gate PASS 이후 test/lint/typecheck/build는 반드시 `node_runtime.py`를 통해 Linux isolated workspace에서 실행한다. dependency mutation이 필요한 경우에만 같은 capability의 mutation preflight/Tirith 경로를 추가 적용한다.

## Lazy capability

- 외부 library/framework/SDK/API 공식 version evidence → `dev-official-docs-context`
- Design Reference 정규화 → `dev-design-reference`
- Figma provider read → `dev-figma-design`
- TypeScript type/config/nullability → `dev-typescript-guidelines`
- React component/state/form/browser behavior → `dev-frontend-guidelines`
- Next.js router/server-client/cache/metadata → `dev-nextjs-feature`
- Node dependency add/remove/restore/lockfile → `dev-node-dependencies`
- frontend unit/component/e2e/visual verification → `dev-frontend-test`
- backend↔frontend request/response contract → `dev-api-contract`
- visual/interaction/responsive/accessibility/chart → `dev-ui-ux`

React/Next.js가 존재한다는 이유만으로 모든 Skill을 로드하지 않는다. 다만 Node 기반 Frontend Task의 **환경 Gate는 항상 적용**하며, `dev-node-dependencies`의 dependency mutation/Tirith 절차는 package mutation이 실제 구현 범위일 때만 추가 적용한다.

## External Technology Documentation Gate

다음 중 하나면 production source 수정 전에 `skill_view("dev-official-docs-context")`를 적용한다.

```text
외부 SDK/library/API 신규 사용
인증/OAuth/Supabase/Firebase 등 외부 연동
Next.js/React/TypeScript 등 version-sensitive API 또는 config 변경
외부 dependency의 .d.ts / compiler compatibility 오류
현재 설치 version의 API signature에 불확실성이 있음
```

순서는 고정한다.

```text
actual resolved version
→ Context7 version-matched official docs
→ official upstream/local package type-source evidence
→ implementation
→ typecheck/test/build
```

Context7 provider 장애만으로 구현을 중단하지 않는다. 공식 upstream 또는 설치된 local type/source로 충분한 evidence가 있으면 fallback한다. 반대로 latest docs만 보고 현재 project에 없는 API를 도입하지 않는다.

외부 declaration 충돌은 앱 source 오류와 분리해 `DEPENDENCY_DECLARATION_COMPATIBILITY` 여부를 판단한다. 오류 origin이 `node_modules/**/*.d.ts` 또는 외부/generated declaration이고 application source error가 아니라면 해당 분류 evidence를 먼저 남긴다. 이를 숨기기 위해 `skipLibCheck=true`, `strict=false`, `patch-package`, node_modules patch, 임의 dependency/compiler downgrade·upgrade를 자동 적용하지 않는다. 호환성 변경이 필요하면 별도 승인된 해결 범위로 분리한다.

## Dependency Mutation

새 package 추가·삭제·version 변경 또는 lockfile 갱신이 필요하면 production source 수정 전에 `skill_view("dev-node-dependencies")`를 적용한다.

```text
exact package root
→ packageManager/lockfile evidence
→ Node/package-manager version
→ manifest/node_modules 상태
→ Tirith package security preflight
→ dependency mutation 1회
→ manifest + canonical lockfile 검증
```

`node_modules`에만 존재하는 package는 정상 dependency evidence가 아니다. `package.json`/canonical lockfile에 없으면 `EXTRANEOUS_PRESENT`로 취급하고 정상 manifest mutation이 필요하다.

Tirith가 `analysis_incomplete`를 반환하면 security finding으로 오인해 package manager를 바꾸거나 install flag를 추가하지 않는다. `dev-node-dependencies`의 daemon 재검사 1회 경로만 사용하고, 이후에도 verdict가 불완전하면 headless worker에서 반복하지 않고 BLOCK한다.

## REFERENCE_DRIVEN 우선순위

`Design Status=APPROVED`일 때:

```text
사용자/Task 명시 요구
→ Approved Reference의 OBSERVED evidence
→ project Design System/component/token/convention
→ INFERRED evidence
→ dev-ui-ux quality guardrail
→ 일반 best practice
```

`REFERENCE` 상태는 source of truth가 아니므로 project pattern보다 위에 놓지 않는다.

Reference와 전역 token/component가 충돌하면 현재 Task 범위를 넘어 global migration하지 않는다. `Design Conflict`와 `Improvement Deferred`로 남긴다.

## IMAGE Reference Package

프로젝트에 별도 convention이 없으면:

```text
docs/ui/screens/<screen>/
├─ reference.png
└─ screen-spec.md
```

을 권장한다.

`reference.png`는 보이는 계약이고 `screen-spec.md`는 interaction/state/responsive/API 같은 보이지 않는 계약이다.

이미지에서 직접 확인할 수 없는 값은 `INFERRED` 또는 `UNKNOWN`으로 남긴다. screenshot을 보고 exact token/CSS 값을 사실처럼 만들지 않는다.

## Storybook Catalog

Storybook이 이미 프로젝트에 있거나 project convention이 Storybook을 사용하면 다음 UI를 catalog 후보로 본다.

```text
공용 UI Component
독립적으로 의미 있는 화면 Component
여러 상태를 가진 Component
복잡한 Chart / Form
```

작은 내부 wrapper/layout helper까지 story를 강제하지 않는다.

상태가 의미 있으면 가능한 범위에서 다음을 story로 분리한다.

```text
Default
Loading
Empty
Error
Selected / Disabled / Positive / Negative 등 실제 domain state
```

Storybook이 없는 프로젝트에 이번 화면 구현만을 이유로 dependency를 자동 추가하지 않는다. 도입이 필요하면 dependency/architecture 결정으로 Standard Flow에서 별도 승인한다.

## Visual Verification

시각 검증은 두 목적을 구분한다.

```text
DESIGN_CONFORMANCE
Approved Design Reference ↔ 최초 구현 결과
목표: 구조/배치/시각 hierarchy/주요 visual intent 일치

VISUAL_REGRESSION
승인된 실제 browser screenshot ↔ 이후 구현 결과
목표: 이미 승인된 구현의 의도치 않은 visual 변경 탐지
```

ChatGPT/디자인 PNG를 곧바로 장기 regression golden으로 사용하지 않는다. 최초 구현 승인 후 실제 browser screenshot을 regression baseline으로 사용한다.

실제 실행 규칙은 `dev-frontend-test`를 따른다.

## CODE_DRIVEN

```text
사용자/Task 명시 요구
→ project Design System/component/token/convention
→ current screen pattern
→ dev-ui-ux quality guardrail
→ 일반 best practice
```

## Reviewer 적용

Reviewer는 기존 `dev-code-review`의 diff-first/verification reuse 계약을 유지하면서 다음을 추가한다.

- Frontend Mode / Design Source / Status / Fidelity를 확인한다.
- Desktop/Mobile 범위면 View Strategy와 실제 package/component 분리가 Plan과 일치하는지 확인한다.
- `SPLIT_VIEW`/`HYBRID`에서 API/model/state/hooks가 presentation 차이만으로 불필요하게 복제되지 않았는지 확인한다.
- `SHARED`/`RESPONSIVE`에서 동일 semantic tree를 불필요하게 desktop/mobile 별도 tree로 복제하지 않았는지 확인한다.
- Desktop/Mobile 차이를 이유로 Backend API가 불필요한 superset DTO 또는 중복 endpoint로 확장되지 않았는지 확인한다.
- REFERENCE_DRIVEN이면 Coder의 Normalized Design Evidence와 `screen-spec.md`를 우선 재사용한다.
- fidelity finding에 원본이 필요할 때만 IMAGE/Figma Reference를 다시 확인한다.
- `OBSERVED`, `INFERRED`, `UNKNOWN` 경계를 Coder가 무너뜨리지 않았는지 확인한다.
- approved reference와 project Design System 충돌을 global redesign 요구로 확대하지 않는다.
- 외부 기술 변경이면 `Documentation Evidence`의 detected/resolved version, Version Match, local type/source, compiler evidence를 확인한다.
- dependency 변경이 있으면 `dev-node-dependencies`의 package root/manager/lockfile/Tirith evidence를 확인한다.
- Storybook/Playwright가 없는 프로젝트에 review 단계에서 새 dependency 도입을 강제하지 않는다.

## Handoff

```text
Frontend Mode: REFERENCE_DRIVEN | CODE_DRIVEN
Design Source: IMAGE | FIGMA | EXISTING_CODE
Design Status: DRAFT | REFERENCE | APPROVED | N/A
Design Fidelity: STRUCTURE | VISUAL | HIGH | N/A
Reference: <repo path | Figma URL | current code>
Screen Spec: <path | none>
View Strategy: SHARED | RESPONSIVE | HYBRID | SPLIT_VIEW | N/A
View Strategy Rationale:
Platform Scope: DESKTOP | MOBILE | BOTH | N/A
Section Overrides: <... | NONE>
Package / View Plan:
Shared Implementation:
Split Implementation:
API Impact: NONE | SHARED_CONTRACT | CONTRACT_CHANGE | N/A
Responsive / Breakpoint Source:
Desktop/Mobile Verification Matrix:
Observed / Inferred / Unknown:
- ...
Applied Capability Skills:
- ...
Frontend Environment Gate: PASS | BLOCKED
Frontend Environment Blocker Class: NONE | PROJECT_TOOLCHAIN_MIGRATION_REQUIRED | DEVKIT_RUNTIME_CAPABILITY_MISSING | PROJECT_STRUCTURE_INVALID
Verification Runtime: linux-isolated-node-runtime | NOT_RUN
Source Verification Fallback: FORBIDDEN
Documentation Required: yes | no
Documentation Ready: pass | partial | blocked | NOT_REQUIRED
Documentation Version Match: EXACT | COMPATIBLE | LATEST_ONLY | LOCAL_ONLY | UNKNOWN | NOT_REQUIRED
Official/Local Type Evidence:
- ...
Node Dependency Preflight: PASS | BLOCKED | NOT_REQUIRED
Package Root / Manager / Lockfile: <evidence | NOT_REQUIRED>
Tirith Package Preflight: allow | approval_required | unavailable | NOT_REQUIRED
Component/Token Reuse:
- ...
Storybook Catalog: UPDATED | NOT_REQUIRED | NOT_AVAILABLE
Design Conformance: PASS | MANUAL_PASS | NOT_RUN | NOT_REQUIRED
Visual Regression: PASS | NOT_RUN | NOT_REQUIRED
Design Conflicts:
- ...
Verification:
- ...
Residual Risk:
- ...
```

## 불변식

- Node 기반 Frontend Task는 첫 Node command 전에 Frontend Environment Gate를 통과한다.
- Gate BLOCKED 상태에서 source worktree 직접 npm/npx/next/tsc/pnpm 검증으로 fallback하지 않는다.
- test/lint/typecheck/build는 PASS 이후 `node_runtime.py` Linux isolated workspace에서만 실행한다.
- DRAFT/REFERENCE를 APPROVED로 임의 승격하지 않는다.
- 이미지 추정치를 exact design fact로 바꾸지 않는다.
- Approved Reference 일치를 이유로 unrelated global style/token refactor를 하지 않는다.
- Desktop/Mobile 차이만으로 API/model/state/data hook을 중복 구현하지 않는다.
- View Strategy 없이 desktop/mobile component tree를 임의 분기하지 않는다.
- project package convention이 있는데 feature-first 구조로 일괄 migration하지 않는다.
- dependency/state/form/query/UI/test library를 편의상 추가하지 않는다.
- 외부 기술 변경에서 actual resolved version 확인 전에 latest 문법을 도입하지 않는다.
- Context7 조회 성공을 typecheck/test/build 성공으로 대체하지 않는다.
- package mutation이 필요한 경우 `node_modules`를 manifest/lockfile 대신 source of truth로 사용하지 않는다.
- Tirith `analysis_incomplete`를 scanner 우회나 다른 package manager 사용의 근거로 삼지 않는다.
- Design Conformance reference와 Visual Regression golden을 동일 개념으로 취급하지 않는다.
- Reviewer가 독립성을 이유로 같은 이미지/Figma/test evidence를 불필요하게 반복 조회하지 않는다.
