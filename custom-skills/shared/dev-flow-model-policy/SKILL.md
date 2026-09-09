---
name: dev-flow-model-policy
description: Standard/Fast Flow에서 승인된 Coder 모델을 Task에 고정하고 Reviewer는 DEFAULT를 사용하도록 Coder↔Reviewer 전이 시 모델 override를 관리하는 공통 정책.
version: 0.4.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, flow, model, approval, coder, reviewer, kanban]
    related_skills: [dev-fast-flow, dev-workflow-orchestrate, dev-workspace-dispatch, dev-implement-plan, dev-code-review, dev-review-cycle]
    requires_tools: [kanban_show, kanban_request_review, kanban_request_changes, kanban_block]
---

# dev-flow-model-policy

이 Skill은 구현 내용이 아니라 **Flow 실행 모델 계약**만 담당한다.

## 1. 논리 모델 등급

Flow는 실제 모델명을 정책에 하드코딩하지 않고 `DEFAULT | PREMIUM` 두 등급을 사용한다.

```text
HERMES_FLOW_MODEL_DEFAULT_PROVIDER
HERMES_FLOW_MODEL_DEFAULT
HERMES_FLOW_MODEL_PREMIUM_PROVIDER
HERMES_FLOW_MODEL_PREMIUM
```

현재 기본값은 다음과 같지만 세대 교체 시 ENV만 바꾼다.

```text
DEFAULT = openai-codex / gpt-5.6-terra
PREMIUM = openai-codex / gpt-6-astra
```

## 2. 승인 불변식

- Coder 모델은 신규 Standard/Fast dispatch 전에 사용자가 명시적으로 승인한다.
- Reviewer는 별도 승인 없이 항상 Reviewer profile의 `DEFAULT`를 사용한다.
- PREMIUM 자동 escalation은 금지한다.
- 동일 승인 모델로 같은 Task를 retry할 때 재승인하지 않는다.
- ENV 변경은 이미 승인된 Task에 영향을 주지 않는다. Task body 또는 durable migration comment의 snapshot이 source of truth다.

신규 Task에는 다음 계약을 보존한다.

```text
Model Policy:
- Coder Model Tier: DEFAULT | PREMIUM
- Coder Model: <resolved model>
- Coder Provider: <resolved provider>
- Reviewer Model: DEFAULT
- Model Escalation: REQUIRE_REAPPROVAL
```

## 3. 기존 활성 Task 호환

정책 도입 전 활성 Task는 새 카드를 만들지 않고 Orchestrator/관리 경로에서 한 번만 migration한다.

```bash
python3 /opt/data/shared/scripts/flow_model_policy.py migrate-existing \
  --tier <DEFAULT|PREMIUM> \
  --lane <coder|reviewer> \
  --board <board> \
  --task-id <task>
```

`done`/`archived` Task는 migration하지 않는다. `MODEL_POLICY_SNAPSHOT_V1` durable comment가 승인 snapshot을 보존한다.

## 4. Coder 실행

Coder 시작 시 `kanban_show`의 `model_override/provider_override`가 승인 snapshot과 일치해야 한다. 불일치하면 구현하지 않고 block한다.

Fast LOW self-complete는 현재 Coder override를 유지한 채 `kanban_complete`한다.

### Reviewer handoff

Coder가 Reviewer에게 넘길 때 **Codex/native shell에서 `flow_model_policy.py review-enter`를 직접 실행하지 않는다.** `HERMES_KANBAN_TASK`, claim lock 같은 ownership env는 Codex shell에 의도적으로 노출되지 않기 때문이다.

대신 handoff evidence를 준비한 뒤 바로 claim-bound Hermes lifecycle 도구를 호출한다.

```text
kanban_request_review(summary=..., reviewer=<Reviewer Profile>, metadata=...)
```

DevKit runtime patch가 이 도구 내부에서 다음을 하나의 신뢰된 Worker context로 수행한다.

```text
승인 model policy 존재 확인
→ review-enter (Task override clear)
→ kanban request_review
→ lifecycle 실패 시 changes-return rollback
```

따라서 Worker가 별도 shell helper로 모델 override를 먼저 변경하면 안 된다. `kanban_request_review`가 실패하면 도구가 rollback까지 시도한 오류를 반환하며, Coder는 임의 재호출/수동 env 주입 대신 해당 오류를 근거로 `kanban_block(kind=capability)`한다.

## 5. Reviewer 실행

Review run은 Task `model_override/provider_override`가 비어 있어야 하고 Reviewer profile의 DEFAULT를 사용한다.

APPROVED는 `kanban_complete`한다.

### CHANGES_REQUESTED

Reviewer가 Coder에게 돌려보낼 때도 **shell에서 `flow_model_policy.py changes-return`을 직접 실행하지 않는다.** 바로 claim-bound lifecycle 도구를 호출한다.

```text
kanban_request_changes(reason=...)
```

DevKit runtime patch가 내부에서 다음을 수행한다.

```text
승인 model policy 존재 확인
→ changes-return (승인 Coder snapshot 복원)
→ kanban request_changes
→ lifecycle 실패 시 review-enter rollback
```

실패하면 수동 model mutation이나 env 주입으로 우회하지 않고 capability blocker로 종료한다.

## 6. 전이 상태표

```text
Coder running
  model_override = approved Coder snapshot
    ↓ kanban_request_review 내부 review-enter
  model_override = none
    ↓ lifecycle 성공
Reviewer review/running
  model_override = none → Reviewer profile DEFAULT
    ↓ kanban_request_changes 내부 changes-return
  model_override = approved Coder snapshot
    ↓ lifecycle 성공
Coder ready/running
  model_override = approved Coder snapshot
```

Lifecycle 전이가 실패하면 같은 claim-bound tool handler가 바로 앞 model mutation을 반대로 실행해 원상복구한다.

## 7. Shell helper 사용 범위

`flow_model_policy.py`의 `resolve`, `apply`, `migrate-existing`는 Orchestrator/관리 경로에서 사용할 수 있다. `review-enter`, `changes-return`은 runtime lifecycle handler의 내부 구현용이다.

Coder/Reviewer Codex native shell에서 다음을 직접 실행하지 않는다.

```text
flow_model_policy.py review-enter
flow_model_policy.py changes-return
hermes kanban set-model ...
HERMES_KANBAN_TASK 수동 주입
HERMES_KANBAN_CLAIM_LOCK 수동 주입
```

## 8. 금지

- Reviewer를 PREMIUM으로 자동 승격
- Coder가 난이도를 이유로 스스로 PREMIUM 전환
- retry 때 ENV를 다시 해석해 기존 Task 모델 변경
- review 진입 후 Coder override 유지
- CHANGES_REQUESTED 반환 전 승인 Coder snapshot 복원 생략
- lifecycle 실패 후 다음 lane용 override 방치
- 승인 snapshot과 다른 model/provider로 set-model
- Codex shell에 Kanban ownership env 재노출
- pre-policy 활성 Task를 migration 없이 새 카드로 대체

## 9. Discord 표시

Discord 알림은 Task의 현재 override를 우선 표시한다.

- Coder 실행: 승인 provider/model
- Reviewer 단계 및 `review_requested`: `DEFAULT (profile)`
- `changes_requested`: 복원된 승인 Coder provider/model

알림 표시는 실행 계약을 바꾸지 않는다. source of truth는 Kanban Task override와 승인 snapshot이다.
