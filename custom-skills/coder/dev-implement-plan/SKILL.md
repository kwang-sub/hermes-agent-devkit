---
name: dev-implement-plan
description: 승인된 Kanban 작업을 할당 Workspace에서 최소 구현·구조 품질 점검·검증하고 Fast Flow는 risk에 따라 완료 또는 review, Standard Flow는 reviewer에게 인계한다.
version: 0.15.1
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
3. 모든 작업은 `/opt/data/shared/references/coding-rules.md`와 `/opt/data/shared/references/project-pattern-rules.md`를 적용하고 가장 가까운 기존 구현을 기준으로 최소 diff를 만든다.
4. Task의 `Project Pattern Summary`, `Pattern References`, `Applicable Skills`, `Goal`, `Acceptance Criteria`, `Implementation Tasks`를 재사용한다. 실제 source와 충돌하지 않는 한 프로젝트 전체를 다시 분석하지 않는다.
5. Spring은 실제 evidence로 필요한 Skill만 lazy-load한다. 적용할 때 반드시 해당 본문을 `skill_view()`로 읽는다.
   - Spring 공통 → `skill_view("dev-spring-guidelines")`
   - API/Controller/Service/DTO/Validation/Exception → `skill_view("dev-spring-feature")`
   - JPA/Repository/QueryDSL/Converter/Paging → `skill_view("dev-spring-data")`
   - **테스트 작성/수정** → `skill_view("dev-spring-test")` (단순 테스트 실행만으로는 로드하지 않음)
   - **Spring source 구현 완료 후 구조 trigger가 실제로 있을 때만** → `skill_view("dev-spring-refactor")`
   - OpenAPI/Swagger/Postman 작업 → `skill_view("dev-api-docs")`
6. Java/Gradle/Maven 프로젝트는 Bootstrap이 생성한 `.hermes/toolchain.env`를 사용한다. build/test/compile 명령은 `hermes-java` launcher를 우선한다. `.hermes/toolchain.env`가 없거나 선택 JDK가 유효하지 않으면 개발환경 bootstrap 문제로 `BLOCKED`한다.
7. 구현 전 반드시 `SOURCE_EVIDENCE_READY`와 `IMPLEMENTATION_SCOPE_READY`를 만족한다. 범위가 불안정한 상태에서 production patch를 시작하지 않는다.
8. 구현 후 `IMPLEMENTATION_STABLE`을 만족한 뒤 Verification Mode와 Task Test Plan에 따라 최소 검증을 수행한다. 동일한 PASS 검증을 관련 executable source/test 변경 없이 반복하지 않는다.
9. 최종 변경 범위가 확정된 뒤 scoped `scripts/change_summary.py`를 **최종 검증으로 1회** 실행한다. 실패하면 실제 reported error만 수정하고, 중간 상태 확인 용도로 반복 호출하지 않는다. 성공 시 출력되는 `EFFECTIVE_SCOPE_SHA256`를 final verification fingerprint로 보존한다.
10. 구현 후 `Review Risk`를 **positive eligibility** 방식으로 판정한다. `LOW`임을 근거로 증명하지 못하면 `REVIEW_REQUIRED`다. Standard Flow 또는 CHANGES_REQUESTED 재작업은 항상 review, Fast Flow + LOW는 complete, Fast Flow + REVIEW_REQUIRED는 review로 보낸다.
11. terminal transition은 `kanban_complete`, `kanban_block`, `kanban_request_review` 중 정확히 하나다. 성공한 `kanban_request_review` 이후 Coder는 추가 `kanban_complete`, review skill load, status probe를 하지 않고 즉시 종료한다.

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

## Source Evidence Map / Exploration Exit Gate
탐색 중 확인한 source/symbol을 짧은 Evidence Map으로 유지한다. 별도 파일을 만들 필요는 없다.

```text
SOURCE_EVIDENCE_READY
Target:
- <file/symbol>
Direct Impact:
- <caller/callee/persistence boundary>
Tests:
- <verified existing test paths>
Open Questions: NONE
```

`Open Questions: NONE`이면 source discovery는 종료한다. 이후 추가 grep/find/read는 새로운 test failure, source contradiction, scope expansion evidence가 생겼을 때만 허용한다.

### Pass 1 — Target
- Task body에 정확한 파일/심볼이 있으면 해당 경로부터 확인한다.
- 같은 목적의 symbol은 결과가 과도해지지 않는 범위에서 한 grep에 묶는다.
- 큰 source의 전체 read는 피하고 필요한 symbol 주변 약 100~250 lines를 우선한다.

### Pass 2 — Direct Impact
- direct caller/callee, 실제 persistence/external boundary, 관련 test까지만 확인한다.
- 동일 파일을 전체 read한 뒤 다시 큰 overlapping range로 읽지 않는다.
- 동일/유사 symbol grep은 원칙적으로 1회다.
- Pass 2 종료 시 `Open Questions`를 판정한다. `NONE`이면 즉시 exploration 종료.

### Pass 3 — Exception
Pass 1~2로 correctness/compatibility/risk 판단이 불가능할 때만 사용한다.

```text
Need additional evidence:
- Question: <판단이 안 되는 점>
- Required symbol/path: <직접 답하는 최소 범위>
```

단순 확신 확보를 위한 추가 탐색은 금지한다.

## Existence-Before-Read
파일명은 추측해서 read하지 않는다. 특히 `Foo.java`가 있다고 `FooTest.java`가 있다고 가정하지 않는다.

read 가능한 path는 다음 중 하나를 만족해야 한다.
- Task/Pattern References에 정확한 path가 있음
- 이전 grep/find 결과로 존재가 확인됨
- 이미 성공적으로 읽은 path의 bounded 추가 범위

존재가 확인되지 않은 예상 test 파일을 연속으로 probe하지 않는다.

## Implementation Scope Gate
첫 production patch 전에 최소 변경 범위를 확정한다.

```text
IMPLEMENTATION_SCOPE_READY
Production:
- <필수 production files>
Tests:
- <필수 test files>
Docs:
- <필요 시 docs>
Excluded:
- <검토했지만 변경 불필요한 직접 관련 files>
Reason:
- <왜 이 범위만 필요한지>
```

규칙:
- `IMPLEMENTATION_SCOPE_READY` 전 production patch 금지.
- scope에 없는 파일을 수정해야 하면 먼저 `Scope Expansion Evidence`를 남긴다.
- 새 evidence 없이 '혹시 필요할 수 있어서' 공통 utility/service/test를 넓게 수정하지 않는다.
- 기존 사용자 변경을 되돌리기 위한 reset/restore/clean/stash는 금지한다.

## Implementation Stable Gate
최종 behavior verification은 아래 상태에서 시작한다.

```text
IMPLEMENTATION_STABLE
- Production scope fixed: true
- Test scope fixed: true
- Additional production edits planned: false
- Structural quality check: PASS | REFACTORED | ESCALATED
```

버그 재현을 위해 pre-test가 반드시 필요한 경우는 예외지만, 구현 중간 상태에서 반복 confidence test를 돌리지 않는다.

## Documentation Reuse Rule
분석 Markdown이 포함되어도 문서 전용 repository 재탐색을 만들지 않는다.
- Source Evidence Map, Pattern References, 구현 중 확보한 source, 최종 diff를 재사용한다.
- 문서 작성 전에 별도 전체 비교 pass를 수행하지 않는다.
- 근거가 부족한 항목만 정확한 symbol 주변을 추가 확인한다.
- 문서-only 최종 수정은 이미 PASS한 behavior test를 무효화하지 않는다.

## Verification Mode
- `DOCS`: 실행 코드 미변경. scoped change summary와 whitespace/path 검증만 수행.
- `COMPILE`: 실행 의미 미변경 source. compile 기본.
- `TARGETED_TEST`: 실행 로직 변경. 관련 targeted test 기본.
- 실제 diff 위험도가 더 높으면 검증을 상향한다.

## Verification Execution Budget
1. 버그 재현이 필요하지 않다면 구현 전 테스트를 반복 실행하지 않는다.
2. 여러 Java targeted test는 가능한 한 한 Gradle/Maven invocation으로 합친다.
3. frontend 테스트는 마지막 frontend source 변경 이후 한 번 실행한다.
4. PASS 이후 해당 검증이 커버하는 executable source/test가 바뀌지 않았다면 같은 명령을 다시 실행하지 않는다.
5. unrelated lifecycle/build 환경 단계 때문에 실패하면 원인을 확인해 **한 번만** 조정된 targeted 명령으로 재시도한다.
6. test failure 수정으로 source가 바뀌면 실패를 재현한 최소 검증 + 최종 consolidated 검증만 수행한다.
7. 문서/주석-only 수정은 이미 PASS한 behavior test 재실행 사유가 아니다.

## Scoped Change Verification / EOL Recovery Hard Stop
최종 변경 검증은 확정된 변경 파일만 `--include`로 넘긴다.

```bash
python3 /opt/custom-skills/coder/dev-implement-plan/scripts/change_summary.py \
  --workspace "<Workspace>" \
  --include "<changed-path-1>" \
  --include "<changed-path-2>"
```

- `TRACKED_*`는 effective content change, `EOL_ONLY_*`는 CRLF/LF-only noise다.
- `EOL_ONLY_COUNT > 0` + `WHITESPACE_ERROR_COUNT=0`은 정상이며 파일을 수정하지 않는다.
- EOL-only 복구를 위해 Python/sed/perl/awk/dos2unix/unix2dos/전체 파일 rewrite를 실행하지 않는다.
- EOL-only 확인 뒤 별도 `git status`, `git diff --numstat`, `git diff --ignore-space-at-eol`, script source read를 반복하지 않는다.
- 실제 `WHITESPACE_ERROR`가 보고된 경우에만 해당 changed line을 수정한다.
- untracked 파일의 `git diff --no-index --check` return code `1`은 정상 diff 상태로 처리한다.
- change_summary는 Final Scope 이후 한 번 실행하는 것이 기본이며 중간 상태 확인용으로 사용하지 않는다.
- `EFFECTIVE_SCOPE_SHA256`는 effective tracked/untracked 파일의 path와 CRLF 정규화된 현재 content로 계산된다. final summary 이후 executable source/test가 바뀌면 기존 fingerprint와 `Verification Final: true`는 무효다.

## Java Toolchain Contract
```bash
hermes-java ./gradlew test
hermes-java ./gradlew compileJava
hermes-java ./mvnw test
```
Project build file을 Java version/toolchain 자동 변경 목적으로 수정하지 않는다.

## Fast Flow Review Risk
Risk 판정은 파일 수보다 **behavior 영향 범위와 compatibility 의미**를 우선한다.

### REVIEW_REQUIRED trigger
다음 중 하나라도 있으면 review로 보낸다.
- public API / request / response contract 의미 변경
- DB schema / Entity relation / dependency 변경
- transaction / security / concurrency 정책 영향
- complex QueryDSL / Native Query
- package/module/common architecture 의미 변경
- shared/common Utility의 behavioral change
- 여러 실행 흐름이 함께 사용하는 공통 코드의 의미 변경
- legacy/fallback/backward compatibility 동작 변경
- `application.properties` 등 운영 설정 조회/저장 의미 변경
- file persistence / property key resolution / serialization 의미 변경
- 영향 범위가 불명확함

### LOW positive eligibility
다음을 모두 확인한 경우만 `LOW`다.
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

## Structured Review Handoff
`REVIEW_REQUIRED`인 경우 `kanban_request_review` 전에 다음 evidence를 Task/comment 및 request summary에 기록한다.

```text
Changed Files:
- ...
Verification Mode: <mode>
Verification Commands / Results:
- <command> -> PASS | FAIL
Verification Final: true
Effective Scope SHA256: <EFFECTIVE_SCOPE_SHA256>
Structural Quality Check: PASS | REFACTORED | ESCALATED
Review Risk: REVIEW_REQUIRED
Risk Reasons:
- Impact Scope: ...
- Compatibility: ...
- Operational Config: ...
- Reason: ...
Residual Risk:
- ...
```

가능한 경우 `kanban_request_review` structured metadata에도 `verification_final`, `verification_mode`, `effective_scope_sha256`, `verification`, `changed_files`, `review_risk`, `risk_reasons`, `residual_risk`를 기록한다.

`Verification Final: true`는 기록된 PASS 이후 해당 검증이 커버하는 executable source/test가 다시 변경되지 않았고, 그 상태에서 final `change_summary.py`가 출력한 fingerprint를 handoff에 기록했다는 뜻이다. Reviewer는 동일 scope fingerprint를 재계산해 재실행 여부 판단에 사용한다.

`kanban_request_review` 성공 후 해당 Coder run은 handoff 완료로 간주하고 **즉시 종료**한다. `kanban_complete`, reviewer skill load, 추가 `kanban_show`를 시도하지 않는다.

## 공통 Coding Rules 핵심
- 기존 abstraction/library/pattern을 재사용하고 unrelated refactor를 섞지 않는다.
- 함수/메서드 실행 block은 기본 `2-depth`; 반복 I/O/N+1을 확인한다.
- API는 기존 공통 response/error contract를 유지한다.
- JPA 조회는 단순 Method Query → 복잡/동적 QueryDSL → 근거 있는 Native Query 순서다.

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
