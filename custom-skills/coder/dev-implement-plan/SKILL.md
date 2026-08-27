---
name: dev-implement-plan
description: 승인된 Kanban 작업을 할당 Workspace에서 최소 구현·구조 품질 점검·검증하고 Fast Flow는 risk에 따라 완료 또는 review, Standard Flow는 reviewer에게 인계한다.
version: 0.12.0
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
   - **Spring source 구현 완료 후 구조 품질 점검/리팩터링** → `skill_view("dev-spring-refactor")`
   - OpenAPI/Swagger/Postman 작업 → `skill_view("dev-api-docs")`
6. Java/Gradle/Maven 프로젝트는 Bootstrap이 생성한 `.hermes/toolchain.env`를 사용한다. build/test/compile 명령은 `hermes-java` launcher를 우선한다.
   - Gradle: `hermes-java ./gradlew <task>`
   - Maven: `hermes-java ./mvnw <goal>`
   - `JAVA_HOME`을 임의 추측하거나 Windows host Java를 탐색하거나 Task 중 JDK를 다운로드하지 않는다.
   - `.hermes/toolchain.env`가 없거나 선택 JDK가 유효하지 않으면 개발환경 bootstrap 문제로 `BLOCKED`한다.
7. **Post-Implementation Structural Quality Gate**를 verification 전에 수행한다.
   - Standard Flow의 Spring source 변경은 `dev-spring-refactor`를 반드시 읽고 Structural Quality Check를 수행한다.
   - Fast Flow는 check를 수행하되 구조 trigger가 없으면 refactor 없이 진행한다.
   - Service가 validation/mapping/persistence/external I/O를 과도하게 직접 수행하거나, raw payload parsing·Gateway/File I/O·state persistence가 orchestration과 섞였거나, 상위 메서드만으로 업무 흐름이 읽히지 않으면 기존 프로젝트 패턴 안에서 task-coupled refactoring을 수행한다.
   - public API/schema/dependency/transaction/security/concurrency/package/module architecture 의미 변경이 필요하면 자동 refactor하지 않고 `REVIEW_REQUIRED` 또는 Fast Flow escalation으로 전환한다.
   - Javadoc/주석도 같은 Gate에서 검토한다. 동작이 자명하지 않은 public/package 계약, 주요 orchestration, retry/idempotency/transaction/file migration 같은 운영 의미에는 프로젝트 스타일의 Javadoc을 보강한다. 복잡한 메서드 내부에는 2~5개의 의미 있는 업무 단계가 있을 때만 흐름 주석을 사용한다. 좋은 이름/타입/메서드 추출을 주석보다 우선한다.
8. 구조 변경이 있었다면 targeted verification을 다시 실행한다. 이후 scoped `scripts/change_summary.py`로 필요한 범위만 검증한다. 전체 test suite는 변경 위험이나 기존 계약상 필요할 때만 실행하며 동일 실패를 환경 우회 목적으로 반복하지 않는다.
9. 구현 후 `Review Risk`를 판정한다.
   - **Standard Flow 또는 CHANGES_REQUESTED 재작업** → 항상 `kanban_request_review`.
   - **Fast Flow + LOW** → 근거, Structural Quality Check, verification을 기록하고 `kanban_complete`.
   - **Fast Flow + REVIEW_REQUIRED** → `kanban_request_review`.
10. terminal action 하나를 실행한 뒤 즉시 멈춘다. 구현 불가/필수 입력 누락/필수 검증 불가만 `kanban_block`한다. review 대용 `kanban_block`은 금지한다.

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

## Source Exploration Budget
토큰과 반복 탐색을 줄이되 correctness evidence는 유지한다.

1. Task body에 정확한 파일 경로가 있으면 해당 경로를 우선하며 repository-wide `find`를 먼저 수행하지 않는다.
2. 메서드/심볼이 명시되어 있으면 `grep(symbol)` → 필요한 line range `read` 순서로 확인한다.
3. 큰 source의 `L1-2000` 전체 읽기는 기본 금지한다. 한 번의 read는 필요한 symbol 주변 약 100~250 lines를 우선한다.
4. 새로운 evidence가 없는 한 같은 파일을 반복해서 read하지 않는다.
5. Task에 이미 기록된 분석/Pattern Reference를 검증하는 데 필요한 source만 추가 조사한다.
6. `DOCS`/`COMPILE` 성격의 비동작 변경에서는 architecture-wide dependency discovery를 하지 않는다.
7. exact path가 없거나 source evidence가 task body와 충돌할 때만 탐색 범위를 단계적으로 넓힌다.

## Verification Mode
Fast Flow Task에 `Verification Mode`가 있으면 다음 최소 검증을 적용한다. 사용자가 더 강한 검증을 명시하면 사용자 요구가 우선한다.

- `DOCS`: 실행 코드 미변경. scoped change summary와 whitespace/path 검증만 수행한다.
- `COMPILE`: JavaDoc/주석 등 executable behavior 미변경 source 수정. Java 프로젝트는 `hermes-java ./gradlew compileJava` 또는 대응 Maven compile을 기본으로 한다.
- `TARGETED_TEST`: 실행 로직 변경. Task Test Plan의 관련 targeted test를 실행한다.
- 모드와 실제 diff가 충돌하면 실제 변경 위험도에 맞춰 검증을 상향한다. 로직 변경을 `COMPILE`로 축소하지 않는다.

## Scoped Change Verification
변경 검증은 Task 대상 파일을 `--include`로 넘겨 한 번에 처리한다.

```bash
python3 /opt/custom-skills/coder/dev-implement-plan/scripts/change_summary.py \
  --workspace "<Workspace>" \
  --include "<changed-path-1>" \
  --include "<changed-path-2>"
```

- `--include`가 있으면 해당 경로만 검사하고 전체 raw `git status`를 context에 출력하지 않는다.
- untracked 파일은 내부적으로 `git diff --no-index --check`를 사용하며 return code `1`(차이 있음)은 정상 diff 상태로 처리한다. `>1` 또는 whitespace error 출력만 실패로 본다.
- 동일 정보를 얻기 위해 별도 `git status`, `git diff --no-index`, script source read를 반복하지 않는다.

## Java Toolchain Contract
DevKit image는 다음 JDK를 제공한다.

```text
/opt/jdks/temurin-8
/opt/jdks/temurin-17
/opt/jdks/temurin-21
```

DevKit 기본 `JAVA_HOME`은 Java 17이지만 프로젝트 작업에서는 기본값에 의존하지 않는다. `dev-project-bootstrap`이 Gradle/Maven 설정에서 target을 감지해 `.hermes/toolchain.env`를 만들며 Coder는 그 결과를 사용한다.

예:

```bash
hermes-java ./gradlew test
hermes-java ./gradlew compileJava
hermes-java ./mvnw test
```

Project build file을 Java version/toolchain 자동 변경 목적으로 수정하지 않는다.

## Fast Flow Review Risk
`LOW`는 기존 패턴의 작은 국소 변경이고 public API/DB schema/Entity relation/dependency/transaction/security/concurrency/복잡 QueryDSL/Native Query/공통 architecture 영향이 없으며 targeted/declared verification과 Structural Quality Check가 PASS일 때만 허용한다. task-coupled refactor가 여러 production type으로 확장되거나 구조 판단이 불확실하면 `REVIEW_REQUIRED`다.

## 공통 Coding Rules 핵심
- 기존 abstraction/library/pattern을 재사용하고 unrelated refactor를 섞지 않는다.
- 이번 Task로 드러난 구조적 복잡성을 behavior-preserving 방식으로 정리하는 것은 task-coupled refactor로 허용한다.
- 함수/메서드 실행 block은 기본 `2-depth`; 반복 I/O/N+1을 확인한다.
- Stack / Capability Skill은 기존 convention을 확장할 뿐 architecture/dependency/common contract를 임의 변경하지 않는다.
- API는 기존 공통 response/error contract를 유지한다.
- JPA 조회는 단순 Method Query → 복잡/동적 QueryDSL → 근거 있는 Native Query 순서다.
- Javadoc은 구현을 번역하지 않고 업무 의도·전제·실패/retry 의미·입출력 계약을 설명한다.
- 메서드 흐름 주석은 실제 처리 순서가 중요한 orchestration에만 제한적으로 사용한다.

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
Review Risk: LOW | REVIEW_REQUIRED
Risk Reasons
Residual Risk
```

LOW completion metadata에는 `flow=FAST`, `review_risk=LOW`, Structural Quality Check 근거와 verification을 남긴다. Reviewer handoff에는 동일 evidence를 보존한다.

## 불변식
- Workspace 밖 수정, branch 전환, 다른 worktree 생성, commit, push, PR, merge, reset, clean, stash 금지.
- secret/raw credential 기록 금지.
- JDK/Gradle/Maven task-time 설치 금지.
- Fast Flow에서는 raw `git status`의 EOL-only noise를 사용자 변경으로 승격하지 않는다.
- behavior/API/schema 의미 변경을 refactor라는 이름으로 섞지 않는다.
- 주석으로 나쁜 구조를 덮지 않으며 자명한 코드에 설명 주석을 반복하지 않는다.
- `CHANGES_REQUESTED`는 terminal 상태가 아니며 original coder가 동일 Workspace에서 blocking finding만 수정 후 반드시 재-review한다.
- Standard Flow에서 Coder self-complete 금지.

retry/BLOCKED/검증/risk metadata 세부 형식이 필요하면 `references/implementation-details.md`를 읽는다.
