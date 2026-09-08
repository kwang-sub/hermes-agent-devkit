---
name: dev-review-cycle
description: 동일 Kanban card/workspace에서 coder와 reviewer가 risk 기반 Fast Flow와 필수 Standard review loop를 수행하며 승인된 모델 전이를 보존하는 프로토콜.
version: 0.6.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, review, workflow, coder, reviewer, kanban, model]
    related_skills: [dev-implement-plan, dev-code-review, dev-flow-model-policy]
    requires_tools: [kanban_show, kanban_request_review, kanban_request_changes, kanban_complete, kanban_block, terminal]
---

# dev-review-cycle

```text
Fast LOW: coder running → kanban_complete → done
Fast REVIEW_REQUIRED / Standard:
coder approved model
→ flow_model_policy.py review-enter --task-id <Task> --board <Board>
→ kanban_request_review
→ reviewer DEFAULT
→ APPROVED/done | CHANGES_REQUESTED
→ changes-return --task-id <Task> --board <Board>
→ original coder approved model ready
```

## Worker Context 불변식
- Kanban worker의 canonical identity는 현재 chat session이 아니라 Kanban Task/Board/Workspace다.
- 서버/컨테이너 재시작으로 이전 session이 없어지는 것은 허용한다. 이 경우 dispatcher는 `NEW` session을 만들되 Task context를 다시 주입해야 한다.
- `HERMES_KANBAN_TASK`, `HERMES_KANBAN_BOARD`, `HERMES_KANBAN_DB`, `HERMES_KANBAN_WORKSPACE`, `HERMES_PROFILE`, `HERMES_SESSION_SOURCE=kanban`, `HERMES_KANBAN_CONTEXT_VERSION=1`은 dispatcher가 매 spawn마다 재구성하는 worker context다.
- Coder/Reviewer가 표시하는 `Resume this session with: hermes --resume ...` 명령은 일반 대화 재개용이며 Kanban lifecycle 재개 경로로 사용하지 않는다.
- 서버 재시작 또는 worker crash 뒤 작업을 이어갈 때는 동일 Card를 requeue/unblock하고 dispatcher가 다시 spawn하게 한다. Session affinity가 유효하면 RESUME, 없거나 session DB가 유실되었으면 NEW로 안전하게 시작한다.
- Task prompt를 알고 있더라도 worker context가 누락된 direct chat/manual resume에서는 모델 전이·review handoff를 수행하지 않는다.

## 모델 전이 불변식
- Coder는 Task body의 승인된 `Coder Model Tier / Model / Provider` snapshot으로 실행한다.
- Reviewer는 별도 모델 승인 없이 항상 Reviewer profile의 DEFAULT를 사용한다.
- Coder가 review를 요청하기 직전 아래처럼 **현재 `kanban_show`에서 읽은 Task ID와 Board를 명시적으로 전달**하고 `STATUS=review-default-ready`를 확인한다.

```bash
python3 /opt/data/shared/scripts/flow_model_policy.py review-enter \
  --task-id "<Task ID>" \
  --board "<Board>"
```

- Reviewer가 CHANGES_REQUESTED를 반환하기 직전에도 ENV fallback에 의존하지 않고 Task ID와 Board를 명시적으로 전달한다.

```bash
python3 /opt/data/shared/scripts/flow_model_policy.py changes-return \
  --task-id "<Task ID>" \
  --board "<Board>"
```

- `flow_model_policy.py`의 ENV fallback은 수동 진단/하위호환용이다. Standard/Fast review transition의 canonical 호출은 항상 `--task-id` + `--board` 명시 방식이다.
- 모델 helper 실패 시 잘못된 모델로 다음 lane을 dispatch하지 않는다. `kanban_block(kind=capability)`으로 종료한다.
- retry/review cycle에서 ENV를 다시 해석하지 않는다. 동일 Task는 승인 당시 snapshot을 유지한다.
- Coder Model/Provider 변경이나 PREMIUM escalation은 사용자 재승인 없이는 금지한다.

## 허용 전이
- `Flow: FAST`이고 `Review Risk: LOW`이며 targeted verification이 충분한 최초 구현은 Coder가 risk evidence를 남기고 `kanban_complete`할 수 있다. 이 경우 review 전이가 없으므로 승인된 Coder override를 그대로 유지한다.
- Fast `REVIEW_REQUIRED`, 모든 Standard Flow, 모든 `CHANGES_REQUESTED` 재작업은 Coder가 모델 helper로 Reviewer DEFAULT 전환을 준비한 뒤 동일 Card/Workspace에서 `kanban_request_review`하고 멈춘다.
- Reviewer는 source를 수정하지 않고 정확히 하나만 호출한다: APPROVED=`kanban_complete`, 수정 가능한 P0/P1=`changes-return` 성공 후 `kanban_request_changes`, 판단 불가/외부 결정/반복 blocker=`kanban_block`.
- CHANGES_REQUESTED는 terminal 상태가 아니다. Card는 승인된 Coder 모델이 복원된 상태로 original coder에게 ready로 돌아가고 같은 Workspace에서 수정 후 반드시 다시 review를 요청한다.

## 금지 전이
- Standard Flow의 Coder self-approval 또는 LOW 근거 없는 Fast `kanban_complete`.
- review가 이미 시작된 Card에서 Coder가 LOW로 재분류해 reviewer를 우회하는 것.
- Reviewer DEFAULT 전환 없이 `kanban_request_review`.
- Coder 승인 모델 복원 없이 `kanban_request_changes`.
- 구현 완료 후 review 대용 `kanban_block`, 새 review card 생성.
- Reviewer source 수정, P0/P1을 둔 APPROVED, 수정 가능한 finding을 BLOCKED로 종료.
- Reviewer를 PREMIUM으로 자동 승격하거나 Coder가 스스로 모델을 변경하는 것.
- Kanban task를 재개하기 위해 수동 `hermes --resume`으로 worker를 대체하는 것.

동일 중요 blocker가 3 review cycle 지속되면 Reviewer가 `kind=needs_input`으로 human escalation한다. 정상 완료는 `workspace remains + no commit/push`이며 cleanup하지 않는다.

상세 risk metadata/상태 전이는 `references/review-protocol.md`를 읽는다.
