---
name: dev-code-review
description: 동일 Workspace의 미커밋 구현을 requirement/AC와 project pattern/capability/구조 품질 계약 기준으로 독립 검토하고 승인·수정요청·차단한다.
version: 0.9.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, review, reviewer, kanban, quality, verification, capability, java, refactor, structural-quality]
    related_skills: [dev-implement-plan, dev-review-cycle, dev-workspace-dispatch, dev-spring-guidelines, dev-spring-feature, dev-spring-data, dev-spring-test, dev-spring-refactor, dev-api-docs]
    requires_tools: [terminal, kanban_show, kanban_request_changes, kanban_complete, kanban_block, kanban_heartbeat, skill_view]
---

# dev-code-review

Reviewer의 **compact 실행 계약**이다. 상세 severity/checklist/escalation은 필요할 때만 `references/review-details.md`를 읽는다.

## 실행 계약
1. `kanban_show()`에서 requirement/AC/scope, Pattern References, Applied Capability Skills, coder evidence, attempts/comments를 읽는다.
2. 같은 Workspace에서 `scripts/review_context.py`로 Base SHA/Expected Branch를 검증하고 해당 Base SHA 기준 diff + untracked + `git diff --check`를 read-only로 확인한다.
3. 전체 프로젝트를 다시 분석하지 않는다. Kanban의 Pattern References와 실제 diff 주변 코드부터 보고, correctness 판단에 필요한 경우에만 범위를 넓힌다.
4. requirement/AC/correctness/compatibility/security/tests와 Coder verification claim을 대조한다.
5. Task에 capability가 적용되었으면 Coder가 사용한 **동일 canonical capability 문서**를 확인한다. Reviewer role Skill은 `skill_view()`를 그대로 사용하고, Coder canonical capability는 Docker의 별도 read-only root `/opt/reviewer-skills/<skill>/SKILL.md`에서 읽는다.
   - `/opt/reviewer-skills/dev-spring-guidelines/SKILL.md`
   - `/opt/reviewer-skills/dev-spring-feature/SKILL.md`
   - `/opt/reviewer-skills/dev-spring-data/SKILL.md`
   - `/opt/reviewer-skills/dev-spring-test/SKILL.md`
   - `/opt/reviewer-skills/dev-spring-refactor/SKILL.md`
   - `/opt/reviewer-skills/dev-api-docs/SKILL.md`
   필요한 capability 파일이 없으면 DevKit mount 구성 문제로 보고한다. capability 재탐색을 위해 전체 repo를 다시 분석하지 않는다.
6. Spring source 변경에서는 Coder의 `Structural Quality Check`, `Refactor Triggers`, `Javadoc/Comment Review` evidence를 확인하고 실제 diff와 대조한다. 기능이 맞더라도 Task로 인해 드러난 명확한 책임 혼재를 그대로 남겼거나 상위 Service가 parsing/persistence/external I/O 세부 구현에 묻혀 업무 흐름을 읽기 어려우면 구조 finding으로 기록한다. 단순 파일 길이나 클래스 수만으로 finding을 만들지 않는다.
7. Javadoc/Comment는 프로젝트 스타일과 변경 의미를 기준으로 검토한다. 업무 의도·전제·실패/retry/idempotency/transaction 의미가 필요한 public/package 계약이나 주요 orchestration에 설명이 누락되었는지 보고, 복잡한 메서드의 단계 주석이 실제 처리 경계를 설명하는지 확인한다. 자명한 코드 번역 주석이나 과도한 주석도 개선 대상으로 본다.
8. Java/Gradle/Maven verification을 재실행해야 하면 프로젝트가 bootstrap한 `.hermes/toolchain.env`를 사용하는 `hermes-java` launcher를 사용한다. 예: `hermes-java ./gradlew test`. Reviewer가 임의 JDK를 다운로드하거나 host Java를 탐색하지 않는다.
9. P0/P1이 있으면 `kanban_request_changes`; 없고 evidence가 충분하면 `kanban_complete`; 안전한 판단 불가·외부 결정 필요·반복 blocker면 `BLOCKED`로 `kanban_block` 중 정확히 하나만 실행한다.

## Common Coding Review Gate
- `/opt/data/shared/references/coding-rules.md`와 project pattern을 기준으로 기존 abstraction 재사용, scope, `2-depth`, 반복 I/O/N+1을 확인한다.
- Style/nit만으로 승인을 막지 않는다.
- API는 기존 response/error contract, JPA는 Method Query → QueryDSL → 근거 있는 Native Query 정책을 확인한다.
- 테스트는 변경 behavior와 risk를 실제로 증명하는지 본다.

## Structural Quality Review Gate
다음은 Task 범위와 직접 연결된 경우 blocking 구조 finding이 될 수 있다.

- Service/use-case가 validation + mapping + persistence + external/file I/O를 과도하게 직접 수행해 책임 경계가 흐림.
- raw payload parsing이나 gateway/file 세부 동작이 orchestration과 섞여 변경 이해·검증을 어렵게 함.
- 동일 책임의 DTO/Resolver/Mapper/Context 추출이 프로젝트 기존 패턴으로 명확한데도 구현 세부가 상위 Service에 남아 있음.
- Coder가 구조 리팩터링을 수행했지만 behavior-preserving verification이 없음.
- 구조 문제를 주석만 추가해 덮음.

다음만으로는 blocking finding을 만들지 않는다.

- 파일/메서드가 길다.
- 클래스를 더 쪼갤 수 있다.
- 개인적 선호상 더 예쁜 abstraction이 가능하다.

public API/schema/dependency/transaction/security/concurrency/architecture 의미 변경이 필요한 개선은 Coder에게 즉시 강제하지 않고 escalation/잔여 위험으로 분리한다.

## Stack / Capability Review Gate
현재 capability set은 `dev-spring-guidelines`, `dev-spring-feature`, `dev-spring-data`, `dev-spring-test`, `dev-spring-refactor`, `dev-api-docs`다. diff가 해당 영역일 때만 관련 계약을 확인한다. Stack / Capability Review Gate를 위해 필요하지 않은 Skill/reference는 읽지 않는다.

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
- 구조 finding은 Task와 직접 연결되고 프로젝트 패턴으로 근거를 제시할 수 있어야 한다.
- Javadoc/주석의 개인적 문체 선호만으로 승인을 막지 않는다.
- Fast Flow `Review Risk: LOW` Task는 Coder가 완료하므로 Reviewer가 호출되지 않는다. Reviewer가 받은 Task는 독립 review가 필요한 것으로 간주한다.

Severity, 상세 checklist, retry/escalation이 필요하면 `references/review-details.md`를 읽는다.
