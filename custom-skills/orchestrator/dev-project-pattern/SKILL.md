---
name: dev-project-pattern
description: 개발 계획 전에 Bootstrap 기술 스택 캐시와 대상 Repository의 기존 구조·코드·UI·디자인 Reference·데이터·테스트 패턴을 근거로 유지할 convention과 적용할 capability skill을 식별한다.
version: 0.7.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, orchestrator, pattern, convention, project-analysis, stack, java, kotlin, frontend, design-reference, image, figma, data, database, dbml, cache]
    related_skills: [dev-project-bootstrap, dev-tech-dispatch, dev-breakdown, dev-java-guidelines, dev-kotlin-guidelines, dev-spring-guidelines, dev-spring-feature, dev-spring-data, dev-spring-test, dev-api-docs, dev-frontend-feature, dev-design-reference, dev-data-feature, dev-data-modeling, dev-db-schema, dev-db-query, dev-db-migration, dev-db-performance, dev-typescript-guidelines, dev-frontend-guidelines, dev-nextjs-feature, dev-frontend-test, dev-api-contract, dev-figma-design, dev-ui-ux]
    requires_tools: [terminal, skill_view]
---

# dev-project-pattern

복잡한 작업에서 `dev-breakdown` 전에 대상 프로젝트의 기존 패턴을 읽어 새 코드가 현재 프로젝트와 최대한 동일한 방식으로 작성되도록 기준을 만드는 planning Skill이다.

```text
/opt/data/shared/references/project-pattern-rules.md
/opt/data/shared/references/coding-rules.md
/opt/data/shared/references/implementation-decision-rules.md
/opt/data/shared/references/data-design-rules.md   # data affected area일 때
```

을 공통 Foundation으로 적용한다.

## 실행 순서

1. managed project repository/workspace identity와 `.hermes/project.yaml`을 확인한다.
2. instruction/AGENTS, 실제 Task와 관련된 source root를 읽는다.
3. `stack_cache.py`를 한 번 실행해 Bootstrap 기술 스택 캐시를 검증한다.
4. `STACK_CACHE=reused`면 저장된 technology metadata를 그대로 사용한다.
5. manifest fingerprint가 달라 `created|updated`가 나오면 detector가 재실행한 최신 stack 결과를 사용한다.
6. 요청과 가장 유사한 기존 구현을 1~3개 찾는다.
7. backend/frontend/data/UI/test convention을 evidence와 함께 요약한다.
8. 실제 Task affected area와 stack 결과를 합쳐 runtime entry capability와 lazy capability hint를 결정한다.
9. Frontend Task면 Design Source를 `IMAGE | FIGMA | EXISTING_CODE`로 분류하고 Reference Package/Figma/current screen evidence를 bounded하게 확인한다.
10. data affected area이면 기존 schema/migration/DBML/data docs convention과 DBMS vendor candidate를 확인한다.
11. 기존 패턴과 사용자 정책 충돌은 조용히 덮지 않고 최소 변경 방향과 Improvement Candidate로 전달한다.

## Technology cache

Bootstrap이 생성한 `.hermes/project.yaml`의 `technology:` section이 canonical project-level stack/cache다.

```bash
python3 /opt/custom-skills/orchestrator/dev-project-bootstrap/scripts/stack_cache.py \
  --repo "<managed repository>"
```

예:

```text
STACK_CACHE=reused
DETECTOR_VERSION=4
STACK_FINGERPRINT=sha256:...
STACK_INPUTS=backend/build.gradle.kts,frontend/package.json,frontend/tsconfig.json
STACKS=kotlin,spring,typescript,react,nextjs
BACKEND_SKILLS=dev-kotlin-guidelines,dev-spring-guidelines
FRONTEND_ENTRY=dev-frontend-feature
FRONTEND_HINTS=dev-typescript-guidelines,dev-frontend-guidelines,dev-nextjs-feature,dev-frontend-test
DATABASE_VENDORS=mssql
DATA_ENTRY_CANDIDATE=dev-data-feature
STATUS=pass
```

`STACK_CACHE=reused`에서는 full stack detector를 다시 실행하지 않는다. Fingerprint는 bounded build/dependency manifest와 `schema.prisma` 같은 schema manifest만 대상으로 하므로 일반 source/SQL 변경은 cache invalidation 원인이 아니다.

manifest 변경 또는 detector version 변경 시에만 stack을 다시 계산하고 Bootstrap-managed local metadata의 `technology:` section을 갱신한다. `.hermes/`는 Bootstrap `.gitignore` 정책으로 Git 추적에서 제외되므로 application source/config 변경으로 취급하지 않는다.

기존 Bootstrap Repository가 `technology:` section이 없거나 detector version이 바뀌면 최초 Standard Flow에서 자동 갱신될 수 있지만, DevKit 업데이트 직후에는 다음 명시적 migration을 우선 권장한다.

```bash
python3 /opt/custom-skills/orchestrator/dev-project-bootstrap/scripts/bootstrap.py \
  --repo "<managed repository>" \
  --refresh-stack
```

여러 Repository는 `refresh_stacks.py --root <root>`로 일괄 갱신할 수 있다.

## Stack Detection != Skill Loading

Technology cache는 Repository가 사용할 수 있는 stack/vendor/capability 후보를 저장할 뿐 이번 Task가 Backend/Frontend/Data/Full-stack인지 결정하지 않는다.

```text
Repository Capability Candidate
+ 사용자 요구사항
+ 실제 affected area
= Task Capability
```

Repository에 Kotlin/Spring + Next.js + MSSQL이 함께 있어도 Service-only Task에는 frontend/data entry를 적용하지 않는다.

## Backend capability

```text
Java → dev-java-guidelines
Kotlin → dev-kotlin-guidelines
Spring → dev-spring-guidelines
Controller/Service/DTO/Validation/Exception → dev-spring-feature
JPA/Repository/DataJPA/QueryDSL/Converter/Paging → dev-spring-data
Spring/JPA test → dev-spring-test
OpenAPI/Swagger/Postman → dev-api-docs
```

Java + Kotlin mixed Repository에서는 실제 Task diff/affected area의 언어에 맞춰 적용한다. Kotlin project pattern에서는 필요할 때 compiler/language version, kotlin-spring/kotlin-jpa, KSP/kapt, nullability/modeling, coroutine/reactive, Java interop boundary를 확인한다.

## Frontend canonical entry

실제 Task가 TypeScript/React/Next.js UI 또는 browser 동작을 변경하면 runtime entry는:

```text
→ dev-frontend-feature
```

하위 전문 Skill은 `Frontend Capability Hints`로만 전달한다.

```text
Design Reference IMAGE/Figma → dev-design-reference
TypeScript → dev-typescript-guidelines
React component/state/form/browser → dev-frontend-guidelines
Next.js router/server-client/cache/metadata → dev-nextjs-feature
frontend unit/component/e2e/visual → dev-frontend-test
backend↔frontend contract → dev-api-contract
visual/interaction/responsive/accessibility/chart → dev-ui-ux
Figma provider read → dev-figma-design
```

React/Next.js가 repository에 있다는 이유만으로 frontend entry나 UI/UX를 자동 적용하지 않는다.

## Design Source / Reference Package

Frontend Task에서는 다음을 구분한다.

```text
Frontend Mode: REFERENCE_DRIVEN | CODE_DRIVEN
Design Source: IMAGE | FIGMA | EXISTING_CODE
Design Status: DRAFT | REFERENCE | APPROVED | N/A
Design Fidelity: STRUCTURE | VISUAL | HIGH | N/A
Reference: <repo path | Figma URL | current code>
Screen Spec: <repo path | none>
```

### IMAGE

프로젝트에 기존 UI 문서 표준이 없으면 stable GitHub Reference Package를 우선한다.

```text
docs/ui/screens/<screen>/
├─ reference.png
└─ screen-spec.md
```

`screen-spec.md`가 있으면 frontmatter와 실제 reference path를 확인한다. `APPROVED` 이미지가 구현 기준인데 reference가 repo/workspace에서 접근 불가능하면 source of truth를 추측하지 않고 Open Question으로 남긴다.

### FIGMA

Figma는 optional provider다.

```text
Design Source: FIGMA
Design Status: DRAFT | REFERENCE | APPROVED
Reference: <selected frame/component URL>
```

`APPROVED`인 경우 `dev-design-reference → dev-figma-design`으로 evidence를 정규화한다. file-level URL보다 selected `node-id` URL을 우선한다.

### EXISTING_CODE

authoritative external Reference가 없으면:

```text
Frontend Mode: CODE_DRIVEN
Design Source: EXISTING_CODE
```

으로 current component/token/screen pattern을 사용한다.

## Storybook / Visual Test Pattern

Frontend Task에서는 repository에 이미 존재하는 catalog/visual test evidence도 bounded하게 확인한다.

```text
Storybook config / *.stories.*
Playwright config / visual screenshot tests
기타 project visual regression mechanism
```

존재 여부만으로 새 dependency를 추가하거나 모든 component에 story를 요구하지 않는다.

## Data canonical entry

실제 Task가 데이터 모델, relational schema, SQL dialect, migration, execution plan/index tuning을 변경하면 runtime entry 후보는:

```text
→ dev-data-feature
```

하위 Skill은 `Data Capability Hints`로 전달한다.

```text
모델/관계/cardinality/DBML → dev-data-modeling
PK/FK/UNIQUE/type/index/constraint → dev-db-schema
SQL/query semantics/dialect → dev-db-query
DDL/backfill/compatibility → dev-db-migration
execution plan/index/locking/statistics → dev-db-performance
JPA implementation → dev-spring-data (backend companion)
```

다음은 구분한다.

```text
기존 승인 schema + JPA Repository/QueryDSL 구현만 변경
→ dev-spring-data

DBML/schema/DDL/vendor SQL/query tuning 자체가 Task 책임
→ dev-data-feature
```

`DATABASE_VENDORS`는 project-level candidate다. 둘 이상이면 affected module에서 실제 target을 특정한다. vendor version은 dependency 이름만으로 추측하지 않는다.

### DBML / Data Documentation Pattern

Data Task이면 우선 다음을 찾는다.

```text
기존 *.dbml / ERD source
docs/data 또는 project data docs
Flyway/Liquibase/raw migration 위치
schema naming / PK/FK/index naming
actual DB vendor/version 근거
```

기존 표준이 없으면 `docs/data/schema.dbml`을 canonical relational model 기본값으로 추천한다. DBML Canvas는 Human View이며 runtime dependency가 아니다.

## 필수 출력

```text
Project Pattern Summary
- Language / Framework / Persistence / Build / Test
- Technology Cache Status / Fingerprint
- Detected Stacks
- Database Vendor Candidates (해당 시)
- Pattern References
- Package / Naming
- Response Contract
- Error / Validation Contract
- Data Access Convention
- Data Schema/Migration/DBML Convention (해당 시)
- Kotlin Language/Compiler/Interop Convention (해당 시)
- Frontend Component/State/Style Convention (해당 시)
- Design System Reference (해당 시)
- Frontend Mode / Design Source / Status / Fidelity / Reference / Screen Spec (해당 시)
- Storybook / Visual Test Convention (해당 시)
- Test Convention
- Applicable Skills
- Frontend Capability Hints
- Data Capability Hints
- Pattern Conflicts
- Improvement Candidates (not auto-applied)
```

## 불변식

- application source/build dependency를 수정하지 않는다.
- `technology:` cache 갱신 외 project metadata를 planning 단계에서 변경하지 않는다.
- 새 architecture/library/common contract를 제안 없이 확정하지 않는다.
- 기존 패턴을 Public Skill/Design Reference/DBML 기본값으로 광범위하게 교체하지 않는다.
- Kotlin version/compiler plugin/KSP migration을 planning 근거 없이 자동 결정하지 않는다.
- DB driver가 있다는 이유만으로 Data entry를 자동 적용하지 않는다.
- DBMS version/vendor-specific feature를 근거 없이 추측하지 않는다.
- `dev-tech-dispatch`는 detector이며 runtime pinned skill이 아니다.
- frontend/data 하위 capability를 전부 runtime pin하지 않고 canonical entry를 사용한다.
- Figma를 Frontend implementation의 필수 단계로 만들지 않는다.
