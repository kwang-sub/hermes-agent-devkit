---
name: dev-workspace-dispatch
description: 승인된 단일 Work Unit 계획·API 규격·Infrastructure Desired State·workspace·branch·Coder 모델과 capability 계약을 최초 등록 알림과 함께 Kanban으로 인계한다.
version: 0.15.1
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, git, workspace, branch, kanban, dispatch, orchestrator, work-unit, capability, infrastructure, desired-state, preflight, notification, registration, model, api, spec, performance]
    related_skills: [dev-project-bootstrap, dev-project-pattern, dev-breakdown, dev-api-spec, dev-infrastructure, dev-skill-preflight, dev-workflow-orchestrate, dev-flow-model-policy]
    requires_tools: [terminal, skill_view, kanban_create, kanban_show, kanban_unblock, clarify]
---

# dev-workspace-dispatch

사용자 승인까지 완료된 READY **단일 Work Unit** 계획을 승인된 Git workspace/branch 및 Coder model snapshot과 함께 Kanban으로 인계한다. 이 Skill이 신규 Standard Dispatch의 표준이다.

`/opt/data/shared/references/standard-work-unit-rules.md`를 적용한다.

## 1. 진입 조건
- Plan 승인 완료
- `Work Unit Class`가 `DESIGN | IMPLEMENTATION | MIGRATION | REFACTOR | AUDIT` 중 하나
- `Work Unit Boundary`와 Current/Follow-up/Excluded scope가 승인 Plan에 존재
- `SPLIT_REQUIRED`이면 현재 Plan의 Implementation Tasks/AC가 **Current Deliverable만** 포함하고 Follow-up scope를 구현 범위에서 제외
- 승인 이후 요구사항 변경 작업이면 Requirement Delta 승인 완료
- `API Spec Gate: REQUIRED`이면 `API Spec Status: APPROVED` 및 승인된 Markdown snapshot 확보
- `API Spec Gate: NOT_REQUIRED`이면 Mode가 `SOURCE_SYNC | AUDIT | NOT_REQUIRED` 중 하나임을 확인
- `Infrastructure Impact: YES`이면 승인된 Infrastructure Desired State snapshot 확보
- workspace/current 또는 create branch 승인 완료
- 기존 변경이 있을 수 있는 workspace라면 reset/restore/stash 없이 전부 보존할지 승인 완료
- Coder Model Tier(DEFAULT|PREMIUM) 승인 완료
- 승인 Tier를 `flow_model_policy.py resolve`로 해석한 `MODEL/PROVIDER` snapshot 확보
- Primary Repository의 `.hermes/project.yaml` managed metadata 존재

Reviewer는 별도 모델 승인을 받지 않고 항상 Reviewer profile DEFAULT를 사용한다.

`SPLIT_REQUIRED`의 Follow-up Work Unit은 Task metadata로만 보존한다. Dispatch가 같은 승인으로 후속 Task를 자동 생성하거나 pin/dispatch하면 안 된다.

## 2. Project / Workspace 분리 계약

```text
Project = Primary Repository
  /workspace/chagok
  └─ .hermes/project.yaml  ← canonical metadata

Workspace = Primary 또는 linked worktree
  /workspace/chagok
  /workspace/.worktrees/chagok/investment-data-model
```

`prepare_dispatch.py`는 승인된 Workspace에서 `git worktree list --porcelain`로 Primary Worktree를 해석하고 Primary Repository의 `.hermes/project.yaml`만 읽는다. linked worktree마다 별도 Project/Board/Infrastructure metadata를 생성하거나 요구하지 않는다.

Helper 경계:

```text
PROJECT_REPOSITORY=<primary worktree>
PROJECT_METADATA_FILE=<primary>/.hermes/project.yaml
PROJECT_CONTEXT_SOURCE=primary-worktree
WORKSPACE_PATH=<approved primary or linked worktree>
LINKED_WORKTREE=true | false
```

linked worktree의 stale `.hermes/project.yaml`은 `WORKSPACE_METADATA_IGNORED`로 처리한다. Git ownership이 달라도 승인 Workspace와 Primary Repository만 process-local `safe.directory`로 신뢰하며 global safe.directory 변경은 금지한다.

## 3. 대형 Workspace Fast Path

사용자가 기존 변경 전체 보존을 이미 승인한 경우:

```text
prepare_dispatch.py --confirmed-dirty
→ repository/workspace/branch/Base SHA/Board만 검증
→ repository-wide dirty/EOL/untracked 분류를 **생략**
→ WORKSPACE_CHANGE_SCAN_MODE=skipped-approved-preservation
→ *_COUNT=-1, WORKSPACE_*_DIRTY=unknown
```

기존 변경 보존 승인이 없는 경우에만 batch scan을 수행한다.

```text
git diff --name-only -z HEAD
git diff --name-only -z --ignore-cr-at-eol HEAD
git ls-files -z --others --exclude-standard
```

파일별 `git diff --quiet` 반복 호출은 금지한다.

## 4. Workspace Helper 실행

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

Helper 출력의 `BOARD`는 Primary Repository `.hermes/project.yaml`의 `kanban.board`이며 유일한 board source다.

모델은 승인 직후 정확히 1회 해석한다.

```bash
python3 /opt/data/shared/scripts/flow_model_policy.py resolve --tier "<DEFAULT|PREMIUM>"
```

`MODEL_TIER`, `MODEL`, `PROVIDER`를 immutable snapshot으로 사용한다.

## 5. Infrastructure Desired State Persistence

`Infrastructure Impact: YES`이면 `prepare_dispatch.py` 성공 후 Kanban 생성 전에 승인된 Desired State를 Primary metadata에 정확히 한 번 영속화한다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/persist_infrastructure_desired.py" \
  --repo "<PROJECT_REPOSITORY>" \
  --application-runtime "<LOCAL_HOST|NETWORK_HOST|CONTAINER>" \
  [--application-host "<host>"] \
  --database-runtime "<LOCAL_HOST|NETWORK_HOST|CONTAINER>" \
  [--database-host "<host>"] \
  [--database-port "<port>"] \
  --database-platform "<NATIVE|SUPABASE>" \
  --database-vendor "<vendor>"
```

`INFRASTRUCTURE_DESIRED_PERSIST=updated|unchanged`는 둘 다 성공이다. Desired State 영속화를 Observed State 변경으로 간주하지 않는다.

## 6. Skill Preflight

`skill_view("dev-skill-preflight")` 후 Coder/Reviewer 공통 사용 가능 skill만 pin한다.

```text
VALIDATED_SKILLS → kanban_create.skills
REJECTED_SKILLS → body 기록만 하고 pin 금지
```

`capability-lifecycle.json`의 `strict_pin=true` capability가 Current Work Unit의 `Applicable Skills`에 있으면 Coder/Reviewer 모두 `--strict` preflight를 통과해야 한다. **Follow-up Work Unit에만 필요한 capability는 현재 Task의 Applicable Skills/pinned skills에 넣지 않는다.**

예:

```text
Data DESIGN + Follow-up MIGRATION
현재 Task pin: dev-data-feature (+ 필요한 design support)
현재 Task pin 금지: follow-up 전용 dev-db-migration
```

`dev-flow-model-policy`는 runtime pin 필수다. preflight 실패 시 dispatch하지 않는다.

## 7. Kanban 생성·알림 Gate 단일 경로

```text
prepare_dispatch.py 정확히 한 번
→ Work Unit Contract 확인
→ Infrastructure Impact=YES이면 approved Desired persist 정확히 한 번
→ dev-skill-preflight
→ approved API Spec contract 확인 (REQUIRED일 때)
→ approved model snapshot 확인
→ kanban_create(board=BOARD, initial_status="blocked", model=MODEL, provider=PROVIDER, skills=VALIDATED_SKILLS + dev-flow-model-policy)
→ kanban_show 정확히 1회
→ 등록 read-back 계약 검증
→ subscribe_notification.py 정확히 1회
→ NOTIFY_STATUS=subscribed + NOTIFY_VERIFIED=true + NOTIFY_REGISTRATION_EVENT=queued
   또는 NOTIFY_STATUS=disabled
→ kanban_unblock 정확히 1회
→ ready 전환 후 worker dispatch
```

### 최초 등록 알림

알림이 활성화된 환경에서는 `kanban_show` read-back 이후 subscription을 검증하고, 그 다음 `registered` task event를 enqueue해서 **최초 등록 알림**이 subscription cursor보다 과거 event로 사라지지 않게 한다.

```text
task read-back
→ notify-subscribe
→ subscription verified
→ registered task_event enqueue
→ NOTIFY_REGISTRATION_EVENT=queued
```

`registered` event는 Task별 1회만 enqueue하는 idempotent 계약이다. 알림 활성 환경에서 helper 실패/검증 실패/등록 event 누락/전달 ACK timeout 시 절대 unblock하지 않는다.

알림 Gate 실패 시 Task는 이미 `initial_status="blocked"`이므로 **그 상태를 그대로 유지한다.** 실패를 기록하기 위해 `kanban_block`을 다시 호출하지 않는다. 특히 `goal_mode` Task에 임의의 block `kind`를 추론해 전달하는 것은 금지한다. 필요하면 durable comment로 실패 원인과 `registration_event_id`, 관측된 cursor를 남기고 종료한다. 복구 후에는 기존 Task를 기준으로 별도 승인된 resume 경로를 사용하며, 실패한 Standard Dispatch 안에서 `subscribe_notification.py`나 `prepare_dispatch.py`를 재실행하지 않는다.

호출 횟수 계약:

```text
prepare_dispatch.py 정확히 1회
persist_infrastructure_desired.py 0회 또는 정확히 1회
kanban_create tool 정확히 1회
kanban_show tool 정확히 1회
subscribe_notification.py 정확히 1회
kanban_unblock tool 정확히 1회 (Gate 성공 또는 알림 disabled일 때만)
```

금지:

```text
Work Unit Contract 없는 Standard Task dispatch
SPLIT_REQUIRED인데 Follow-up scope를 같은 Task에 포함
Follow-up Work Unit 자동 Kanban 생성/dispatch
Follow-up capability를 현재 Applicable Skills에 자동 추가
board 인자 생략
HERMES_KANBAN_BOARD fallback
default/current board fallback
Infrastructure Impact=YES인데 Desired State persistence 생략
Plan에 없는 Infrastructure Desired 값을 dispatch 시 재추론
Infrastructure metadata에 credential/secret 기록
알림 실패를 warning으로 무시하고 unblock
알림 Gate 실패 후 이미 blocked인 Task에 kanban_block 재호출
Coder 모델 승인 없이 create/unblock
Requirement Delta가 필요한 작업을 승인 없이 create/unblock
API Spec Gate가 REQUIRED인데 APPROVED 없이 create/unblock
승인 뒤 ENV를 다시 resolve하여 model 변경
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

## 8. Task Body Contract

```text
Work Unit:
- Work Unit Class: DESIGN | IMPLEMENTATION | MIGRATION | REFACTOR | AUDIT
- Work Unit Boundary: SINGLE_UNIT | SPLIT_REQUIRED
- Current Deliverable: <...>
- Follow-up Required: YES | NO
- Follow-up Work Unit: <... | NONE>
- Follow-up Input: <... | NONE>
- Excluded Follow-up Scope: <... | NONE>

Workspace:
- Kanban board: <BOARD>
- Workspace: <WORKSPACE_PATH>
- Branch mode: current | create
- Expected branch: <BRANCH>
- Base branch: <BASE_BRANCH>
- Base SHA: <BASE_SHA>
- Existing changes preservation approved: true | false
- Workspace change scan mode: full | skipped-approved-preservation

API Specification:
- API Spec Mode: DESIGN_FIRST | SOURCE_SYNC | AUDIT | NOT_REQUIRED
- API Spec Gate: REQUIRED | NOT_REQUIRED
- API Spec Status: APPROVED | DRAFT | NOT_REQUIRED
- API Spec Path: <path | none>
- API Spec Source: DESIGN | APPLICATION_SOURCE | MIGRATED_SPEC | none

Infrastructure:
- Infrastructure Impact: YES | NO
- Desired Persist: UPDATED | UNCHANGED | NOT_REQUIRED
- Application Runtime: <...>
- Application Host: <... | unknown>
- Database Runtime: <...>
- Database Host: <... | unknown>
- Database Port: <... | unknown>
- Database Platform: <...>
- Database Vendor: <...>

Model Policy:
- Coder Model Tier: <DEFAULT|PREMIUM>
- Coder Model: <MODEL>
- Coder Provider: <PROVIDER>
- Reviewer Model: DEFAULT
- Model Escalation: REQUIRE_REAPPROVAL
```

Data DESIGN Task에서 `Follow-up Work Unit: MIGRATION`이 있어도 Coder는 현재 Task에서 migration을 시작하지 않는다. Follow-up metadata는 다음 Standard Flow를 위한 안내다.

## 9. Coder↔Reviewer 모델 전이

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

## 10. 성능 불변식

- Workspace 승인 전 working-tree 전체 scan 금지.
- `--confirmed-dirty` 이후 exact count 복구를 위한 재scan 금지.
- API SOURCE_SYNC/AUDIT도 Task/도메인 범위 bounded scan.
- Infrastructure detector도 bounded evidence만 사용.
- Coder/Reviewer는 실제 changed scope만 검증.
- 모델 snapshot은 승인 시 1회 resolve.

## 11. 회귀 검증

```bash
python3 scripts/check_skill_contract.py
python3 scripts/check_api_spec_contract.py
python3 scripts/check_infrastructure_capability_contract.py
python3 scripts/check_standard_work_unit_contract.py
python3 custom-skills/orchestrator/dev-workspace-dispatch/tests/test_prepare_dispatch.py
python3 custom-skills/orchestrator/dev-workspace-dispatch/tests/test_persist_infrastructure_desired.py
python3 custom-skills/orchestrator/dev-workspace-dispatch/tests/test_subscribe_notification.py
python3 shared/scripts/test_kanban_registration_event.py
python3 shared/scripts/test_flow_model_policy.py
```
