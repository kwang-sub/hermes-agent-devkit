---
name: dev-code-review
description: 동일 Workspace의 미커밋 구현을 requirement/AC와 project pattern/capability/구조 품질 계약 기준으로 독립 검토하고 승인·수정요청·차단한다.
version: 0.11.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, review, reviewer, kanban, quality, verification, capability, java, refactor, structural-quality]
    related_skills: [dev-implement-plan, dev-review-cycle, dev-workspace-dispatch, dev-spring-guidelines, dev-spring-feature, dev-spring-data, dev-spring-test, dev-spring-refactor, dev-api-docs]
    requires_tools: [terminal, kanban_show, kanban_request_changes, kanban_complete, kanban_block, kanban_heartbeat, skill_view]
---

# dev-code-review

Reviewer의 compact 실행 계약이다.

## 실행 계약
1. `kanban_show()`에서 requirement/AC/scope, Pattern References, coder evidence, attempts/comments를 읽는다.
2. 같은 Workspace에서 `scripts/review_context.py`를 canonical 형식으로 한 번 실행해 Base SHA/Expected Branch/scoped changed paths/EOL noise와 `EFFECTIVE_SCOPE_SHA256`를 검증한다.
3. diff-first로 시작하고 changed hunk와 필요한 주변 source만 bounded read한다.
4. requirement/AC/correctness/compatibility/security/tests와 Coder verification claim을 대조한다.
5. capability 문서는 실제 finding 판단에 필요한 것만 lazy-load한다.
6. Coder의 `Review Risk`/`Risk Reasons`를 탐색 시작점으로 재사용하되 verdict는 독립적으로 판단한다.
7. Coder의 `Verification Final: true`, PASS command/result, handoff `Effective Scope SHA256`가 있고 reviewer의 `EFFECTIVE_SCOPE_SHA256`와 같으면 해당 검증을 기본 재사용한다. 단순 확신 확보를 위해 동일 테스트를 다시 실행하지 않는다.
8. fingerprint mismatch, verification 누락/실패/모호, P0/P1 의심, public API/schema/security/transaction/concurrency 고위험 contract에서 테스트가 핵심 판단 근거인 경우만 최소 재실행한다.
9. P0/P1이면 `kanban_request_changes`, 없고 evidence 충분하면 `kanban_complete`, 판단 불가/외부 결정이면 `kanban_block` 중 정확히 하나만 실행한다.

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

- `--include` scope만 검사한다.
- `EOL_ONLY_*`는 review failure가 아니다.
- 정상 실행 뒤 동일 정보를 위한 별도 status/diff-check/safe.directory probe를 반복하지 않는다.
- `EFFECTIVE_SCOPE_SHA256`는 Coder final change summary와 동일 알고리즘(path + CRLF 정규화된 effective changed file content)으로 계산한다.

## Verification Evidence Reuse
다음을 모두 만족하면 Coder verification을 재사용한다.

```text
Coder Verification Final: true
Coder Verification Result: PASS
Coder Effective Scope SHA256: A
Reviewer EFFECTIVE_SCOPE_SHA256: A
review_context STATUS: valid
```

추가 조건:
- Coder command가 현재 변경 behavior를 충분히 cover한다.
- diff 검토에서 verification claim과 모순되는 새 P0/P1 evidence가 없다.

이 경우 verdict evidence에 다음처럼 남기고 동일 test 재실행을 생략한다.

```text
Verification Evidence: REUSED
Fingerprint Match: true
Reason: coder final verification covers the unchanged effective scope
```

재실행 조건:
- fingerprint mismatch
- `Verification Final`/command/result/fingerprint 중 하나 누락
- Coder PASS 이후 executable source/test 변경 정황
- P0/P1 가능성을 직접 검증해야 함
- public API/schema/security/transaction/concurrency 등 고위험 contract에서 테스트 결과가 핵심 판단 근거

재실행 시 여러 Java test는 한 invocation으로 합치고 동일 PASS를 확신 확보용으로 반복하지 않는다.

## Diff-first Review Budget
- 먼저 changed hunk/diff를 본다.
- Risk Reasons의 impact/compatibility/config 범위를 재사용한다.
- diff만으로 이해 안 되는 symbol만 주변 source를 읽는다.
- 동일 파일 전체 read 후 overlapping range 반복 금지.
- 분석 Markdown 때문에 repository-wide 비교를 새로 하지 않는다.

## Common Coding Review Gate
- 기존 abstraction 재사용, scope, 2-depth, 반복 I/O/N+1을 확인한다.
- Style/nit만으로 승인을 막지 않는다.
- API 기존 response/error contract, JPA Method Query → QueryDSL → 근거 있는 Native Query 정책을 확인한다.
- 테스트가 변경 behavior/risk를 실제로 증명하는지 본다.

## Java / Build Verification Gate
- `.hermes/toolchain.env`가 있으면 Coder evidence와 대조한다.
- 재실행 필요 시 `hermes-java <wrapper command>`를 우선한다.
- 임의 JDK 다운로드/host Java 탐색 금지.

## Verdict
```text
P0/P1 + coder 수정 가능 → kanban_request_changes
P0/P1 없음 + evidence 충분 → kanban_complete
판단 불가/외부 결정 → kanban_block
```

## 불변식
- Reviewer는 source를 수정하지 않는다.
- secret/raw credential 출력 금지.
- commit/push/PR/cleanup 금지.
- EOL-only noise를 이유로 line ending 변경 금지.
- Coder Risk Reasons는 starting point이지 verdict가 아니다.
- fingerprint가 일치하고 verification reuse 조건을 모두 만족하면 동일 테스트 재실행을 기본적으로 하지 않는다.
