# Stack / Capability Skill Extension Guide

이 문서는 `coding-rules.md`, `implementation-decision-rules.md`, `project-pattern-rules.md`를 기반으로 특정 언어·프레임워크·기술 기능 Skill을 추가할 때의 설계 규칙이다.

## 1. 계층

```text
Foundation
- coding-rules.md
- implementation-decision-rules.md
- project-pattern-rules.md
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

두 번째 이상의 framework/language가 실제 사용되므로 canonical stack resolver로 사용한다.

```text
root build/dependency evidence
→ stack detection
→ baseline capability candidate
```

source 수정, architecture 선택, dependency 설치, runtime pin 결정, Kanban 생성은 하지 않는다.

`Stack Detection != Skill Loading`이다.

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

### Frontend lazy capability

```text
dev-typescript-guidelines
dev-frontend-guidelines
dev-nextjs-feature
dev-frontend-test
dev-figma-design
dev-ui-ux
```

### Cross-stack

```text
dev-api-contract
dev-api-docs
```

## 5. Capability 공통 실행 순서

```text
1. stack/version 탐색
2. 기존 동일/유사 구현 검색
3. 기존 convention 결정
4. assumption/정책 충돌 확인
5. implementation-decision-rules 필요성 사다리 적용
6. 최소 변경 구현
7. stack-specific verification
8. reviewer handoff evidence
```

새 dependency/framework/language version을 기본값으로 추가하지 않는다.

## 6. Java / Kotlin / Spring

```text
Java convention → dev-java-guidelines
Kotlin convention → dev-kotlin-guidelines
Spring common → dev-spring-guidelines
Controller/Service/DTO/Validation/Exception → dev-spring-feature
JPA/Repository/QueryDSL/Converter/Paging → dev-spring-data
Spring/JPA test → dev-spring-test
```

Java와 Kotlin은 서로 대체 관계가 아닌 first-class JVM language capability다.

```text
Java-only project      → dev-java-guidelines
Kotlin-only project    → dev-kotlin-guidelines
Java + Kotlin mixed    → 두 capability를 후보로 유지하고 실제 changed source 언어에 적용
```

Kotlin capability는 project Kotlin/compiler version을 우선하고 Stable 기능만 기본 허용한다. null-safety, data/value/sealed modeling, compiler plugin, annotation target, coroutine, KSP/kapt, Java interop을 담당하며 Spring layer/transaction/JPA query 정책을 중복 소유하지 않는다.

JPA Query 정책은 Method Query → QueryDSL → 근거 있는 Native Query 순서다.

## 7. Frontend entry와 lazy-load

실제 frontend Task는 `dev-frontend-feature`를 runtime entry로 한다.

```text
TypeScript → dev-typescript-guidelines
React/component/state/form/browser → dev-frontend-guidelines
Next.js → dev-nextjs-feature
spec/e2e → dev-frontend-test
Figma APPROVED → dev-figma-design
visual/interaction/responsive/accessibility/chart → dev-ui-ux
API integration → dev-api-contract
```

repository가 React/Next.js를 포함한다는 이유만으로 frontend skill을 로드하지 않는다.

## 8. FIGMA_DRIVEN / CODE_DRIVEN

```text
FIGMA_DRIVEN
사용자/Task
→ APPROVED Figma frame/component
→ project component/token/convention
→ dev-ui-ux quality guardrail

CODE_DRIVEN
사용자/Task
→ project component/token/convention
→ dev-ui-ux quality guardrail
```

Figma `DRAFT`는 planning reference다. 승인 상태가 불명확하면 구현 source of truth로 승격하지 않는다.

### Figma provider

현재 `dev-figma-design`은 Figma 공식 REST API의 read-only endpoint를 사용한다.

```text
GET /v1/files/:key/nodes
GET /v1/files/:key (bounded/explicit)
GET /v1/images/:key
```

Personal/Plan REST token은 `X-Figma-Token`, OAuth는 Bearer를 사용한다. token은 환경변수에서만 읽는다.

Provider 구현이 향후 MCP로 바뀌어도 `Design Evidence` 계약은 유지한다.

## 9. UI/UX adapter

`dev-ui-ux`는 UI/UX Pro Max 공개 가이드에서 안정적인 quality priority를 참고한 audited adapter다.

```text
승인 Design / project Design System
→ current component/token pattern
→ dev-ui-ux baseline
```

accessibility, interaction, responsive, typography/color, reduced motion, form feedback, navigation, chart semantics를 보호한다.

## 10. API Contract

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

## 11. Frontend verification

package manager/test runner는 repository evidence를 따른다.

```text
affected test/spec
→ typecheck
→ lint
→ related integration
→ 필요한 경우 build
→ 필요한 경우 e2e
```

새 runner/library를 검증 편의로 추가하지 않는다.

## 12. Reviewer evidence

```text
Skill / Applied Capability Skills
Detected stack/version
Frontend Mode / Design Source / Status
Pattern References
Component/Token Reuse
API/UI strategy
Verification
Intentional Deviations
Design Conflicts
Improvement Deferred
Residual Risk
```

Reviewer는 실제 diff 판단에 필요한 capability만 읽는다.

## 13. Skill 추가 체크리스트

```text
[ ] Foundation만으로 해결할 수 없는 전문 기능인가
[ ] 반복 가능한 작업인가
[ ] 기존 Skill과 역할이 겹치지 않는가
[ ] stack/task detection이 정의됐는가
[ ] dependency 정책이 정의됐는가
[ ] verification/evidence가 정의됐는가
[ ] Public Skill/provider source/version/security를 검토했는가
[ ] runtime pin 대신 lazy-load가 적합한지 검토했는가
```
