---
name: dev-flow-model-policy
description: Standard/Fast Flow에서 승인된 Coder 모델을 Task에 고정하고 Reviewer는 DEFAULT를 사용하도록 Coder↔Reviewer 전이 시 모델 override를 관리하는 공통 정책.
version: 0.3.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, flow, model, approval, coder, reviewer, kanban]
    related_skills: [dev-fast-flow, dev-workflow-orchestrate, dev-workspace-dispatch, dev-implement-plan, dev-code-review, dev-review-cycle]
    requires_tools: [terminal, kanban_show, kanban_request_review, kanban_request_changes, kanban_block]
---

# dev-flow-model-policy

이 Skill은 구현 내용이 아니라 **Flow 실행 모델 계약**만 담당한다.

## 1. 논리 모델 등급

Flow는 실제 모델명을 직접 정책으로 사용하지 않고 다음 두 등급만 사용한다.

```text
DEFAULT
PREMIUM
```

실제 provider/model은 승인 시점 환경 변수에서 해석한다.

```text
HERMES_FLOW_MODEL_DEFAULT_PROVIDER
HERMES_FLOW_MODEL_DEFAULT
HERMES_FLOW_MODEL_PREMIUM_PROVIDER
HERMES_FLOW_MODEL_PREMIUM
```

현재 DevKit 기본값은 다음과 같지만 세대 교체 시 ENV만 바꾼다.

```text
DEFAULT = openai-codex / gpt-5.6-terra
PREMIUM = openai-codex / gpt-6-astra
```

## 2. 승인 불변식

- Coder 모델은 신규 Standard/Fast dispatch 전에 사용자가 명시적으로 승인한다.
- Reviewer는 별도 승인 없이 항상 Reviewer profile의 `DEFAULT` 모델을 사용한다.
- Agent가 PREMIUM 사용을 추천할 수는 있지만 자동 escalation은 금지한다.
- Coder Model Tier/Provider/Model을 바꾸려면 사용자 재승인이 필요하다.
- 동일 승인 모델로 같은 Task를 retry하는 것은 재승인하지 않는다.
- ENV 변경은 이미 승인된 Task에 영향을 주지 않는다. Task body 또는 legacy migration comment에 저장된 snapshot을 사용한다.

신규 Task body에는 반드시 다음 계약이 있다.

```text
Model Policy:
- Coder Model Tier: DEFAULT | PREMIUM
- Coder Model: <resolved model>
- Coder Provider: <resolved provider>
- Reviewer Model: DEFAULT
- Model Escalation: REQUIRE_REAPPROVAL
```

## 3. 기존 활성 Task 호환

새 모델 정책 적용 전에 생성된 **활성 Task**는 새 카드를 만들 필요가 없다. 사용자가 Coder Model Tier를 승인하면 같은 Task에 snapshot을 이관한다.

```bash
python3 /opt/data/shared/scripts/flow_model_policy.py migrate-existing \
  --tier <DEFAULT|PREMIUM> \
  --lane <coder|reviewer> \
  --board <board> \
  --task-id <task>
```

성공 조건:

```text
STATUS=legacy-task-migrated
SNAPSHOT_SOURCE=durable-comment
```

이 helper는:

1. 기존 Task 상태를 확인한다.
2. 승인한 tier를 현재 ENV에서 정확히 한 번 resolve한다.
3. 현재 lane이 Coder면 승인 model/provider override를 적용하고, Reviewer면 override를 clear한다.
4. `MODEL_POLICY_SNAPSHOT_V1` marker가 포함된 durable Kanban comment에 승인 snapshot을 기록한다.
5. comment 기록 실패 시 기존 model/provider override로 rollback한다.

`done`/`archived` Task는 migration하지 않는다. 후속 작업이 필요하면 **정상 Standard/Fast 승인 게이트를 모두 통과한 후** 새 Task를 만든다.

**금지:** pre-policy Task라는 이유만으로 새 카드 생성을 강제하거나, `대체 카드 생성 승인`을 Plan/Workspace/Model 승인 대신 사용한다.

## 4. Coder 실행

Coder run 시작 시 `kanban_show` 결과의 `model_override/provider_override`가 승인 snapshot과 일치해야 한다. snapshot source는 다음 우선순위를 사용한다.

1. `MODEL_POLICY_SNAPSHOT_V1` durable comment의 최신 snapshot
2. 신규 Task body의 `Model Policy`

불일치하면 구현을 진행하지 않고 model contract mismatch로 `kanban_block`한다.

Coder가 Fast LOW로 직접 완료하는 경우 현재 override를 유지한 채 `kanban_complete`한다.

Coder가 Reviewer에게 넘기는 경우 `kanban_request_review` **직전** 다음 helper를 정확히 1회 실행한다.

```bash
python3 /opt/data/shared/scripts/flow_model_policy.py review-enter
```

성공 조건:

```text
STATUS=review-default-ready
```

그 다음 같은 turn에서 기존 review handoff 계약에 따라 `kanban_request_review`를 호출한다.

Helper 실패 시 Reviewer handoff를 진행하지 말고 `kanban_block(kind=capability)`한다.

### Review handoff 실패 복구

`review-enter`는 성공했지만 이어지는 `kanban_request_review`가 실패하면 Task는 아직 Coder lane에 있으므로 즉시 원래 승인 Coder snapshot을 복원한다.

```bash
python3 /opt/data/shared/scripts/flow_model_policy.py changes-return
```

복원 성공(`STATUS=coder-model-restored`) 후 실패 원인을 처리한다. 모델을 복원하지 않은 채 Coder Task를 retry/종료하지 않는다.

복원 helper까지 실패하면 `kanban_block(kind=capability)`하고 다음 dispatch를 막는다.

## 5. Reviewer 실행

Review run은 Task `model_override/provider_override`가 비어 있어야 하며 Reviewer profile의 DEFAULT를 사용한다.

Reviewer APPROVED는 그대로 `kanban_complete`한다.

Reviewer가 `CHANGES_REQUESTED`를 반환하는 경우 `kanban_request_changes` **직전** 다음 helper를 정확히 1회 실행한다.

```bash
python3 /opt/data/shared/scripts/flow_model_policy.py changes-return
```

Helper는 ENV를 다시 해석하지 않고 Task body 또는 legacy durable comment의 승인 snapshot을 읽어 원래 Coder provider/model을 복원한다.

성공 조건:

```text
STATUS=coder-model-restored
```

그 다음 `kanban_request_changes`를 호출한다.

Helper 실패 시 Coder에게 잘못된 모델로 돌아갈 수 있으므로 `kanban_request_changes`를 호출하지 말고 `kanban_block(kind=capability)`한다.

### Changes handoff 실패 복구

`changes-return`은 성공했지만 이어지는 `kanban_request_changes`가 실패하면 Task는 아직 Reviewer lane에 있으므로 Reviewer DEFAULT 상태로 즉시 되돌린다.

```bash
python3 /opt/data/shared/scripts/flow_model_policy.py review-enter
```

복구 성공(`STATUS=review-default-ready`) 후 실패 원인을 처리한다. Coder 모델 override를 남긴 채 Reviewer Task를 retry/종료하지 않는다.

복구 helper까지 실패하면 `kanban_block(kind=capability)`하고 다음 dispatch를 막는다.

## 6. 전이 상태표

```text
Coder running
  model_override = approved Coder snapshot
    ↓ review-enter
  model_override = none
    ↓ kanban_request_review 성공
Reviewer review/running
  model_override = none → Reviewer profile DEFAULT
    ↓ changes-return
  model_override = approved Coder snapshot
    ↓ kanban_request_changes 성공
Coder ready/running
  model_override = approved Coder snapshot
```

Lifecycle 전이가 실패하면 바로 앞 model mutation을 반대로 실행해 원상복구한다.

## 7. 금지

```text
Reviewer를 PREMIUM으로 자동 승격
Coder가 요구사항 난이도를 이유로 스스로 PREMIUM 전환
retry 때 ENV를 다시 해석해 기존 Task 모델 변경
review 진입 후 Coder PREMIUM override 유지
CHANGES_REQUESTED 반환 전 Coder 승인 모델 복원 생략
lifecycle 전이 실패 후 다음 lane용 model override 방치
승인 snapshot과 다른 model/provider로 set-model
pre-policy 활성 Task를 migration 없이 새 카드로 대체
대체 카드 생성 승인으로 Standard Flow 승인 Gate 생략
```

## 8. Discord 표시

Discord Kanban 알림은 Task의 현재 `model_override/provider_override`를 우선 표시한다.

- Coder 실행/완료: 승인된 실제 provider/model
- Reviewer 단계: `DEFAULT (profile)`
- `review_requested` 알림: Reviewer가 다음 실행 주체이므로 `DEFAULT (profile)`
- `changes_requested` 알림: Coder가 다음 실행 주체이므로 복원된 승인 provider/model

알림 표시는 실행 계약을 바꾸지 않으며, 실행 모델의 source of truth는 Kanban Task override와 승인 snapshot이다.
