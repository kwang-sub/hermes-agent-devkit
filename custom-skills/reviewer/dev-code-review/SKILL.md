---
name: dev-code-review
description: 동일 Workspace의 미커밋 구현을 requirement/AC와 project pattern/capability 계약 기준으로 독립 검토하고 승인·수정요청·차단한다.
version: 0.8.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, review, reviewer, kanban, quality, verification, capability, java]
    related_skills: [dev-implement-plan, dev-review-cycle, dev-workspace-dispatch, dev-spring-guidelines, dev-spring-feature, dev-spring-data, dev-spring-test, dev-api-docs]
    requires_tools: [terminal, kanban_show, kanban_request_changes, kanban_complete, kanban_block, kanban_heartbeat, skill_view]
---

# dev-code-review

Reviewer의 **compact 실행 계약**이다. 상세 severity/checklist/escalation은 필요할 때만 `references/review-details.md`를 읽는다.

## 실행 계약
1. `kanban_show()`에서 requirement/AC/scope, Pattern References, Applied Capability Skills, coder evidence, attempts/comments를 읽는다.
2. 같은 Workspace에서 `scripts/review_context.py`로 Base SHA/Expected Branch를 검증하고 해당 Base SHA 기준 diff + untracked + `git diff --check`를 read-only로 확인한다.
3. 전체 프로젝트를 다시 분석하지 않는다. Kanban의 Pattern References와 실제 diff 주변 코드부터 보고, correctness 판단에 필요한 경우에만 범위를 넓힌다.
4. requirement/AC/correctness/compatibility/security/tests와 Coder verification claim을 대조한다.
5. Task에 capability가 적용되었으면 Reviewer profile에서도 **동일 canonical capability Skill**을 `skill_view()`로 로드한다. DevKit Compose는 coder의 capability 디렉터리를 reviewer namespace에 read-only bind mount하므로 아래 Skill은 Reviewer에서도 존재해야 한다.
   - `dev-spring-guidelines`
   - `dev-spring-feature`
   - `dev-spring-data`
   - `dev-spring-test`
   - `dev-api-docs`
   해당 Skill이 없으면 단순 무시하지 말고 DevKit profile/mount 구성 문제로 보고한다. 다만 이미 충분한 Kanban evidence만으로 판정 가능한 경우 capability 재탐색을 위해 전체 repo를 다시 분석하지 않는다.
6. Java/Gradle/Maven verification을 재실행해야 하면 프로젝트가 bootstrap한 `.hermes/toolchain.env`를 사용하는 `hermes-java` launcher를 사용한다. 예: `hermes-java ./gradlew test`. Reviewer가 임의 JDK를 다운로드하거나 host Java를 탐색하지 않는다.
7. P0/P1이 있으면 `kanban_request_changes`; 없고 evidence가 충분하면 `kanban_complete`; 안전한 판단 불가·외부 결정 필요·반복 blocker면 `BLOCKED`로 `kanban_block` 중 정확히 하나만 실행한다.

## Common Coding Review Gate
- `/opt/data/shared/references/coding-rules.md`와 project pattern을 기준으로 기존 abstraction 재사용, scope, `2-depth`, 반복 I/O/N+1을 확인한다.
- Style/nit만으로 승인을 막지 않는다.
- API는 기존 response/error contract, JPA는 Method Query → QueryDSL → 근거 있는 Native Query 정책을 확인한다.
- 테스트는 변경 behavior와 risk를 실제로 증명하는지 본다.

## Stack / Capability Review Gate
현재 capability set은 `dev-spring-guidelines`, `dev-spring-feature`, `dev-spring-data`, `dev-spring-test`, `dev-api-docs`다. diff가 해당 영역일 때만 관련 계약을 확인한다. Stack / Capability Review Gate를 위해 필요하지 않은 Skill/reference는 읽지 않는다.

## Java / Build Verification Gate
- `.hermes/toolchain.env`가 있으면 Java target/runtime을 확인하고 Coder evidence와 일치하는지 본다.
- Java build/test 재실행은 `hermes-java <wrapper command>`를 우선한다.
- `./gradlew`/`./mvnw`를 다른 전역 JDK로 무심코 실행하지 않는다.
- JDK 8/17/21이 필요한데 DevKit image에 없거나 toolchain file이 bootstrap contract와 맞지 않으면 환경 문제로 분리한다.

## Verdict
```text
P0/P1 + coder가 수정 가능 → kanban_request_changes
P0/P1 없음 + evidence 충분 → kanban_complete
판단 불가/외부 결정/동일 blocker 3회 → kanban_block(kind=needs_input...)
```

`CHANGES_REQUESTED는 terminal 상태가 아니며` original coder에게 돌아간다. 같은 Workspace에서 blocking finding만 수정한 뒤 다시 review한다.

## 불변식
- Reviewer는 application/test/config source를 수정하지 않는다.
- secret/raw credential을 출력하지 않는다.
- commit, push, PR, cleanup 금지.
- finding은 file/symbol, evidence, required change, expected verification을 포함한다.
- Fast Flow `Review Risk: LOW` Task는 Coder가 완료하므로 Reviewer가 호출되지 않는다. Reviewer가 받은 Task는 독립 review가 필요한 것으로 간주한다.

Severity, 상세 checklist, retry/escalation이 필요하면 `references/review-details.md`를 읽는다.
