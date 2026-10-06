---
name: dev-review-cycle
description: 동일 Kanban card/workspace에서 Direct와 Standard Flow의 Coder→Reviewer 필수 review loop와 승인된 모델 전이를 보존하는 프로토콜.
version: 0.8.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, review, workflow, coder, reviewer, kanban, model, direct-flow, standard-flow]
    related_skills: [dev-implement-plan, dev-code-review, dev-flow-model-policy]
    requires_tools: [kanban_show, kanban_request_review, kanban_request_changes, kanban_complete, kanban_block, kanban_comment, terminal]
---

# dev-review-cycle

Direct/Standard 모두 구현 완료 후 Reviewer를 반드시 거친다.

```text
Coder running (approved Coder model)
→ kanban_request_review
   └─ trusted lifecycle handler가 review-enter 수행
→ Reviewer DEFAULT
   ├─ APPROVED → kanban_complete → done
   ├─ CHANGES_REQUESTED → kanban_request_changes
   │   └─ trusted lifecycle handler가 changes-return 수행
   │       → original coder approved model ready → fix → review
   └─ BLOCKED → kanban_block
```

## Worker Context 불변식
- `/opt/data/shared/references/kanban-execution-boundary.md`의 `KANBAN_EXECUTION_BOUNDARY_V1`을 적용한다. Kanban worker의 canonical identity와 lifecycle은 Task/Board/Workspace에서 오지만 launcher/timeout/retry/cache/process cleanup 같은 runtime HOW는 Kanban state에서 읽지 않는다.
- Kanban worker의 canonical identity는 현재 chat session이 아니라 Kanban Task/Board/Workspace다.
- 서버/컨테이너 재시작으로 이전 session이 없어져도 동일 Card를 requeue/unblock하고 dispatcher가 다시 spawn한다. Session affinity가 유효하면 RESUME, 없으면 NEW로 안전하게 시작한다.
- `HERMES_KANBAN_TASK`, `HERMES_KANBAN_BOARD`, `HERMES_KANBAN_DB`, `HERMES_KANBAN_WORKSPACE`, `HERMES_PROFILE`, `HERMES_SESSION_SOURCE=kanban`, `HERMES_KANBAN_CONTEXT_VERSION=1`은 dispatcher가 매 spawn마다 재구성하는 worker context다.
- `hermes --resume`은 일반 대화 재개용이며 Kanban lifecycle 재개 경로로 사용하지 않는다.
- Task prompt를 알고 있어도 worker context가 누락된 direct chat/manual resume에서는 구현·모델 전이·review handoff를 수행하지 않는다.

## 모델 전이 불변식
- Coder는 Task body의 승인된 `Coder Model Tier / Model / Provider` snapshot으로 실행한다.
- Reviewer는 별도 모델 승인 없이 Reviewer profile의 DEFAULT를 사용한다.
- Coder는 shell에서 `flow_model_policy.py review-enter`를 직접 호출하지 않고 claim-bound `kanban_request_review`를 호출한다.
- Reviewer는 shell에서 `flow_model_policy.py changes-return`을 직접 호출하지 않고 claim-bound `kanban_request_changes`를 호출한다.
- trusted lifecycle handler가 review-enter/changes-return과 rollback을 수행한다.
- lifecycle tool 실패 시 수동 model mutation/환경변수 주입으로 우회하지 않고 `kanban_block(kind=capability)`한다.
- retry/review cycle에서 ENV를 다시 해석하지 않는다. 동일 Task는 승인 당시 snapshot을 유지한다.
- Coder Model/Provider 변경이나 PREMIUM escalation은 사용자 재승인 없이는 금지한다.

## 세션 이력 보완 — SESSION_HISTORY_FINALIZE

Standard / Direct / Recovery / CHANGES_REQUESTED는 `/opt/data/shared/references/session-history-rules.md`의 `SESSION_HISTORY_BEST_EFFORT_V1`을 공통 적용한다. Coder/Reviewer 시작 capture는 해당 역할 entrypoint에서 수행한다. 별도 Flow별 추적 helper는 만들지 않는다.

미확인/comment 미완료일 때만 현재 역할의 `capture --phase finalize`를 최대 1회 호출한다. 이미 `SESSION_HISTORY_COMMENT_PENDING=false`로 기록된 추적은 생략한다. Coder는 `kanban_request_review` 직전, Reviewer는 `kanban_complete` / `kanban_request_changes` 직전, 다른 원인으로 중단하면 `kanban_block` 직전이다. 성공한 marker는 중복 없이 comment/ack-comment하고, finalize 이후에도 미확인/추적 오류 또는 marker/receipt 보완 실패가 남을 때만 `TASK_SESSION_HISTORY_WARNING`을 최대 1회 durable comment로 기록한다. 보완을 위해 terminal transition 뒤 도구 호출이나 background 수집기를 만들지 않는다.

`unavailable`만으로 BLOCK하지 않는다. Task/Workspace/승인·검증·lifecycle 오류는 기존 blocker를 유지한다. Reviewer ID를 Coder 누락에 대신 넣거나 새 Recovery 세션으로 과거 미확인이 복구됐다고 기록하지 않는다.

## 허용 전이
- `Flow: DIRECT | STANDARD` Coder 구현 완료 → verification/handoff evidence → `kanban_request_review`.
- Reviewer APPROVED → `kanban_complete`.
- 수정 가능한 P0/P1 → `kanban_request_changes`; original coder가 동일 Workspace에서 blocking finding만 수정 후 다시 Reviewer에게 보낸다.
- 판단 불가/외부 결정/동일 중요 blocker 반복 → `kanban_block`.

## 금지 전이
- Direct/Standard Coder self-complete.
- risk LOW를 이유로 Reviewer 우회.
- trusted lifecycle handler를 거치지 않은 model override 변경.
- 구현 완료 후 review 대용 `kanban_block`.
- correction을 위한 새 Review Card/Workspace 생성.
- Reviewer source 수정, P0/P1을 둔 APPROVED, 수정 가능한 finding을 BLOCKED로 종료.
- Reviewer PREMIUM 자동 승격 또는 Coder의 임의 모델 변경.
- Kanban task 재개를 위한 수동 `hermes --resume` worker 대체.

동일 중요 blocker가 3 review cycle 지속되면 Reviewer가 `kind=needs_input`으로 human escalation한다. 정상 완료는 `workspace remains + no commit/push`이며 cleanup하지 않는다.

상세 상태 전이는 `references/review-protocol.md`를 읽는다.
