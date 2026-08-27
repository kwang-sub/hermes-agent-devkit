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
1. `kanban_show()`로 Task body, attempts, comments, feedback을 읽고 Workspace/Expected Branch/Base SHA를 `scripts/verify_workspace.py`로 검증한다. mismatch면 수정 전에 `BLOCKED`.
2. `Flow: FAST`는 Task의 `Pre-existing effective changes at dispatch`를 사용자 변경 baseline으로 사용한다. raw `git status`의 CRLF/LF noise로 baseline을 다시 정의하지 않는다. Fast 범위를 벗어나면 `FAST_FLOW_ESCALATION_REQUIRED`로 `kanban_block`한다.
3. `/opt/data/shared/references/coding-rules.md`, `/opt/data/shared/references/project-pattern-rules.md`, Task의 Pattern References/Applicable Skills를 재사용하고 가장 가까운 기존 구현 기준 최소 diff를 만든다.
4. Spring capability Skill은 실제 evidence로 필요할 때만 lazy-load한다. 단순 테스트 실행만으로 `dev-spring-test`를 로드하지 않는다.
5. Java/Gradle/Maven은 `.hermes/toolchain.env`와 `hermes-java`를 사용한다. toolchain이 없거나 유효하지 않으면 `BLOCKED`.
6. 구현 전 `SOURCE_EVIDENCE_READY`와 `IMPLEMENTATION_SCOPE_READY`, 구현 후 `IMPLEMENTATION_STABLE`을 만족한다.
7. Verification Mode/Test Plan에 따라 최소 검증을 수행하고 관련 executable source/test 변경 없이 동일 PASS를 반복하지 않는다.
8. 최종 변경 범위가 확정된 뒤 scoped `scripts/change_summary.py`를 최종 검증으로 1회 실행한다. `EFFECTIVE_SCOPE_SHA256`를 최종 handoff evidence로 보존한다.
9. `Review Risk`는 positive eligibility로 판정한다. LOW를 증명하지 못하면 `REVIEW_REQUIRED`다.
10. terminal transition은 `kanban_complete`, `kanban_block`, `kanban_request_review` 중 정확히 하나다. 성공한 `kanban_request_review` 이후 즉시 종료한다.

## Canonical Workspace Verification
```bash
python3 /opt/custom-skills/coder/dev-implement-plan/scripts/verify_workspace.py \
  --task-key "<Task Key>" \
  --workspace "<Workspace>" \
  --expected-workspace "<Workspace>" \
  --expected-branch "<Expected Branch>" \
  --base-sha "<Base SHA>"
```

## Source Evidence Map / Exploration Exit Gate
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

`Open Questions: NONE`이면 탐색을 종료한다. 새로운 test failure/source contradiction/scope expansion evidence가 있을 때만 다시 연다.

- Pass 1 Target: 정확한 대상 path/symbol부터 bounded read.
- Pass 2 Direct Impact: direct caller/callee, persistence/external boundary, 관련 test까지만.
- Pass 3 Exception: `Need additional evidence: Question -> Required symbol/path`가 명확할 때만 최소 탐색.
- 동일/유사 grep은 원칙적으로 1회이며 전체 read 뒤 overlapping range를 반복하지 않는다.

## Existence-Before-Read
파일명을 추측해서 read하지 않는다. path는 Task/Pattern References, grep/find 결과, 이미 성공적으로 읽은 path 중 하나로 존재가 확인돼야 한다.

## Implementation Scope Gate
첫 production patch 전에 다음을 확정한다.

```text
IMPLEMENTATION_SCOPE_READY
Production:
- ...
Tests:
- ...
Docs:
- ...
Excluded:
- ...
Reason:
- ...
```

scope 밖 파일 수정이 필요하면 먼저 `Scope Expansion Evidence`를 남긴다.

## Implementation Stable Gate
```text
IMPLEMENTATION_STABLE
- Production scope fixed: true
- Test scope fixed: true
- Additional production edits planned: false
- Structural quality check: PASS | REFACTORED | ESCALATED
```

이 상태 이후 최종 behavior verification을 시작한다.

## Documentation Reuse Rule
분석 Markdown은 Source Evidence Map, Pattern References, 구현 중 확보한 source, 최종 diff를 재사용한다. 문서 전용 repository 재탐색을 만들지 않는다. 문서-only 최종 수정은 이미 PASS한 behavior test를 무효화하지 않는다.

## Verification Mode
- `DOCS`: 문서-only. scoped change summary/whitespace 검증.
- `COMPILE`: executable behavior 미변경 source. compile 기본.
- `TARGETED_TEST`: 실행 로직 변경. 관련 targeted test 기본.
- 실제 diff 위험도가 더 높으면 상향한다.

## Verification Execution Budget
- 버그 재현이 필수가 아니면 구현 전 반복 테스트 금지.
- 여러 Java targeted test는 한 invocation으로 합친다.
- PASS 이후 관련 executable source/test가 안 바뀌면 같은 명령 재실행 금지.
- unrelated lifecycle/build 실패는 원인 확인 후 한 번만 조정된 targeted 명령으로 재시도.
- test failure 수정으로 source가 바뀌면 최소 재현 + 최종 consolidated 검증만.

## Scoped Change Verification / EOL Recovery Hard Stop
```bash
python3 /opt/custom-skills/coder/dev-implement-plan/scripts/change_summary.py \
  --workspace "<Workspace>" \
  --include "<changed-path-1>" \
  --include "<changed-path-2>"
```

- `TRACKED_*`는 effective content change, `EOL_ONLY_*`는 CRLF/LF-only noise.
- `EOL_ONLY_COUNT > 0` + `WHITESPACE_ERROR_COUNT=0`이면 정상이며 source를 rewrite하지 않는다.
- EOL 복구용 Python/sed/perl/awk/dos2unix/unix2dos/전체 파일 rewrite 금지.
- `EFFECTIVE_SCOPE_SHA256`는 effective tracked/untracked 파일의 path + CRLF 정규화된 현재 content로 계산되는 scoped fingerprint다. Reviewer가 같은 scope의 현재 상태를 재계산해 검증 결과의 유효성을 확인할 수 있다.
- 최종 summary 이후 executable source/test가 바뀌면 기존 fingerprint와 `Verification Final: true`는 무효다. 다시 필요한 최소 검증과 summary를 수행한다.

## Java Toolchain Contract
```bash
hermes-java ./gradlew test
hermes-java ./gradlew compileJava
hermes-java ./mvnw test
```
Project build file을 Java/toolchain 자동 변경 목적으로 수정하지 않는다.

## Fast Flow Review Risk
다음 중 하나라도 있으면 `REVIEW_REQUIRED`다.
- public API/request/response contract, DB schema/Entity relation/dependency 변경
- transaction/security/concurrency 정책 영향
- complex QueryDSL/Native Query
- package/module/common architecture 의미 변경
- shared/common Utility behavioral change
- 여러 실행 흐름 공통 코드 의미 변경
- legacy/fallback/backward compatibility 변경
- `application.properties` 등 운영 설정 조회/저장 의미 변경
- file persistence/property key resolution/serialization 의미 변경
- 영향 범위 불명확

`LOW`는 기존 패턴의 작은 local behavior, 제한된 consumer, compatibility/config/persistence unchanged, declared verification PASS, structural quality PASS, residual risk low를 모두 evidence로 확인한 경우만 허용한다.

## Structured Review Handoff
`REVIEW_REQUIRED`이면 `kanban_request_review`의 `summary`와 가능하면 structured `metadata`에 다음을 전달한다.

```text
Changed Files:
- ...
Verification Mode: <mode>
Verification Commands / Results:
- <command> -> PASS
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

가능한 경우 metadata key는 다음을 사용한다: `verification_final`, `verification_mode`, `effective_scope_sha256`, `verification`, `changed_files`, `review_risk`, `risk_reasons`, `residual_risk`.

`Verification Final: true`는 PASS 검증 이후 해당 검증이 커버하는 executable source/test가 바뀌지 않았고, 그 상태에서 final `change_summary.py`가 출력한 `EFFECTIVE_SCOPE_SHA256`와 handoff fingerprint가 동일함을 뜻한다.

`kanban_request_review` 성공 후 Coder run은 handoff 완료로 간주하고 즉시 종료한다. 추가 `kanban_complete`, reviewer skill load, `kanban_show`를 하지 않는다.

## 공통 Coding Rules 핵심
- 기존 abstraction/library/pattern 재사용, unrelated refactor 금지.
- 함수/메서드 실행 block 기본 `2-depth`; 반복 I/O/N+1 확인.
- API 기존 response/error contract 유지.
- JPA 조회: Method Query → QueryDSL → 근거 있는 Native Query.

## 불변식
- Workspace 밖 수정, branch 전환, worktree 생성, commit/push/PR/merge/reset/clean/stash 금지.
- secret/raw credential 기록 금지.
- task-time JDK/Gradle/Maven 설치 금지.
- EOL noise를 사용자 변경으로 승격하거나 source line ending을 rewrite하지 않는다.
- Fast Flow LOW는 positive evidence로만 허용한다.
- Standard Flow Coder self-complete 금지.
