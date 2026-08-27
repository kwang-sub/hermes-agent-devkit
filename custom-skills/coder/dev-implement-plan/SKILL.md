---
name: dev-implement-plan
description: 승인된 Kanban 작업을 할당 Workspace에서 최소 구현·구조 품질 점검·검증하고 Fast Flow는 risk에 따라 완료 또는 review, Standard Flow는 reviewer에게 인계한다.
version: 0.14.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, implementation, coder, kanban, workspace, review, fast-flow, capability, java, refactor, structural-quality]
    related_skills: [dev-fast-flow, dev-breakdown, dev-workspace-dispatch, dev-review-cycle, dev-code-review, dev-spring-guidelines, dev-spring-feature, dev-spring-data, dev-spring-test, dev-spring-refactor, dev-api-docs]
    requires_tools: [terminal, kanban_show, kanban_request_review, kanban_complete, kanban_block, kanban_heartbeat, skill_view]
---

# dev-implement-plan

Coder worker의 **compact 실행 계약**이다. 상세 구현/검증/risk 기준은 필요할 때만 `references/implementation-details.md`를 읽는다.

## 실행 계약
1. `kanban_show()`로 Task body, attempts, comments, feedback을 읽고 Workspace/Expected Branch/Base SHA를 `scripts/verify_workspace.py`로 검증한다. 검증기는 workspace를 Git `safe.directory`로 idempotent하게 등록한다. mismatch면 수정 전에 `BLOCKED`.
2. `Flow: FAST`는 Task의 `Pre-existing effective changes at dispatch`를 사용자 변경 baseline으로 사용한다. raw `git status`에 Windows bind-mount CRLF/LF noise가 대량 표시되어도 raw modified-file 개수만으로 작업을 중단하거나 baseline을 다시 정의하지 않는다. 실제 source를 읽은 뒤 Fast Flow 범위를 재확인한다. API/schema/dependency/architecture/transaction/security/concurrency/cross-repo/모호한 요구사항 등 설계 판단이 필요하면 `FAST_FLOW_ESCALATION_REQUIRED`로 `kanban_block`한다.
3. 모든 작업은 `/opt/data/shared/references/coding-rules.md`와 `/opt/data/shared/references/project-pattern-rules.md`를 적용하고 가장 가까운 기존 구현을 기준으로 최소 diff를 만든다. 단, 이번 Task 구현으로 새로 생기거나 명확히 드러난 책임 혼재·중복·orchestration/detail 결합은 unrelated refactor로 보지 않는다.
4. Task의 `Project Pattern Summary`, `Pattern References`, `Applicable Skills`, `Goal`, `Acceptance Criteria`, `Implementation Tasks`를 재사용한다. 실제 source와 충돌하지 않는 한 프로젝트 전체를 다시 분석하지 않는다.
5. Spring은 실제 evidence로 필요한 Skill만 lazy-load한다. 적용할 때 반드시 해당 본문을 `skill_view()`로 읽는다.
   - Spring 공통 → `skill_view("dev-spring-guidelines")`
   - API/Controller/Service/DTO/Validation/Exception → `skill_view("dev-spring-feature")`
   - JPA/Repository/QueryDSL/Converter/Paging → `skill_view("dev-spring-data")`
   - **테스트 작성/수정** → `skill_view("dev-spring-test")` (단순 테스트 실행만으로는 로드하지 않음)
   - **Spring source 구현 완료 후 구조 trigger가 실제로 있을 때만** → `skill_view("dev-spring-refactor")`
   - OpenAPI/Swagger/Postman 작업 → `skill_view("dev-api-docs")`
6. Java/Gradle/Maven 프로젝트는 Bootstrap이 생성한 `.hermes/toolchain.env`를 사용한다. build/test/compile 명령은 `hermes-java` launcher를 우선한다. `.hermes/toolchain.env`가 없거나 선택 JDK가 유효하지 않으면 개발환경 bootstrap 문제로 `BLOCKED`한다.
7. **Post-Implementation Structural Quality Gate**를 verification 전에 수행한다. Standard Flow의 Spring source 변경은 필요한 경우 `dev-spring-refactor`를 읽고 구조 품질을 점검한다. Fast Flow는 구조 trigger가 없으면 refactor 없이 진행한다. public API/schema/dependency/transaction/security/concurrency/package/module architecture 의미 변경이 필요하면 자동 refactor하지 않고 `REVIEW_REQUIRED` 또는 Fast Flow escalation으로 전환한다.
8. 구현이 안정된 뒤 Verification Mode와 Task Test Plan에 따라 최소 검증을 수행하고, 최종 source 변경 후 필요한 검증만 한 번 더 수행한다. 동일한 PASS 검증을 관련 source 변경 없이 반복하지 않는다.
9. 최종 변경 범위는 scoped `scripts/change_summary.py`로 한 번에 검증한다. `EOL_ONLY_*`는 Windows bind-mount noise로 기록만 하고 source 파일을 수동 normalize하지 않는다.
10. 구현 후 `Review Risk`를 **positive eligibility** 방식으로 판정한다. `LOW`임을 근거로 증명하지 못하면 `REVIEW_REQUIRED`다. Standard Flow 또는 CHANGES_REQUESTED 재작업은 항상 review, Fast Flow + LOW는 complete, Fast Flow + REVIEW_REQUIRED는 review로 보낸다.
11. terminal action 하나를 실행한 뒤 즉시 멈춘다. 구현 불가/필수 입력 누락/필수 검증 불가만 `kanban_block`한다. review 대용 `kanban_block`은 금지한다.

## Canonical Workspace Verification
Workspace 검증은 아래 형식을 그대로 사용한다. 필수 인수를 일부 생략한 probe 호출을 하지 않는다.

```bash
python3 /opt/custom-skills/coder/dev-implement-plan/scripts/verify_workspace.py \
  --task-key "<Task Key>" \
  --workspace "<Workspace>" \
  --expected-workspace "<Workspace>" \
  --expected-branch "<Expected Branch>" \
  --base-sha "<Base SHA>"
```

## Source Evidence Map
탐색 중 확인한 source/symbol을 짧은 Evidence Map으로 유지하고 동일 목적의 재탐색을 피한다. 별도 산출물 파일을 만들 필요는 없다.

예:

```text
Target
- ConfigMetadataUtils.java
  - applicationPropertyValue
  - fallbackKeys
Direct Consumers
- ConfigService
- NodeSpecificConfigService
Implementation Dependency
- PropertiesWriter
Tests
- ConfigMetadataUtilsTest
- NodeSpecificConfigServiceTest
```

규칙:
- 한 번 확인한 파일/심볼은 새로운 correctness 질문이 생기지 않는 한 다시 grep/read하지 않는다.
- 문서 작성과 Risk 판정은 이미 확보한 Evidence Map, Pattern References, 최종 diff를 우선 재사용한다.
- Evidence Map에 없는 추가 탐색은 무엇을 확인하려는지 명확한 질문이 있을 때만 수행한다.

## Source Exploration Budget
토큰과 반복 탐색을 줄이되 correctness evidence는 유지한다. 분석형 Fast Worker는 **약 50~60 tool calls를 soft target**으로 삼되, correctness evidence가 필요하면 초과할 수 있다. 초과 이유는 새로운 evidence여야 한다.

### Pass 1 — Target
1. Task body에 정확한 파일/심볼이 있으면 해당 경로부터 확인한다. repository-wide `find`를 먼저 수행하지 않는다.
2. 같은 목적의 관련 symbol은 결과가 과도해지지 않는 범위에서 한 grep에 묶는다.
3. 큰 source의 `L1-2000` 전체 읽기는 기본 금지한다. 필요한 symbol 주변 약 100~250 lines를 우선한다.

### Pass 2 — Direct Impact
4. Target의 direct caller/callee, 실제 persistence/external boundary, 관련 test까지만 확인한다.
5. 동일 파일을 전체 read한 뒤 다시 큰 overlapping range로 읽지 않는다.
6. 동일/유사 symbol grep은 원칙적으로 1회다. 이미 얻은 검색 결과를 다음 read 위치 결정에 재사용한다.
7. Task의 Pattern References/기존 분석과 source가 일치하면 프로젝트 전체 재분석을 하지 않는다.

### Pass 3 — Exception
8. Pass 1~2 evidence만으로 구현/compatibility/risk 판단이 불가능할 때만 범위를 넓힌다.
9. 추가 탐색 전 내부적으로 `Need additional evidence: <판단 질문> → <필요 symbol/path>`를 명확히 하고 그 질문에 직접 답하는 최소 grep/read만 수행한다.
10. frontend/backend contract 변경처럼 양쪽 구현을 함께 수정해야 하는 경우에도 정확한 payload builder/parser symbol을 먼저 찾고 repository-wide 동일 문자열 grep은 한 번만 허용한다.
11. Pass 2 종료 시점에 구현 가능 여부를 먼저 판단한다. 단순 확신 확보를 위해 Pass 3로 넘어가지 않는다.

## Documentation Reuse Rule
분석 Markdown이 구현 Task에 포함되어도 문서 전용 repository 재탐색을 만들지 않는다.

- 구현을 위해 이미 읽은 source, **Source Evidence Map**, Pattern References, 최종 diff를 문서 근거로 재사용한다.
- 문서 작성 전에 별도의 전체 비교 pass를 수행하지 않는다.
- 근거가 부족한 항목만 정확한 symbol 주변을 추가 확인한다.
- 사용자가 기존 문서와의 비교를 명시하지 않았다면 기존 Markdown 전체를 추가로 읽지 않는다.
- 문서만 마지막에 수정한 것은 Java/Frontend 테스트 재실행 사유가 아니다.

## Verification Mode
Fast Flow Task에 `Verification Mode`가 있으면 다음 최소 검증을 적용한다. 사용자가 더 강한 검증을 명시하면 사용자 요구가 우선한다.

- `DOCS`: 실행 코드 미변경. scoped change summary와 whitespace/path 검증만 수행한다.
- `COMPILE`: JavaDoc/주석 등 executable behavior 미변경 source 수정. Java 프로젝트는 compile을 기본으로 한다.
- `TARGETED_TEST`: 실행 로직 변경. Task Test Plan의 관련 targeted test를 실행한다.
- 모드와 실제 diff가 충돌하면 실제 변경 위험도에 맞춰 검증을 상향한다.

## Verification Execution Budget
검증은 가능한 한 **최종 변경 이후 소수의 명령**으로 끝낸다.

1. 버그 재현이 필요하지 않다면 구현 전 테스트를 미리 반복 실행하지 않는다.
2. 여러 Java targeted test는 가능한 경우 한 Gradle/Maven invocation으로 합친다.
   예: `./gradlew test --tests A --tests B`.
3. frontend 테스트는 마지막 frontend source 변경 이후 한 번 실행한다.
4. PASS 이후 해당 검증이 커버하는 production/test 파일이 바뀌지 않았다면 같은 명령을 다시 실행하지 않는다.
5. 테스트가 unrelated lifecycle/build 환경 단계 때문에 실패하면 원인을 확인해 **한 번만** 조정된 targeted 명령으로 재시도하고, 원래 실패 명령을 반복하지 않는다.
6. 테스트 실패를 수정하기 위해 source를 바꿨다면 그 실패를 재현한 최소 검증과 최종 consolidated 검증만 수행한다.
7. 최종 문서/주석-only 수정은 이미 PASS한 behavior test를 무효화하지 않는다.
8. verification command가 PASS했으면 단순 확신 확보 목적으로 reviewer와 동일한 테스트를 미리 반복하지 않는다.

## Scoped Change Verification / EOL Contract
변경 검증은 Task 대상 파일을 `--include`로 넘겨 한 번에 처리한다.

```bash
python3 /opt/custom-skills/coder/dev-implement-plan/scripts/change_summary.py \
  --workspace "<Workspace>" \
  --include "<changed-path-1>" \
  --include "<changed-path-2>"
```

- `--include`가 있으면 해당 경로만 검사하고 전체 raw `git status`를 context에 출력하지 않는다.
- `TRACKED_*`는 실제 content change, `EOL_ONLY_*`는 CRLF/LF-only noise다.
- untracked 파일의 `git diff --no-index --check` return code `1`은 정상 diff 상태로 처리한다.
- `EOL_ONLY_COUNT > 0`만으로 실패 처리하거나 파일을 Python/sed/perl 등으로 rewrite/normalize하지 않는다.
- whitespace error가 실제 보고된 경우에만 해당 변경 line을 수정한다.
- 동일 정보를 얻기 위해 별도 `git status`, `git diff --no-index`, `git diff --check`, script source read를 반복하지 않는다.

## Java Toolchain Contract
DevKit image는 JDK 8/17/21을 제공하며 프로젝트 작업에서는 `.hermes/toolchain.env` 결과를 사용한다.

```bash
hermes-java ./gradlew test
hermes-java ./gradlew compileJava
hermes-java ./mvnw test
```

Project build file을 Java version/toolchain 자동 변경 목적으로 수정하지 않는다.

## Fast Flow Review Risk
Risk 판정은 파일 수보다 **behavior 영향 범위와 compatibility 의미**를 우선한다.

### REVIEW_REQUIRED trigger
다음 중 하나라도 있으면 Fast Flow self-complete하지 않고 review로 보낸다.

- public API / request / response contract 의미 변경
- DB schema / Entity relation 변경
- dependency 변경
- transaction / security / concurrency 정책 영향
- complex QueryDSL / Native Query
- package/module/common architecture 의미 변경
- shared/common Utility의 **behavioral change**
- 여러 실행 흐름이 함께 사용하는 공통 코드의 의미 변경
- legacy/fallback/backward compatibility 동작 변경
- `application.properties` 등 운영 설정의 조회/저장 의미 변경
- file persistence / property key resolution / serialization 의미 변경
- task-coupled refactor가 여러 production type으로 확장되거나 영향 범위가 불명확함

### LOW positive eligibility
`LOW`는 위험 trigger가 없다는 것만으로는 부족하고 다음을 모두 evidence로 확인해야 한다.

1. 변경이 기존 패턴의 작은 local behavior다.
2. consumer/영향 범위가 단일 또는 명확히 제한되어 있다.
3. compatibility semantics가 바뀌지 않는다.
4. operational config/persistence semantics가 바뀌지 않는다.
5. targeted/declared verification이 PASS다.
6. Structural Quality Check가 PASS다.
7. residual risk가 명확히 낮다.

하나라도 증명되지 않거나 불확실하면 `REVIEW_REQUIRED`다.

Risk Reasons는 Reviewer가 시작점으로 재사용할 수 있게 짧고 구조화한다.

```text
Review Risk: REVIEW_REQUIRED
Risk Reasons:
- Impact Scope: SHARED | LOCAL | API | DATA | ...
- Compatibility: LEGACY_FALLBACK | UNCHANGED | ...
- Operational Config: APPLICATION_PROPERTIES | NONE | ...
- Reason: <구체적인 behavior 영향>
```

## 공통 Coding Rules 핵심
- 기존 abstraction/library/pattern을 재사용하고 unrelated refactor를 섞지 않는다.
- 함수/메서드 실행 block은 기본 `2-depth`; 반복 I/O/N+1을 확인한다.
- API는 기존 공통 response/error contract를 유지한다.
- JPA 조회는 단순 Method Query → 복잡/동적 QueryDSL → 근거 있는 Native Query 순서다.
- Javadoc은 구현을 번역하지 않고 업무 의도·전제·실패/retry 의미·입출력 계약을 설명한다.

## Handoff / Completion Evidence
```text
Reviewer Profile
Pattern References
Applied Capability Skills
Java Target / Runtime (Java project)
Changed Files
Verification Mode
Structural Quality Check: PASS | REFACTORED | ESCALATED
Refactor Triggers
Refactor Scope
Javadoc/Comment Review: PASS | UPDATED
Behavior Preserved By
Intentional Non-Refactors
Verification Commands / Results
Verification Final: true
Review Risk: LOW | REVIEW_REQUIRED
Risk Reasons
Residual Risk
```

`Verification Final: true`는 기록된 PASS 검증 이후 해당 검증이 커버하는 executable source/test가 다시 변경되지 않았음을 뜻한다. Reviewer는 이 evidence를 재실행 여부 판단에 사용할 수 있다.

## 불변식
- Workspace 밖 수정, branch 전환, 다른 worktree 생성, commit, push, PR, merge, reset, clean, stash 금지.
- secret/raw credential 기록 금지.
- JDK/Gradle/Maven task-time 설치 금지.
- Fast Flow에서는 raw `git status`의 EOL-only noise를 사용자 변경으로 승격하지 않는다.
- EOL noise 해결을 위해 사용자 source 전체를 line-ending rewrite하지 않는다.
- behavior/API/schema 의미 변경을 refactor라는 이름으로 섞지 않는다.
- Fast Flow `LOW`는 absence-of-risk 추론이 아니라 positive evidence로만 허용한다.
- `CHANGES_REQUESTED`는 terminal 상태가 아니며 original coder가 동일 Workspace에서 blocking finding만 수정 후 반드시 재-review한다.
- Standard Flow에서 Coder self-complete 금지.

retry/BLOCKED/검증/risk metadata 세부 형식이 필요하면 `references/implementation-details.md`를 읽는다.
