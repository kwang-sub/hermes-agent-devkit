---
name: dev-implement-plan
description: 승인된 Kanban 작업을 할당 Workspace에서 최소 구현·구조 품질 점검·검증하고 Fast Flow는 risk에 따라 완료 또는 review, Standard Flow는 reviewer에게 인계한다.
version: 0.19.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, implementation, coder, kanban, workspace, review, fast-flow, capability, java, refactor, structural-quality, performance]
    related_skills: [dev-fast-flow, dev-breakdown, dev-workspace-dispatch, dev-review-cycle, dev-code-review, dev-java-guidelines, dev-spring-guidelines, dev-spring-feature, dev-spring-data, dev-spring-test, dev-spring-refactor, dev-api-docs]
    requires_tools: [terminal, kanban_show, kanban_request_review, kanban_complete, kanban_block, kanban_heartbeat, skill_view]
---

# dev-implement-plan

Coder worker의 compact 실행 계약이다. 상세 구현/검증/risk 형식이 필요할 때만 `references/implementation-details.md`를 읽는다.

## 실행 순서 — Workspace Verify First

Coder run은 다음 순서를 고정한다.

```text
kanban_show
→ dev-implement-plan load
→ verify_workspace.py 단독 1회
→ STATUS=valid
→ 필요한 target source/test만 탐색
→ 구현
→ targeted verification
→ IMPLEMENTATION_STABLE
→ final regression gate (필요한 경우 full test 1회)
→ change_summary.py 1회
→ terminal transition 1회
```

**`verify_workspace.py`는 Coder가 Task를 읽은 뒤 실행하는 첫 terminal command다.** Skill load는 가능하지만 그 전에 workspace를 훑는 terminal probe는 실행하지 않는다.

Workspace 검증 전에 다음 명령 또는 동등한 inline Python/subprocess 조합을 실행하지 않는다.

```text
git status
git diff
git branch
git rev-parse
git ls-files
tracked/effective/EOL 변경 분류
working-tree 파일 개수 계산
```

Task body의 Workspace / Expected Branch / Base SHA는 Orchestrator가 이미 확정한 dispatch contract이므로 사전 재검증하지 않는다.

## Canonical Workspace Verification

Workspace 검증은 아래 **독립 terminal command로 정확히 1회** 실행한다. 다른 명령을 `+`, `&&`, `;`, background process 또는 batch 형태로 붙이지 않는다.

```bash
python3 /opt/custom-skills/coder/dev-implement-plan/scripts/verify_workspace.py \
  --task-key "<Task Key>" \
  --workspace "<Workspace>" \
  --expected-workspace "<Workspace>" \
  --expected-branch "<Expected Branch>" \
  --base-sha "<Base SHA>"
```

`STATUS=valid`이면 helper가 확인한 workspace/branch/base를 신뢰한다. 이를 재확인하기 위한 `git status`, `git branch`, `git rev-parse` probe를 실행하지 않는다. helper가 non-zero로 실패했을 때만 reported error를 해석하기 위한 최소 probe를 허용하며, 실패 전에 사전 probe로 우회하지 않는다.

특히 Windows bind mount에서 raw `git status`는 수천 개 EOL-only 파일 때문에 매우 비쌀 수 있다. raw modified-file 개수를 baseline으로 재정의하거나 작업 중단 근거로 사용하지 않는다.

## Existing Changes Preservation Fast Path

Task body에 다음 중 하나가 있으면 Orchestrator가 기존 workspace 전체 변경 보존을 이미 승인한 것이다.

```text
Existing changes preservation approved: true
Workspace change scan mode: skipped-approved-preservation
```

이 경우 Coder는 exact pre-existing file list/count를 복구하려고 repository-wide `git status`, `git diff`, `git ls-files --others`, EOL 분류를 다시 실행하지 않는다. 기존 변경 전체를 baseline으로 보존하고 자신의 실제 변경 path만 별도로 추적한다.

## Flow: FAST

Fast Flow는 Task의 `Pre-existing effective changes at dispatch`를 기존 사용자 변경 baseline으로 사용한다. raw `git status`의 EOL-only noise를 사용자 변경으로 승격하지 않는다.

다음처럼 설계 판단이 필요한 경우 `FAST_FLOW_ESCALATION_REQUIRED`로 `kanban_block`한다.

- API/schema/dependency/architecture 의미 변경
- transaction/security/concurrency 영향
- cross-repo 변경
- 요구사항이 모호해 구현 방향을 임의로 정해야 함

## Source / Scope 계약

Task의 `Project Pattern Summary`, `Pattern References`, `Goal`, `Acceptance Criteria`, `Implementation Tasks`, 기존 변경 baseline을 재사용한다. 실제 source와 충돌하지 않는 한 프로젝트 전체를 다시 분석하지 않는다.

첫 production patch 전에 다음을 만족한다.

```text
SOURCE_EVIDENCE_READY
Target:
- <file/symbol>
Direct Impact:
- <caller/callee/persistence boundary>
Tests:
- <existing test path>
Open Questions: NONE

IMPLEMENTATION_SCOPE_READY
Production:
- <files>
Tests:
- <files>
Docs:
- <files if required>
Excluded:
- <directly checked but unchanged>
```

탐색 규칙:
- Task/Pattern References에 정확한 path가 있으면 바로 사용한다.
- 같은 목적 symbol은 한 grep으로 묶는다.
- 큰 파일은 필요한 symbol 주변만 읽는다.
- `Open Questions: NONE`이면 반복 grep/find/read를 종료한다.
- 존재가 확인되지 않은 예상 test 파일을 연속 probe하지 않는다.
- 기존 사용자 변경을 reset/restore/clean/stash하지 않는다.

## Java / Spring capability lazy-load

실제 evidence가 필요한 경우에만 로드한다.

- Java 언어/convention → `skill_view("dev-java-guidelines")`
- 공통 Spring 규칙 → `skill_view("dev-spring-guidelines")`
- API/Controller/Service/DTO/Validation/Exception → `skill_view("dev-spring-feature")`
- JPA/Repository/QueryDSL/Converter/Paging → `skill_view("dev-spring-data")`
- 테스트 작성/수정 → `skill_view("dev-spring-test")`
- Spring source 구현 완료 후 **구조 trigger**가 실제로 있을 때만 → `skill_view("dev-spring-refactor")`
- OpenAPI/Swagger/Postman → `skill_view("dev-api-docs")`

Java 프로젝트에서는 `dev-java-guidelines`가 Java version/build/Lombok/type placement/JavaDoc만 담당하고, 공통 품질 규칙은 `coding-rules.md`, Spring 규칙은 Spring capability에 맡긴다.

구조 점검 evidence는 `Structural quality check: PASS | REFACTORED | ESCALATED`로 남긴다.

## Java / Gradle 검증

Java/Gradle/Maven 프로젝트는 Bootstrap의 `.hermes/toolchain.env`를 사용한다. JDK/Gradle/Maven을 task-time에 설치하지 않는다.

Gradle compile/targeted test의 canonical 실행은 `scripts/gradle_verification.py`다.

```bash
python3 /opt/custom-skills/coder/dev-implement-plan/scripts/gradle_verification.py \
  --workspace "<Workspace>" \
  --mode TARGETED_TEST \
  --test "<fully-qualified-test-selector>"
```

규칙:
- 여러 targeted test는 가능한 한 한 invocation으로 합친다.
- 구현 중에는 targeted test 또는 필요한 integration/module test만 사용한다.
- **전체 `test`는 탐색/중간 확인 용도로 실행하지 않는다. `IMPLEMENTATION_STABLE` 이후 final regression gate에서만 실행한다.**
- 전체 test가 필요한 작업은 canonical helper의 `--mode COMPILE --task test`를 **최종 회귀 게이트 용도로만** 사용한다.
- 한 stable verification cycle에서 full test는 기본 **1회**다. 동일 실패를 확인하기 위해 같은 전체 test를 반복하지 않는다.
- 실제 BUILD_FAILURE는 source/test 수정 후 최소 재검증할 수 있다.
- PASS 이후 해당 executable source/test가 바뀌지 않으면 같은 검증을 반복하지 않는다.
- `GRADLE_STATUS=BLOCKED`이면 direct Gradle 반복이나 우회 wrapper를 만들지 않는다.
- Maven 등 비-Gradle launcher 경로만 `hermes-java`를 사용한다.

### Full Test 실패 재사용 정책

Full test가 실패하면 즉시 반복 실행하지 않고 실패를 먼저 분류한다.

```text
FULL_TEST_FAILURE_CLASSIFICATION
- IN_SCOPE_OR_IMPACTED
- OUT_OF_SCOPE_UNCHANGED
- UNCERTAIN
```

`OUT_OF_SCOPE_UNCHANGED`는 다음 evidence가 모두 있을 때만 사용할 수 있다.

- 실패한 test/source가 Task의 Changed Files에 포함되지 않는다.
- `SOURCE_EVIDENCE_READY`의 Direct Impact 기준으로 변경 production symbol이 실패 test의 직접 영향 범위가 아니다.
- 첫 full test 이후 해당 실패를 고치기 위한 production/test 변경을 하지 않았다.
- 실패 signature(test class/method 또는 동일한 failure message)가 첫 실행과 동일하다.

이 경우 첫 full test의 failure evidence를 재사용하고 **같은 Coder run에서 전체 test를 다시 실행하지 않는다.** Reviewer handoff에는 `Full Test: FAIL_REUSED_OUT_OF_SCOPE`와 failure signature를 남긴다.

`IN_SCOPE_OR_IMPACTED`이면 해당 실패를 먼저 targeted test로 재현/수정하고, 다시 `IMPLEMENTATION_STABLE`이 된 뒤 full test를 최종 1회 실행할 수 있다. `UNCERTAIN`은 evidence 재사용으로 우회하지 않고 risk/blocker로 남긴다.

## Implementation Stable / Final Scope

전체 회귀 검증 전에 다음을 확정한다.

```text
IMPLEMENTATION_STABLE
- Production scope fixed: true
- Test scope fixed: true
- Additional production edits planned: false
- Structural quality check: PASS | REFACTORED | ESCALATED
```

검증 순서는 다음을 기본으로 한다.

```text
targeted/integration verification
→ IMPLEMENTATION_STABLE
→ full test 1회 (Task/Standard Flow/AC에서 필요한 경우)
→ failure classification 또는 PASS 확정
→ bootJar 등 artifact 검증 (필요한 경우)
→ scoped change_summary.py 1회
```

Full test 이후 executable production/test를 수정하면 해당 full-test evidence는 무효다. 단, `OUT_OF_SCOPE_UNCHANGED`로 분류한 실패 때문에 코드를 수정하지는 않는다.

최종 변경 범위가 확정된 뒤 scoped `change_summary.py`를 최종 검증으로 1회 실행한다.

```bash
python3 /opt/custom-skills/coder/dev-implement-plan/scripts/change_summary.py \
  --workspace "<Workspace>" \
  --include "<changed-path-1>" \
  --include "<changed-path-2>"
```

Standard Flow에서 `--include` 없이 `change_summary.py`를 호출하지 않는다. `--allow-full-scan`은 명시적 진단 전용이다. tracked와 untracked 모두 Git pathspec으로 제한하며 unrelated repository 전체를 훑지 않는다.

`EOL_ONLY_COUNT > 0` + `WHITESPACE_ERROR_COUNT=0`은 정상이다. EOL 복구를 위해 Python/sed/perl/awk/dos2unix/unix2dos/전체 rewrite를 하지 않는다. final summary 이후 executable source/test가 바뀌면 기존 fingerprint와 `Verification Final: true`는 무효다.

`change_summary.py`가 DevKit runtime/capability 문제로 실패하면 **임시 wrapper/script 생성**, executable bit 변경, inline Python monkey-patch, protected `.hermes` write, approval 대기 등으로 우회하지 않고 `CAPABILITY` blocker로 종료한다.

## Review Risk / Handoff

**Standard Flow 또는 CHANGES_REQUESTED 재작업은 항상 review**한다. Fast Flow는 LOW를 positive evidence로 증명한 경우만 self-complete 가능하다.

다음은 `REVIEW_REQUIRED`다.
- API/request/response 의미 변경
- DB schema/data/query 의미 변경
- transaction/security/concurrency 영향
- shared/common behavior 변경
- legacy/fallback/backward compatibility 변경
- operational config/persistence 의미 변경
- 영향 범위 불명확

Review handoff에는 최소 다음을 남긴다.

```text
Changed Files:
- ...
Verification Mode: <mode>
Verification Commands / Results:
- <command> -> PASS | FAIL
Full Test: PASS | NOT_REQUIRED | FAIL_REUSED_OUT_OF_SCOPE | FAIL_IN_SCOPE | UNCERTAIN
Full Test Failure Signature: <test/method/message | NONE>
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

가능한 경우 `kanban_request_review` metadata에도 `verification_final`, `verification_mode`, `effective_scope_sha256`, `verification`, `changed_files`, `review_risk`, `risk_reasons`, `residual_risk`를 기록한다.

## Terminal transition

한 Coder run의 terminal transition은 `kanban_complete`, `kanban_block`, `kanban_request_review` 중 정확히 하나다.

- Standard Flow에서 Coder self-complete 금지.
- `CHANGES_REQUESTED`는 terminal 상태가 아니며 **original coder가 동일 Workspace**에서 blocking finding만 수정 후 반드시 재-review한다.
- `kanban_request_review` 성공 후 즉시 종료한다. 추가 `kanban_complete`, reviewer skill load, `kanban_show`, status probe를 실행하지 않는다.

## 공통 Coding Rules 핵심

`/opt/data/shared/references/coding-rules.md`를 적용한다.

- 기존 abstraction/library/pattern을 재사용하고 unrelated refactor를 섞지 않는다.
- 함수/메서드 실행 block은 기본 `2-depth`를 지향한다.
- 반복 I/O/N+1을 확인한다.
- API는 기존 common response/error contract를 유지한다.
- JPA는 단순 Method Query → 복잡/동적 QueryDSL → 근거 있는 Native Query 순서다.

## 공통 불변식

- Workspace 밖 수정, branch 전환, 다른 worktree 생성, commit, push, PR, merge, reset, clean, stash 금지.
- secret/raw credential 기록 금지.
- behavior/API/schema 의미 변경을 refactor라는 이름으로 섞지 않는다.
- existing preservation fast path를 이유로 repository-wide dirty/EOL/untracked scan을 재실행하지 않는다.

retry/BLOCKED/검증/risk metadata의 추가 세부 형식이 필요할 때만 `references/implementation-details.md`를 읽는다.
