# Stack / Capability Skill Extension Guide

이 문서는 `coding-rules.md`, `implementation-decision-rules.md`, `project-pattern-rules.md`, 데이터 작업에서는 `data-design-rules.md`를 기반으로 특정 언어·프레임워크·기술 기능 Skill을 추가할 때의 설계 규칙이다.

## 1. 계층

```text
Foundation
- coding-rules.md
- implementation-decision-rules.md
- project-pattern-rules.md
- data-design-rules.md (data affected area)
        ↓
Workflow
- dev-project-pattern
- dev-tech-dispatch
- dev-breakdown
- dev-implement-plan
- dev-code-review
        ↓
Capability Entry
- Backend dev-*
- Frontend dev-frontend-feature
- Data dev-data-feature
        ↓
Lazy Sub-capability
        ↓
Project convention
        ↓
Implementation / Review
```

## 2. Workflow와 Capability는 다른 축

```text
Workflow = 작업 크기/모호성/승인/workspace/review lifecycle
Capability = 어떤 기술 지식과 검증이 필요한가
```

## 3. dev-tech-dispatch

canonical resolver는 bounded build/dependency/schema manifest에서 stack과 DB vendor candidate를 감지한다.

```text
manifest evidence
→ stack / database vendor candidate
→ baseline capability entry candidate
```

source 수정, architecture 선택, dependency 설치, runtime pin 결정, Kanban 생성은 하지 않는다. `Stack Detection != Skill Loading`이다.

`dev-official-docs-context`는 stack이 존재한다는 이유로 자동 load하는 baseline이 아니다. 외부 API surface, version-sensitive 설정, dependency declaration compatibility처럼 **Task 책임이 실제로 공식 문서 evidence를 필요로 할 때** capability entry가 lazy-load한다.

## 4. Capability set

### Backend

```text
dev-java-guidelines
dev-kotlin-guidelines
dev-spring-guidelines
dev-spring-feature
dev-spring-data
dev-spring-test
dev-spring-refactor
```

### Frontend canonical entry

```text
dev-frontend-feature
```

### Frontend design/reference

```text
dev-design-reference
dev-figma-design            # optional Figma provider
```

### Frontend / Node lazy capability

```text
dev-official-docs-context   # version-first official docs/local type evidence
dev-typescript-guidelines
dev-frontend-guidelines
dev-nextjs-feature
dev-frontend-test
dev-node-dependencies       # mandatory frontend environment gate + package add/remove/restore/lockfile + security preflight
dev-ui-ux
```

`dev-node-dependencies`는 Frontend 전용이 아니다. 다만 Node 기반 Frontend Task에서는 environment gate 부분을 항상 적용하고, package mutation/Tirith 절차는 실제 dependency 변경이 Task 책임일 때만 추가 적용한다.

### Data canonical entry

```text
dev-data-feature
```

### Data lazy capability

```text
dev-data-modeling
dev-db-schema
dev-db-query
dev-db-migration
dev-db-performance
```

### Cross-stack

```text
dev-official-docs-context
dev-api-contract
dev-api-docs
dev-api-spec
```

## 5. Capability 공통 실행 순서

```text
1. stack/vendor/version evidence 탐색
2. 외부 기술의 API/config가 Task 책임이면 official-docs evidence 확보
3. 기존 동일/유사 구현 검색
4. 기존 convention 결정
5. assumption/정책 충돌 확인
6. implementation-decision-rules 필요성 사다리 적용
7. 최소 변경 구현
8. capability-specific verification
9. reviewer handoff evidence
```

새 dependency/framework/language/DB migration tool을 기본값으로 추가하지 않는다.

### Official docs evidence boundary

외부 library/framework/SDK/API를 구현할 때는 다음 우선순위를 사용한다.

```text
실제 installed/resolved version
→ Context7 version-matched official docs
→ vendor 공식 문서/공식 upstream repository
→ 설치된 local source/type/JAR signature
→ compiler/typecheck/test/build
```

Context7는 provider이며 correctness 판정자가 아니다. `LATEST_ONLY` 문서를 현재 설치 버전의 API로 간주하지 않고, provider 장애가 있으면 공식 upstream/local evidence로 fallback한다. 문서 조회를 위해 `npx`, global package, 임시 dependency를 설치하지 않는다.

## 6. Java / Kotlin / Spring

```text
Java convention → dev-java-guidelines
Kotlin convention → dev-kotlin-guidelines
Spring common → dev-spring-guidelines
Controller/Service/DTO/Validation/Exception → dev-spring-feature
JPA/Repository/QueryDSL/Converter/Paging → dev-spring-data
Spring/JPA test → dev-spring-test
외부 SDK/API/version-sensitive client → dev-official-docs-context
```

Java/Kotlin은 first-class language capability다. Java-only project는 `dev-java-guidelines`, Kotlin-only project는 `dev-kotlin-guidelines`, Java + Kotlin mixed project에서는 실제 changed source 언어에 적용한다.

JPA Query 정책은 Method Query → QueryDSL → 근거 있는 Native Query 순서다.

## 7. Frontend entry와 Design Reference

실제 frontend Task는 `dev-frontend-feature`를 runtime entry로 한다.

```text
외부 SDK/API/version-sensitive config/type error → dev-official-docs-context
Design Reference IMAGE/Figma → dev-design-reference
TypeScript → dev-typescript-guidelines
React/component/state/form/browser → dev-frontend-guidelines
Next.js → dev-nextjs-feature
Node package add/remove/restore → dev-node-dependencies
functional/component/e2e/visual → dev-frontend-test
Figma provider → dev-figma-design
visual/interaction/responsive/accessibility/chart → dev-ui-ux
API integration → dev-api-contract
```

repository가 React/Next.js를 포함한다는 이유만으로 frontend skill을 로드하지 않는다. 하지만 Frontend Work Unit으로 확정된 뒤에는 dependency mutation 여부와 무관하게 `dev-node-dependencies`의 Frontend Environment Gate를 첫 Node command 전에 적용한다. mutation/Tirith 절차는 dependency 변경이 있을 때만 추가한다. 외부 기술을 사용하지 않는 순수 UI/domain 작업에 `dev-official-docs-context`를 기계적으로 적용하지 않는다.

### Frontend Node environment boundary

모든 Node 기반 Frontend Work Unit은 첫 Node command 전에 `node_environment_gate.py`를 실행한다.

```text
pnpm canonical toolchain PASS
→ Linux isolated node_runtime verification 허용

npm/yarn/bun 또는 legacy lockfile / pnpm 계약 미완성
→ PROJECT_TOOLCHAIN_MIGRATION_REQUIRED
→ 현재 기능 Work Unit BLOCK
→ source worktree npm/npx/next/tsc/pnpm fallback 금지
```

toolchain migration은 현재 기능 구현과 별도 승인 Work Unit으로 분리한다. host/source `.next` 정리나 권한 변경을 canonical verification의 대체 수단으로 사용하지 않는다.

### pnpm dependency build policy

dependency의 install/build script 승인은 pnpm 표준 project config를 사용한다.

```text
pnpm-workspace.yaml
└─ allowBuilds
   ├─ package@exact-version: true
   └─ package@exact-version: false
```

Hermes 전용 allowlist를 만들지 않는다. `strictDepBuilds=true`를 fail-closed 기준으로 유지하고 `dangerouslyAllowAllBuilds=true`, `strictDepBuilds=false`, `pnpm approve-builds --all`을 자동 사용하지 않는다.

`ERR_PNPM_IGNORED_BUILDS`가 발생하면 미검토 package/version을 한 번에 사용자에게 보여 승인/거부를 받는다. 결정은 `pnpm-workspace.yaml`에 Git 관리하고 같은 matcher는 다시 묻지 않는다. 새 version은 기존 exact matcher와 다르므로 다시 검토한다. build policy 변경은 dependency fingerprint를 변경시켜 isolated frozen restore를 다시 요구한다.

### Node dependency mutation boundary

Node dependency 변경은 source 구현과 분리된 compatibility/security boundary로 취급한다.

```text
package.json / canonical lockfile
→ exact package root
→ package manager + version
→ Node version evidence
→ node_modules declared / EXTRANEOUS_PRESENT 판정
→ Tirith exact-command preflight
→ package mutation 1회
→ manifest + lockfile verification
```

`node_modules`는 source of truth가 아니다. package가 물리적으로 존재해도 manifest/lockfile에 없으면 `EXTRANEOUS_PRESENT`다.

Tirith의 `analysis_incomplete`는 positive security finding과 구분한다. dependency helper는 Tirith daemon을 준비한 뒤 동일 command를 정확히 1회 재검사할 수 있지만, incomplete를 allow로 재분류하거나 approval을 끄지 않는다. 재검사 후에도 warn/block이면 headless worker는 반복 실행하지 않고 BLOCK한다.

외부 `.d.ts`와 compiler/platform declaration 충돌은 앱 source 오류와 분리해 `DEPENDENCY_DECLARATION_COMPATIBILITY`로 evidence화한다. 이를 감추기 위한 `skipLibCheck=true`, strictness 완화, `patch-package`, node_modules patch, 임의 버전 downgrade/upgrade는 자동 적용하지 않는다. 호환성 수정이 필요하면 별도 승인 Work Unit으로 분리한다.

## 8. REFERENCE_DRIVEN / CODE_DRIVEN

```text
REFERENCE_DRIVEN
사용자/Task
→ Design Source IMAGE | FIGMA
→ dev-design-reference Normalized Evidence
→ APPROVED OBSERVED evidence
→ project component/token/convention
→ INFERRED evidence
→ dev-ui-ux quality guardrail

CODE_DRIVEN
사용자/Task
→ Design Source EXISTING_CODE
→ project component/token/convention
→ current screen pattern
→ dev-ui-ux quality guardrail
```

Design Status:

```text
DRAFT      = planning only
REFERENCE  = 방향 참고
APPROVED   = 구현 기준
```

기존 `FIGMA_DRIVEN`은 `REFERENCE_DRIVEN + FIGMA`의 legacy 표현이다.

### IMAGE Reference Package

프로젝트에 별도 UI 문서 convention이 없으면:

```text
docs/ui/screens/<screen>/
├─ reference.png
└─ screen-spec.md
```

을 권장한다. `reference.png`은 보이는 계약, `screen-spec.md`는 state/interaction/responsive/API 등 보이지 않는 계약이다. Design Evidence는 `OBSERVED | INFERRED | UNKNOWN`으로 나눈다.

### Figma provider

Figma는 optional provider다. 현재 `dev-figma-design`은 공식 REST API의 read-only endpoint를 사용한다.

```text
GET /v1/files/:key/nodes
GET /v1/files/:key (bounded/explicit)
GET /v1/images/:key
```

Personal/Plan REST token은 `X-Figma-Token`, OAuth는 Bearer를 사용한다. token은 환경변수에서만 읽는다. Provider 구현이 바뀌어도 `dev-design-reference`의 Normalized Design Evidence 계약은 유지한다.

## 9. Storybook / Visual Verification

Storybook이 기존 프로젝트에 있으면 실제 UI Catalog로 사용한다.

```text
공용 component
독립적인 화면 component
여러 상태를 가진 component
chart/form 등 시각 상태가 중요한 component
```

에 story를 우선하고 모든 작은 wrapper에는 강제하지 않는다.

시각 검증은 두 목적을 분리한다.

```text
DESIGN_CONFORMANCE
Approved IMAGE/Figma Reference ↔ 최초 구현 rendering

VISUAL_REGRESSION
Approved browser screenshot golden ↔ 이후 rendering
```

Design Reference PNG를 장기 Visual Regression golden과 동일시하지 않는다. Playwright/Storybook이 이미 있으면 기존 config/threshold/fixture를 재사용한다. 없으면 이번 작업만을 위해 자동 dependency 추가하지 않는다.

## 10. Data entry와 lazy-load

Data/DB Task는 다음 두 경로를 구분한다.

```text
기존 승인 schema + JPA 구현만 변경
→ dev-spring-data

데이터 모델/DBML/schema/SQL dialect/migration/performance 자체가 Task 책임
→ dev-data-feature
```

`dev-data-feature` 하위 lazy capability:

```text
model/relationship/cardinality/DBML → dev-data-modeling
PK/FK/UNIQUE/type/index/constraint → dev-db-schema
SQL/query semantics/dialect → dev-db-query
DDL/backfill/deployment compatibility → dev-db-migration
execution plan/index/locking/statistics → dev-db-performance
```

공통 data 판단은 DBMS 중립으로 수행하고, 실제 physical 차이가 필요한 경우에만 MSSQL/MySQL/MariaDB/PostgreSQL/Oracle vendor reference를 읽는다. DB driver가 Repository에 있다는 이유만으로 Data entry를 자동 적용하지 않는다.

## 11. DBML / Human ERD Review

기존 프로젝트 표준이 없으면 `docs/data/schema.dbml`을 canonical relational model 기본값으로 사용한다.

```text
LOGICAL_RELATIONAL (기본)
→ vendor-neutral relation/key/nullability intent

PHYSICAL
→ target DBMS/version이 확정된 project에서 실제 physical mapping 허용
```

DBML Canvas는 IntelliJ에서 `schema.dbml`을 시각화하는 Human View로 사용할 수 있다. DevKit runtime은 Plugin 설치에 의존하지 않는다. Mermaid는 설명용 파생 View이며 DBML과 독립적인 canonical model로 중복 관리하지 않는다.

의미 있는 model 변경은 기존 Plan Approval에서 proposed DBML/table/relationship을 명시적으로 보여 `Data Model Gate`를 함께 충족할 수 있다.

## 12. UI/UX adapter

`dev-ui-ux`는 Design Source의 IMAGE/Figma 차이를 소유하지 않고 정규화된 Design Evidence와 실제 UI 품질에 집중한다.

```text
Approved Design Reference / project Design System
→ current component/token pattern
→ dev-ui-ux baseline
```

accessibility, interaction, responsive, typography/color, reduced motion, form feedback, navigation, chart semantics를 보호한다.

## 13. API Contract

`dev-api-contract`는 framework 독립 capability다.

```text
method/path
request/query/header
success/error body
field name/nullability
date/time/money/decimal
enum/paging/auth
```

기존 OpenAPI-generated client가 있으면 재사용하고 code generation을 자동 도입하지 않는다.

## 14. Verification

Frontend/Node는 기존 package manager/test runner를 사용한다. dependency 변경이면 package manager compatibility와 canonical lockfile 검증을 먼저 통과해야 한다.

```text
Frontend Environment Gate + pnpm build policy (Node 기반 Frontend이면 항상)
→ Official docs/version evidence (외부 기술 변경 시)
→ Node dependency preflight (dependency mutation 시)
→ Tirith package preflight (해당 시)
→ affected functional/component test
→ typecheck
→ lint
→ related integration/e2e
→ 필요한 경우 build
→ 필요한 경우 DESIGN_CONFORMANCE
→ 승인 후 필요한 경우 VISUAL_REGRESSION baseline/검증
```

Data는 Task 성격에 따라 다음을 사용한다.

```text
DBML → lightweight guard + project parser/DBML Canvas manual review
query → fixture/integration/result semantics
migration → clean/upgrade/backfill/compatibility test
performance → execution plan + before/after evidence
```

새 runner/library를 검증 편의로 추가하지 않고 실행하지 않은 검증을 PASS라고 보고하지 않는다.

## 15. Reviewer evidence

```text
Skill / Applied Capability Skills
Detected stack/vendor/version
Pattern References
Documentation Required / Ready / Version Match (외부 기술 변경 시)
Context7/Official upstream/Local type evidence (해당 시)
Frontend Mode / Design Source / Status / Fidelity (해당 시)
Reference / Screen Spec (해당 시)
Observed / Inferred / Unknown (해당 시)
Node package root / manager / version / lockfile (dependency 변경 시)
pnpm build policy file / approved exact matchers / denied matchers (해당 시)
Tirith package preflight / retry evidence (dependency 변경 시)
Component/Token Reuse (해당 시)
Storybook Catalog / Design Conformance / Visual Regression (해당 시)
Data Task Class / Data Model Status / DBML Path (해당 시)
Schema/Query/Migration/API/UI strategy
Verification
Intentional Deviations
Design Conflicts / Improvement Deferred
Residual Risk
```

Reviewer는 실제 diff 판단에 필요한 capability만 읽는다.

## 16. Skill 추가 체크리스트

```text
[ ] Foundation만으로 해결할 수 없는 전문 기능인가
[ ] 반복 가능한 작업인가
[ ] 기존 Skill과 역할이 겹치지 않는가
[ ] stack/vendor/task detection이 정의됐는가
[ ] dependency/migration tool 정책이 정의됐는가
[ ] verification/evidence가 정의됐는가
[ ] Public Skill/provider/tool source/version/security를 검토했는가
[ ] runtime pin 대신 lazy-load가 적합한지 검토했는가
```
