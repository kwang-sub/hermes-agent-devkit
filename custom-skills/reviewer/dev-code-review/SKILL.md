---
name: dev-code-review
description: 동일 Workspace의 미커밋 구현을 requirement/AC와 project pattern/capability/구조 품질 계약 기준으로 독립 검토하고 승인·수정요청·차단한다.
version: 0.10.0
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
2. 같은 Workspace에서 `scripts/review_context.py`를 canonical 형식으로 **한 번** 실행해 Base SHA/Expected Branch/safe.directory/scoped changed paths/EOL noise를 검증한다.
3. Review는 **diff-first**로 시작한다. 전체 프로젝트를 다시 분석하지 않고 changed hunk와 그 주변 코드부터 본다. Kanban의 Pattern References를 재사용하고 correctness 판단에 필요한 경우에만 범위를 넓힌다.
4. requirement/AC/correctness/compatibility/security/tests와 Coder verification claim을 대조한다.
5. capability 문서는 실제 finding 판단에 필요한 것만 확인한다. 단순히 Coder가 여러 skill을 로드했다는 이유만으로 Reviewer가 모두 다시 읽지 않는다.
6. Spring source 변경에서는 Coder의 Structural Quality/Javadoc evidence를 실제 diff와 대조한다. 단순 파일 길이/클래스 수/개인적 선호만으로 finding을 만들지 않는다.
7. Coder의 `Verification Final: true`와 구체적인 PASS command/result가 있고 그 이후 관련 executable source/test 변경 증거가 없으면 이를 검증 evidence로 재사용한다. 독립 검토상 재실행이 필요한 경우에만 최소 명령을 실행한다.
8. P0/P1이 있으면 `kanban_request_changes`; 없고 evidence가 충분하면 `kanban_complete`; 안전한 판단 불가·외부 결정 필요·반복 blocker면 `kanban_block` 중 정확히 하나만 실행한다.

## Canonical Review Context
필수 인수를 생략한 probe나 별도 `git status` safe.directory probe를 먼저 수행하지 않는다.

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

- 스크립트가 Git `safe.directory`를 idempotent하게 등록한다.
- `--include`가 제공되면 task 변경 후보만 검사한다.
- `EOL_ONLY_*`는 CRLF/LF-only noise이며 review failure가 아니다.
- 정상 실행 뒤 동일 정보를 얻기 위한 별도 `git status`, `git diff --check`, safe.directory 환경변수 우회를 반복하지 않는다.

## Diff-first Review Budget
1. 먼저 Base SHA 기준 changed hunk/diff를 확인한다.
2. diff만으로 이해되지 않는 symbol만 주변 source를 bounded read한다.
3. 변경되지 않은 DTO/entity/repository/service를 전부 읽지 않는다. 실제 contract 근거가 필요할 때만 해당 symbol을 읽는다.
4. 동일 파일을 전체 read한 뒤 다시 큰 line range로 읽지 않는다.
5. 분석 Markdown은 구현 correctness의 근거가 아니라 설명 산출물이다. 문서와 source가 충돌할 때 source/diff를 우선하며, 문서를 검토하기 위해 repository-wide 비교 분석을 새로 수행하지 않는다.

## Verification Evidence Reuse
Reviewer의 독립성은 **모든 테스트를 다시 실행하는 것**이 아니라 evidence와 diff를 독립적으로 판단하는 것으로 유지한다.

Coder evidence를 그대로 재사용할 수 있는 조건:
- command와 결과가 명시되어 있음
- `Verification Final: true`
- 해당 PASS 이후 executable source/test 변경 증거 없음
- review 중 verification claim과 실제 diff의 모순 없음

재실행이 필요한 경우:
- P0/P1 가능성을 검증하려는 경우
- Coder verification이 누락/실패/모호한 경우
- public API/schema/security/transaction/concurrency처럼 contract risk가 높고 테스트가 핵심 판단 근거인 경우
- Coder PASS 이후 관련 executable source/test가 변경된 경우

재실행 규칙:
- 여러 Java test는 가능한 한 한 Gradle/Maven invocation으로 합친다.
- frontend는 affected spec을 한 번만 실행한다.
- 이미 PASS한 동일 명령을 단순 확신 확보용으로 반복하지 않는다.
- unrelated lifecycle task 때문에 Coder가 조정된 targeted command로 PASS했다면 reviewer도 원래 실패 command를 다시 실행하지 않는다.

## Common Coding Review Gate
- `/opt/data/shared/references/coding-rules.md`와 project pattern을 기준으로 기존 abstraction 재사용, scope, `2-depth`, 반복 I/O/N+1을 확인한다.
- Style/nit만으로 승인을 막지 않는다.
- API는 기존 response/error contract, JPA는 Method Query → QueryDSL → 근거 있는 Native Query 정책을 확인한다.
- 테스트는 변경 behavior와 risk를 실제로 증명하는지 본다.

## Structural Quality Review Gate
Task와 직접 연결된 책임 혼재, raw payload parsing/persistence/external I/O 결합, behavior-preserving verification 누락은 finding이 될 수 있다. 파일이 길다거나 더 예쁜 abstraction이 가능하다는 이유만으로 blocking finding을 만들지 않는다.

public API/schema/dependency/transaction/security/concurrency/architecture 의미 변경이 필요한 개선은 Coder에게 즉시 강제하지 않고 escalation/잔여 위험으로 분리한다.

## Stack / Capability Review Gate
현재 capability set은 `dev-spring-guidelines`, `dev-spring-feature`, `dev-spring-data`, `dev-spring-test`, `dev-spring-refactor`, `dev-api-docs`다. diff가 해당 영역이고 실제 review 판단에 필요한 계약만 읽는다. capability 재탐색을 위해 전체 repo를 다시 분석하지 않는다.

## Java / Build Verification Gate
- `.hermes/toolchain.env`가 있으면 Java target/runtime과 Coder evidence를 대조한다.
- Java build/test 재실행은 `hermes-java <wrapper command>`를 우선한다.
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
- Fast Flow `Review Risk: LOW` Task는 Coder가 완료하므로 Reviewer가 호출되지 않는다. Reviewer가 받은 Task는 독립 review가 필요한 것으로 간주한다.

Severity, 상세 checklist, retry/escalation이 필요하면 `references/review-details.md`를 읽는다.
