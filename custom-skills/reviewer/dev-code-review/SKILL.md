---
name: dev-code-review
description: 동일 Workspace의 미커밋 구현을 requirement/AC와 Work Unit·project pattern·capability·구조 품질 계약 기준으로 독립 검토하고 승인·수정요청·차단한다.
version: 0.16.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, review, reviewer, kanban, quality, verification, work-unit, capability, lifecycle, java, refactor, structural-quality, performance]
    related_skills: [dev-implement-plan, dev-review-cycle, dev-workspace-dispatch, dev-java-guidelines, dev-spring-guidelines, dev-spring-feature, dev-spring-data, dev-spring-test, dev-spring-refactor, dev-frontend-feature, dev-data-feature, dev-data-modeling, dev-db-migration, dev-infrastructure, dev-api-spec, dev-api-contract, dev-api-docs]
    requires_tools: [terminal, kanban_show, kanban_request_changes, kanban_complete, kanban_block, kanban_heartbeat, skill_view]
---

# dev-code-review

Reviewer의 **compact 실행 계약**이다. 상세 severity/checklist/escalation은 필요할 때만 `references/review-details.md`를 읽는다. Standard Flow에서는 `/opt/data/shared/references/standard-work-unit-rules.md`를 함께 적용한다.

## 실행 계약
1. `kanban_show()`에서 requirement/AC/scope, **Work Unit Contract**, Pattern References, Applied Capability Skills, coder evidence, attempts/comments를 읽는다.
2. 같은 Workspace에서 `scripts/review_context.py`를 canonical 형식으로 한 번 실행해 Base SHA/Expected Branch/safe.directory/scoped changed paths/EOL noise와 `EFFECTIVE_SCOPE_SHA256`를 검증한다.
3. Review는 diff-first로 시작한다. 전체 프로젝트를 다시 분석하지 않고 changed hunk와 그 주변 코드부터 본다.
4. requirement/AC/correctness/compatibility/security/tests와 Coder verification claim, **Work Unit Boundary**를 대조한다.
5. `/opt/custom-skills/shared/capability-lifecycle.json`의 `reviewer_required=true` 등록부와 Task의 `Applicable Skills`/`Applied Capability Skills`를 대조한다. 실제 finding 판단에 필요한 capability만 `skill_view`한다.
6. Java source 변경에서는 필요할 때 `skill_view("dev-java-guidelines")`를 적용한다. Spring source 변경에서는 Coder의 Structural Quality/Javadoc evidence를 실제 diff와 대조한다.
7. Coder의 `Verification Final: true`, PASS command/result, verification/effective scope fingerprint가 reviewer 계산과 일치하면 해당 PASS evidence를 재사용한다.
8. Coder의 `Review Risk`와 구조화된 `Risk Reasons`를 탐색 시작점으로 재사용하되 verdict로 그대로 신뢰하지 않는다.
9. P0/P1이 있으면 `kanban_request_changes`; 없고 evidence가 충분하면 `kanban_complete`; 안전한 판단 불가·외부 결정 필요·반복 blocker면 `kanban_block` 중 정확히 하나만 실행한다.

## Standard Work Unit Review Gate

Task body에 다음이 있어야 한다.

```text
Work Unit Class: DESIGN | IMPLEMENTATION | MIGRATION | REFACTOR | AUDIT
Work Unit Boundary: SINGLE_UNIT | SPLIT_REQUIRED
Current Deliverable: ...
Follow-up Required: YES | NO
Follow-up Work Unit: ... | NONE
Follow-up Input: ... | NONE
Excluded Follow-up Scope: ... | NONE
```

Reviewer는 capability 수가 아니라 **diff가 Current Deliverable과 Excluded Follow-up Scope의 경계를 넘었는지** 본다.

### DESIGN

DESIGN diff는 승인 artifact/document materialization과 검증에 한정한다.

Data logical DESIGN에서 다음이 섞이면 blocking finding이다.

```text
Flyway/Liquibase migration
CREATE/ALTER/DROP DDL
physical tbl_* mapping
vendor-specific physical schema decision
JPA @Table/@Column physical mapping
schema mutation
```

DBML/design artifact가 `Physicalization Required: YES`여도 같은 Task에서 migration을 선행 구현한 것은 허용하지 않는다.

### IMPLEMENTATION

하나의 Current Deliverable을 완성하기 위해 Backend/Frontend/Infrastructure 등 여러 capability가 함께 변경되는 것은 허용한다. 여러 Skill 사용 자체를 split finding으로 만들지 않는다.

### MIGRATION

MIGRATION은 approved/canonical logical model 또는 명시적 migration intent를 입력으로 가져야 한다. physicalization 과정에서 Subject Area/responsibility/cardinality/ownership을 임의 redesign했다면 blocking finding이다.

### REFACTOR

behavior/API/schema 의미 변경이 섞이면 Work Unit 위반이다.

### AUDIT

AUDIT Task에서 application/test/config source mutation이 발생하면 blocking finding이다. 명시된 audit report/document artifact만 예외다.

### Boundary finding

Coder가 `Excluded Follow-up Scope`를 구현했거나 Task의 Work Unit Class를 사실상 바꿨다면 P1 수준의 scope/contract finding으로 `kanban_request_changes`한다. 안전하게 되돌릴 수 없거나 새 product/architecture 결정이 필요하면 `kanban_block`한다.

## Canonical Review Context

```bash
python3 /opt/custom-skills/reviewer/dev-code-review/scripts/review_context.py \
  --workspace "<Workspace>" \
  --expected-workspace "<Workspace>" \
  --expected-branch "<Expected Branch>" \
  --base-branch "<Base Branch>" \
  --base-sha "<Base SHA>" \
  --include "<changed-path-1>" \
  --include "<changed-path-2>"
```

Canonical 호출은 `review_context.py --include` scoped review다.

- Standard Flow에서는 `--include`를 반드시 제공한다. 값은 Coder handoff의 `Changed Files`를 그대로 사용한다.
- Coder Changed Files가 누락되면 repository-wide scan으로 복구하지 않고 evidence 부족으로 BLOCK한다.
- `--allow-full-scan`은 명시적 진단 전용이다.
- tracked와 untracked 모두 Git pathspec으로 제한한다.
- `EOL_ONLY_*`는 CRLF/LF-only noise이며 review failure가 아니다.
- `EFFECTIVE_SCOPE_SHA256`는 Coder `change_summary.py`와 동일 방식의 fingerprint다.

## Existing Changes Preservation Fast Path

```text
Existing changes preservation approved: true
Workspace change scan mode: skipped-approved-preservation
```

이 상태에서는 exact 기존 변경 목록을 복원하려고 repository-wide scan을 하지 않는다. 검토 대상은 Coder가 선언한 `Changed Files`와 직접 영향 범위다.

## Diff-first Review Budget
1. Base SHA 기준 changed hunk/diff부터 확인한다.
2. Coder Risk Reasons와 Work Unit Contract를 diff에 대조한다.
3. diff만으로 이해되지 않는 symbol만 bounded read한다.
4. 변경되지 않은 DTO/entity/repository/service를 전부 읽지 않는다.
5. 동일 파일을 반복 대량 read하지 않는다.
6. 분석 Markdown과 source가 충돌하면 source/diff를 우선한다.

## Verification Evidence Reuse

Coder evidence 재사용 조건:
- command와 결과가 명시됨
- `Verification Final: true`
- `Verification Request SHA256`와 `Verification Scope SHA256`가 있음
- Coder `Effective Scope SHA256`와 Reviewer `EFFECTIVE_SCOPE_SHA256`가 일치
- PASS 이후 executable source/test/build/toolchain 변경 없음
- verification command가 현재 behavior를 충분히 cover
- `Work Unit Boundary Respected: true` claim과 실제 diff가 일치

모두 만족하면:

```text
Verification Evidence: REUSED
Verification Scope Match: true
Primary Reused: true
PRIMARY_REUSED=true
Reason: coder final verification covers the unchanged executable scope
```

Java/Gradle evidence 확인이 필요하면 같은 cached helper와 `--scope-path` 목록을 사용한다.

```bash
python3 /opt/custom-skills/coder/dev-implement-plan/scripts/gradle_verification_cached.py \
  --workspace "<Workspace>" \
  --mode TARGETED_TEST \
  --test "<same-selector>" \
  --scope-path "<same-covered-path>"
```

현재 scope가 Coder PASS와 동일하면 helper가 `VERIFICATION_EVIDENCE=REUSED`, `PRIMARY_REUSED=true`로 끝나야 한다. 이 경로에서 **Gradle primary를 다시 실행하면 안 된다**.

재실행이 **필수**인 경우:
- Coder PASS 이후 executable production/test/build/toolchain 파일이 수정됨
- Coder/Reviewer effective scope 또는 verification scope fingerprint가 불일치함
- verification fingerprint 또는 `Verification Final`/command/result가 누락됨
- Reviewer finding 수정으로 Coder가 source/test를 변경한 뒤 재-review가 들어옴
- P0/P1 가능성을 검증하는데 기존 PASS command가 해당 behavior를 cover하지 않음
- Coder verification이 실패/모호함. 단 `GRADLE_STATUS=BLOCKED`를 Reviewer가 같은 primary command로 대신 재시도하지 않는다.

재실행이 필요한 경우에는 이전 PASS evidence를 재사용하지 않고 fresh verification을 요구한다. 동일 scope와 동일 PASS evidence가 유효한 경우에는 독립성 확보만을 이유로 같은 Gradle primary를 반복하지 않는다.

`GRADLE_STATUS=BLOCKED`이면 Reviewer가 direct `hermes-java ./gradlew`로 우회하지 않고 blocker evidence를 유지한다.

## Common Coding Review Gate
- `/opt/data/shared/references/coding-rules.md`와 project pattern을 기준으로 기존 abstraction 재사용, scope, `2-depth`, 반복 I/O/N+1을 확인한다.
- Style/nit만으로 승인을 막지 않는다.
- API는 기존 response/error contract, JPA는 Method Query → QueryDSL → 근거 있는 Native Query 정책을 확인한다.
- 테스트는 변경 behavior와 risk를 실제로 증명하는지 본다.

## Capability Lifecycle Review Gate

목록의 source of truth는 `capability-lifecycle.json`이며 다음은 설명용이다.

```text
Backend        → dev-spring-feature, dev-spring-data
Frontend       → dev-frontend-feature
Data           → dev-data-feature, dev-db-migration
Infrastructure → dev-infrastructure
API            → dev-api-spec, dev-api-contract
```

규칙:
- Task의 `Applicable Skills` 또는 실제 diff가 등록 capability 영역이면 판단에 필요한 시점에 `skill_view("<capability>")`한다.
- `strict_pin=true` capability가 Applicable Skills에 있는데 validated/pinned skill에서 누락되면 Dispatch Preflight 계약 위반이다.
- `strict_pin=false` support/companion은 affected scope로 lazy-load할 수 있다.
- **Follow-up Work Unit 전용 capability가 현재 Task에 pin되지 않은 것은 정상**이다.
- capability 재탐색을 위해 repository-wide 분석을 다시 수행하지 않는다.

## Java Convention Review Gate
Java diff에서 실제 판단에 필요할 때 `dev-java-guidelines`를 적용한다.

- target Java version과 사용 문법/API 호환
- Lombok/project convention
- top-level/nested type 배치
- JavaDoc/documentation 품질

## Structural Quality Review Gate
Task와 직접 연결된 책임 혼재, raw payload parsing/persistence/external I/O 결합, behavior-preserving verification 누락은 finding이 될 수 있다. 파일 길이/개인적 선호만으로 blocking finding을 만들지 않는다.

Coder handoff의 `Structural Quality/Javadoc evidence`를 실제 diff와 대조한다. public API/schema/dependency/transaction/security/concurrency/architecture 의미 변경이 필요한 개선은 현재 Work Unit을 넘어가면 follow-up/escalation으로 분리한다.

## Stack / Capability Review Gate
`capability-lifecycle.json`을 cross-flow source of truth로 사용하고 Task/diff에 해당하는 등록 capability와 support capability만 확인한다. Reviewer가 자체 별도 capability 목록을 source of truth로 유지하지 않는다.

## Java / Build Verification Gate
- `.hermes/toolchain.env`가 있으면 Java target/runtime과 Coder evidence를 대조한다.
- Java/Gradle 재검증은 `gradle_verification_cached.py`를 canonical 경로로 사용한다. 최대 primary timeout은 600초다.
- Reviewer가 임의 JDK를 다운로드하거나 host Java를 탐색하지 않는다.

## Verdict
```text
P0/P1 + coder가 수정 가능 → kanban_request_changes
P0/P1 없음 + evidence 충분 → kanban_complete
판단 불가/외부 결정/동일 blocker 3회 → kanban_block(kind=needs_input...)
```

## 불변식
- Reviewer는 application/test/config source를 수정하지 않는다.
- secret/raw credential을 출력하지 않는다.
- commit, push, PR, cleanup 금지.
- EOL-only noise를 이유로 source line ending을 변경하지 않는다.
- finding은 file/symbol, evidence, required change, expected verification을 포함한다.
- Fast Flow `Review Risk: LOW` Task는 Coder가 완료하므로 Reviewer가 호출되지 않는다.
- Coder Risk Reasons는 starting point이지 verdict가 아니다.
- Standard Flow에서는 scope 없는 `review_context.py` 호출을 하지 않는다.
- Follow-up Work Unit을 현재 Task에 구현하도록 요구하지 않는다.

Severity, 상세 checklist, retry/escalation이 필요하면 `references/review-details.md`를 읽는다.
