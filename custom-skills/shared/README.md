# Shared Custom Skills

`custom-skills/shared`는 `orchestrator`, `coder`, `reviewer`가 공통으로 참조하는 Hermes Custom Skill 원본 디렉터리입니다.

## 관리 원칙

- 역할 전용 Skill은 `custom-skills/orchestrator`, `custom-skills/coder`, `custom-skills/reviewer`에서 관리합니다.
- 둘 이상의 프로필이 동일 규칙/기능을 사용하면 이 디렉터리에 한 벌만 둡니다.
- 세 프로필은 자신의 역할 디렉터리와 `/opt/custom-skills/shared`를 함께 `skills.external_dirs`로 참조합니다.
- Foundation 규칙은 `/opt/data/shared/references`에 두고 언어/프레임워크/기능 전문 지식만 capability Skill로 분리합니다.
- Public Skill/외부 provider/IDE plugin은 직접 Workflow에 박지 않고 DevKit adapter/capability 뒤에 둡니다.

## Capability Lifecycle Registry

Standard Flow를 가로지르는 capability의 source of truth는 `capability-lifecycle.json`입니다.

```text
Planner(dev-breakdown)
        ↓
Coder(dev-implement-plan 또는 pinned capability)
        ↓
Reviewer(dev-code-review)
        ↓
Dispatch Preflight(coder + reviewer availability)
```

새 capability가 위 네 단계를 모두 사용해야 하는 경우 등록부에 추가합니다. 특히 shared Skill이 자신을 `canonical entry`로 선언하면 반드시 등록되어야 하며 `scripts/check_capability_lifecycle_contract.py`가 누락을 CI에서 차단합니다.

`strict_pin=true`는 해당 capability가 Task의 `Applicable Skills`에 포함됐을 때 Coder/Reviewer 양쪽 profile에서 exact skill 존재를 `dev-skill-preflight --strict`로 확인해야 한다는 뜻입니다. 단순 support/hint capability는 필요할 때 lazy-load하며 모든 shared skill을 등록부에 넣지는 않습니다.

현재 cross-flow 등록 범위는 Backend Spring feature/data, Frontend canonical entry, Data canonical entry/migration, Infrastructure canonical entry, API specification/contract입니다. Reviewer는 별도 하드코딩 목록을 source of truth로 유지하지 않고 이 등록부와 Task affected scope를 기준으로 필요한 capability만 읽습니다.

## Backend

```text
dev-java-guidelines
dev-kotlin-guidelines
dev-spring-guidelines
dev-spring-feature
dev-spring-data
dev-spring-test
dev-spring-refactor
```

## Frontend / Node

```text
dev-frontend-feature        # canonical frontend entry
dev-design-reference        # IMAGE/Figma normalized design evidence
dev-official-docs-context   # version-first Context7/official/local-type evidence
dev-typescript-guidelines
dev-frontend-guidelines
dev-nextjs-feature
dev-frontend-test            # functional/component/e2e/visual verification
dev-node-dependencies        # Frontend 환경 Gate + pnpm allowBuilds/package root/lockfile + Tirith preflight
dev-figma-design             # optional Figma REST read-only provider
dev-ui-ux                    # audited UI/UX quality baseline
```

Frontend Task는 `dev-frontend-feature`를 runtime entry로 사용하고 세부 capability는 실제 evidence에 따라 lazy-load합니다. Node 기반 Frontend Task는 dependency mutation 여부와 무관하게 `dev-node-dependencies`의 Frontend Environment Gate를 첫 Node command 전에 적용합니다. dependency build-script 권한은 별도 Hermes 설정이 아니라 pnpm 표준 `pnpm-workspace.yaml > allowBuilds`에 exact package/version 단위로 기록하며 같은 결정은 재승인하지 않습니다. 초기 pnpm 안정화에서 여러 미검토 build dependency가 발견되면 package별로 연속 승인받지 않고 first restore output + isolated `pnpm ignored-builds` 결과를 하나의 `SINGLE_REVIEW_BATCH`로 묶어 한 번에 승인/거부합니다. package add/remove/version/restore/lockfile mutation과 Tirith 절차는 실제 dependency 변경이 Task 범위일 때만 추가 적용합니다.

외부 SDK/library/API 또는 version-sensitive framework 설정을 구현할 때는 `dev-official-docs-context`가 먼저 실제 resolved version을 확정하고 Context7 공식 문서 → 공식 upstream → 설치된 local type/source → compiler 순서로 evidence를 만듭니다. Context7는 provider일 뿐 compiler/typecheck/test/build를 대체하지 않습니다.

Node dependency 변경의 기본 경계:

```text
exact package root
→ packageManager / canonical lockfile
→ Node / package-manager version compatibility
→ package.json vs node_modules 상태
→ pnpm-workspace.yaml allowBuilds / strictDepBuilds
→ Tirith exact-command preflight
→ dependency mutation 1회
→ manifest + lockfile 검증
```

`node_modules`만 존재하고 `package.json`/lockfile에 없는 package는 정상 설치로 간주하지 않습니다. Tirith가 실제 finding이 아니라 `analysis_incomplete`를 반환한 경우에만 daemon 준비 후 동일 command를 1회 재검사하며, 재검사도 불완전하거나 positive finding이면 headless worker는 BLOCK합니다. Tirith/approval을 비활성화해 우회하지 않습니다.

Reference 기반 기본 경로:

```text
ChatGPT/Designer/Figma
→ Approved Design Reference
→ GitHub Reference Package
→ Hermes implementation
→ existing Storybook catalog (있을 때)
→ Design Conformance
→ approved browser screenshot
→ Visual Regression
```

프로젝트에 별도 UI 문서 규칙이 없으면 IMAGE Reference는 다음 구조를 권장합니다.

```text
docs/ui/screens/<screen>/
├─ reference.png
└─ screen-spec.md
```

Figma는 필수 단계가 아니라 `dev-design-reference` 아래의 optional provider입니다.

## Data / Design-Time DBA

```text
dev-data-feature            # canonical data/DB entry
dev-data-modeling           # responsibility/lifecycle/cardinality/DBML
dev-db-schema               # key/constraint/type/index
dev-db-query                # query intent/SQL dialect
dev-db-migration            # DDL/backfill/compatibility
dev-db-performance          # execution plan/index/locking evidence
```

Data Skill은 특정 DBMS에 종속되지 않습니다. 공통 판단 후 실제 target이 필요한 경우에만 다음 vendor reference를 lazy-load합니다.

```text
MSSQL
MySQL
MariaDB
PostgreSQL
Oracle
```

기존 프로젝트에 별도 표준이 없으면 `docs/data/schema.dbml`을 canonical relational model 기본값으로 권장합니다. IntelliJ의 DBML Canvas 같은 plugin은 Human ERD View로 활용할 수 있지만 DevKit runtime 의존성은 아닙니다.

운영 DB 직접 DDL/DML, backup/restore, session kill, index maintenance 등은 현재 Data Skill의 책임이 아닙니다. 그런 권한이 실제 필요해질 때 별도 DBA profile/운영 Skill을 검토합니다.

## Cross-stack

```text
dev-official-docs-context   # external technology version-aware official evidence
dev-api-contract
dev-api-docs
dev-api-spec
```

`dev-official-docs-context`는 다음 상황에서 lazy-load합니다.

```text
외부 SDK/API 신규 사용
인증/OAuth/Supabase/Firebase 등 연동
framework/library version-sensitive API/config 변경
외부 dependency declaration/compiler compatibility 오류
외부 API signature 불확실성
```

Context7 조회는 read-only이며 `CONTEXT7_API_KEY`는 선택 사항입니다. provider가 unavailable이면 공식 vendor repository/docs와 local type/source로 fallback하고 version drift를 Handoff에 기록합니다.

## Figma

현재 `dev-figma-design`은 `dev-design-reference` 아래에서 Figma 공식 REST API를 read-only provider로 사용합니다.

```text
FIGMA_ACCESS_TOKEN
→ Personal Access Token 또는 Plan REST Access Token

FIGMA_OAUTH_TOKEN
→ OAuth access token
```

선택한 frame/component의 `node-id` URL을 우선해 bounded context를 읽고, 필요 시 rendered preview를 `HERMES_WRITE_SAFE_ROOT` 안에 저장합니다.

Figma canvas write는 Hermes Frontend 구현 Flow의 책임이 아닙니다. Approved Figma가 있으면 Reference Provider로 읽고, Approved IMAGE가 있으면 Figma 없이 직접 `REFERENCE_DRIVEN` 구현합니다.

## Java legacy

legacy `java-project-conventions`를 새 Task에서 사용하지 않습니다. Java convention은 canonical `dev-java-guidelines`를 사용합니다.
