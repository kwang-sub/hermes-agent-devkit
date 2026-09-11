---
name: dev-workspace-dispatch
description: 승인된 구현 계획·API 규격·workspace·branch·Coder 모델과 project pattern/capability 계약을 최초 등록 알림과 함께 Kanban으로 인계한다.
version: 0.12.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, git, workspace, branch, kanban, dispatch, orchestrator, capability, preflight, notification, registration, model, api, spec, performance]
    related_skills: [dev-project-bootstrap, dev-project-pattern, dev-breakdown, dev-api-spec, dev-skill-preflight, dev-workflow-orchestrate, dev-flow-model-policy]
    requires_tools: [terminal, skill_view, kanban_create, kanban_show, kanban_unblock, clarify]
---

# dev-workspace-dispatch

사용자 승인까지 완료된 READY 구현 계획을 승인된 Git workspace/branch 및 **Coder 모델 snapshot**과 함께 Kanban 작업으로 인계한다. 이 Skill이 신규 Dispatch의 표준이다.

## 1. 진입 조건
- Plan 승인 완료
- 승인 이후 요구사항 변경 작업이면 Requirement Delta 승인 완료
- `API Spec Gate: REQUIRED`이면 `API Spec Status: APPROVED` 및 승인된 Markdown snapshot 확보
- `API Spec Gate: NOT_REQUIRED`이면 Mode가 `SOURCE_SYNC | AUDIT | NOT_REQUIRED` 중 하나임을 확인
- workspace/current 또는 create branch 승인 완료
- 기존 변경이 있을 수 있는 workspace라면 reset/restore/stash 없이 전부 보존할지 승인 완료
- Coder Model Tier(DEFAULT|PREMIUM) 승인 완료
- 승인 Tier를 `flow_model_policy.py resolve`로 해석한 `MODEL/PROVIDER` snapshot 확보
- `.hermes/project.yaml` managed metadata 존재

Reviewer는 별도 모델 승인을 받지 않고 항상 Reviewer profile DEFAULT를 사용한다.

## 2. 대형 Workspace Fast Path

사용자가 기존 변경 전체 보존을 이미 승인한 경우:

```text
prepare_dispatch.py --confirmed-dirty
→ repository/workspace/branch/Base SHA/Board만 검증
→ repository-wide dirty/EOL/untracked 분류를 **생략**
→ WORKSPACE_CHANGE_SCAN_MODE=skipped-approved-preservation
→ *_COUNT=-1, WORKSPACE_*_DIRTY=unknown
```

`-1/unknown`은 not-scanned 의미다. 기존 변경 보존 승인이 없는 경우에만 helper가 batch scan을 수행한다.

```text
git diff --name-only -z HEAD
git diff --name-only -z --ignore-cr-at-eol HEAD
git ls-files -z --others --exclude-standard
```

파일별 `git diff --quiet` 반복 호출은 금지한다.

## 3. Helper 실행

현재 branch:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/prepare_dispatch.py" \
  --task-key "<TASK-KEY>" \
  --workspace "<APPROVED_WORKSPACE>" \
  --branch-mode current \
  [--confirmed-dirty]
```

새 branch:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/prepare_dispatch.py" \
  --task-key "<TASK-KEY>" \
  --workspace "<APPROVED_WORKSPACE>" \
  --branch-mode create \
  --branch "feature/<TASK-KEY>" \
  [--confirmed-dirty]
```

Helper 출력의 `BOARD`는 `.hermes/project.yaml`의 `kanban.board`이며 유일한 board source다. `HERMES_KANBAN_BOARD`나 current/default board fallback은 사용하지 않는다.

모델은 승인 직후 정확히 1회 해석한다.

```bash
python3 /opt/data/shared/scripts/flow_model_policy.py resolve --tier "<DEFAULT|PREMIUM>"
```

`MODEL_TIER`, `MODEL`, `PROVIDER`를 immutable snapshot으로 사용한다.

## 4. Skill Preflight

`skill_view("dev-skill-preflight")` 후 Coder/Reviewer 공통 사용 가능 skill만 pin한다.

```text
VALIDATED_SKILLS → kanban_create.skills
REJECTED_SKILLS → body 기록만 하고 pin 금지
```

API Task의 `Applicable Skills`에 `dev-api-spec`이 있으면 Coder/Reviewer가 동일 Markdown contract를 볼 수 있도록 공통 pin 대상으로 검증한다. `dev-api-contract`, `dev-api-docs`도 계획에 필요한 경우 같은 방식으로 검증한다.

`dev-flow-model-policy`는 runtime pin 필수다. preflight 실패 시 dispatch하지 않는다.

## 5. Kanban 생성·알림 Gate 단일 경로

Task는 알림 Gate가 완료되기 전 worker가 가져가지 못하도록 **처음부터 `blocked` 상태로 생성**한다.

```text
prepare_dispatch.py 정확히 한 번
→ dev-skill-preflight
→ approved API Spec contract 확인 (REQUIRED일 때)
→ approved model snapshot 확인
→ kanban_create(
     board=BOARD,
     initial_status="blocked",
     model=MODEL,
     provider=PROVIDER,
     skills=[..., dev-flow-model-policy],
     ...
   ) tool 정확히 1회
→ kanban_show(board=BOARD, task_id=<CREATED_TASK_ID>) tool 정확히 1회
→ 등록 read-back 계약 검증
→ subscribe_notification.py --board BOARD --task-id <CREATED_TASK_ID> 정확히 1회
→ NOTIFY_STATUS=subscribed + NOTIFY_VERIFIED=true + NOTIFY_REGISTRATION_EVENT=queued
   또는 NOTIFY_STATUS=disabled
→ kanban_unblock(board=BOARD, task_id=<CREATED_TASK_ID>) tool 정확히 1회
→ ready 전환 후 worker dispatch
```

### 최초 등록 알림

알림이 활성화된 환경에서는 `subscribe_notification.py`가 다음을 한 transaction flow로 보장한다.

```text
task read-back
→ notify-subscribe
→ notify-list 검증
→ 구독 cursor 확정
→ `registered` task_event enqueue
→ NOTIFY_REGISTRATION_EVENT=queued
```

Hermes 새 subscription은 생성 시점의 최신 `task_events.id`를 cursor로 잡으므로, `registered` event는 **구독이 확인된 뒤에** 생성한다. 그래야 최초 등록 알림이 과거 이벤트로 간주되어 누락되지 않는다.

Gateway notifier patch는 `registered`를 감시 대상 kind에 포함하고 Discord에서는 다음 의미로 표시한다.

```text
🆕 작업 등록
상태 REGISTERED
```

등록 event는 Task별 1회만 enqueue하는 idempotent 계약이다. transient 재시도 때문에 같은 카드의 등록 알림을 중복 생성하지 않는다.

`kanban_show` 성공 전에는 알림 helper를 실행하지 않는다. 알림 활성 환경에서 다음 중 하나라도 발생하면 **절대 unblock하지 않는다**.

```text
helper exit != 0
NOTIFY_STATUS=failed
NOTIFY_VERIFIED != true
NOTIFY_REGISTRATION_EVENT != queued
```

Task는 blocked 상태로 남겨 수동 점검 후 재시도한다. 알림이 명시적으로 비활성화된 경우(`NOTIFY_STATUS=disabled`)만 구독/등록 알림 없이 unblock을 허용한다.

호출 횟수 계약:

```text
kanban_create tool 정확히 1회
kanban_show tool 정확히 1회
subscribe_notification.py 정확히 1회
kanban_unblock tool 정확히 1회 (Gate 성공 또는 알림 disabled일 때만)
```

금지:

```text
board 인자 생략
HERMES_KANBAN_BOARD fallback
default/current board fallback
알림 실패를 warning으로 무시하고 unblock
등록 알림 enqueue 전에 ready/running dispatch 허용
Coder 모델 승인 없이 create/unblock
Requirement Delta가 필요한 작업을 승인 없이 create/unblock
API Spec Gate가 REQUIRED인데 APPROVED 없이 create/unblock
승인 뒤 ENV를 다시 resolve하여 model 변경
hermes kanban --board <board> create --help
hermes project list / --help
Kanban body 임시 파일
CLI body-file 지원 여부 탐색
CLI fallback을 탐색하지 않고 BLOCK
```

`kanban_show`에서 최소 다음을 검증한다.

```text
board == BOARD
workspace == dir:<APPROVED_WORKSPACE>
assignee == profiles.coder
reviewer == profiles.reviewer
task.skills == VALIDATED_SKILLS (+ dev-flow-model-policy)
status == blocked
model_override == MODEL
provider_override == PROVIDER
```

Task body 모델 계약:

```text
Model Policy:
- Coder Model Tier: MODEL_TIER
- Coder Model: MODEL
- Coder Provider: PROVIDER
- Reviewer Model: DEFAULT
- Model Escalation: REQUIRE_REAPPROVAL
```

하나라도 불일치하면 unblock 금지다.

## 6. Workspace / Model / API Spec Contract

Task body에는 다음을 남긴다.

```text
- Kanban board: <BOARD>
- Workspace: <WORKSPACE_PATH>
- Branch mode: current | create
- Expected branch: <BRANCH>
- Base branch: <BASE_BRANCH>
- Base SHA: <BASE_SHA>
- Existing changes preservation approved: true | false
- Workspace change scan mode: full | skipped-approved-preservation
- Effective project changes at dispatch: <count | unknown>
- EOL-only changes at dispatch: <count | unknown>
- Hermes managed files at dispatch: <count | unknown>

API Specification:
- API Spec Mode: DESIGN_FIRST | SOURCE_SYNC | AUDIT | NOT_REQUIRED
- API Spec Gate: REQUIRED | NOT_REQUIRED
- API Spec Status: APPROVED | DRAFT | NOT_REQUIRED
- API Spec Path: <path | none>
- API Spec Source: DESIGN | APPLICATION_SOURCE | MIGRATED_SPEC | none
- API Spec Snapshot: <approved Markdown body or DRAFT/source-sync evidence when applicable>

Model Policy:
- Coder Model Tier: <DEFAULT|PREMIUM>
- Coder Model: <MODEL>
- Coder Provider: <PROVIDER>
- Reviewer Model: DEFAULT
- Model Escalation: REQUIRE_REAPPROVAL
```

`DESIGN_FIRST`에서는 `API Spec Status: APPROVED`와 승인 snapshot이 Coder/Reviewer의 normative contract다. Coder는 production API를 변경하기 전에 승인 snapshot을 repository Markdown에 materialize/update하고 `dev-api-spec` 계약을 따른다.

`SOURCE_SYNC`에서는 `API Spec Status: DRAFT`, `API Spec Source: APPLICATION_SOURCE`가 정상이며 Coder는 bounded source evidence로 Markdown을 생성/갱신한다. 자동 APPROVED 승격은 금지한다.

Fast Path에서는 모든 기존 변경 보존 승인이 baseline 계약이다. Coder는 자신의 실제 변경 scope만 별도로 추적한다.

## 7. Coder↔Reviewer 모델 전이

```text
Coder run
→ Task override = approved MODEL/PROVIDER
→ Reviewer handoff 직전 flow_model_policy.py review-enter
→ override clear
→ reviewer profile DEFAULT

Reviewer CHANGES_REQUESTED
→ flow_model_policy.py changes-return
→ Task body snapshot의 approved MODEL/PROVIDER 복원
→ original coder 재실행
```

동일 승인 모델 retry는 재승인하지 않는다. 모델/Provider 변경 또는 PREMIUM escalation은 사용자 재승인 대상이다.

## 8. 성능 불변식

- Workspace 승인 전 working-tree 전체 scan 금지.
- `--confirmed-dirty` 이후 exact count 복구를 위한 재scan 금지.
- API SOURCE_SYNC/AUDIT도 Task/도메인 범위의 bounded scan을 기본으로 함.
- Coder/Reviewer는 실제 changed scope만 검증.
- large/binary file을 임의 MB 기준으로 제외하지 않음.
- 모델 snapshot은 승인 시 1회 resolve.

## 9. 회귀 검증

```bash
python3 scripts/check_skill_contract.py
python3 scripts/check_api_spec_contract.py
python3 custom-skills/orchestrator/dev-workspace-dispatch/tests/test_prepare_dispatch.py
python3 custom-skills/orchestrator/dev-workspace-dispatch/tests/test_subscribe_notification.py
python3 shared/scripts/test_kanban_registration_event.py
python3 shared/scripts/test_flow_model_policy.py
```

성능 관찰용 full scan 출력:

```text
GIT_TRACKED_SCAN_SECONDS
GIT_EFFECTIVE_SCAN_SECONDS
GIT_UNTRACKED_SCAN_SECONDS
CLASSIFICATION_SECONDS
WORKSPACE_CLASSIFICATION_TOTAL_SECONDS
```
