---
name: dev-workspace-dispatch
description: 승인된 구현 계획·API 규격·Infrastructure Desired State·workspace·branch·Coder 모델을 Primary Project context와 함께 Kanban으로 인계한다.
version: 0.14.4
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, git, workspace, branch, kanban, dispatch, orchestrator, capability, infrastructure, desired-state, preflight, notification, registration, model, api, spec, performance]
    related_skills: [dev-project-bootstrap, dev-project-pattern, dev-breakdown, dev-api-spec, dev-infrastructure, dev-skill-preflight, dev-workflow-orchestrate, dev-flow-model-policy]
    requires_tools: [terminal, skill_view, kanban_create, kanban_show, kanban_unblock, clarify]
---

# dev-workspace-dispatch

사용자 승인까지 완료된 READY Plan을 승인된 Workspace/Branch와 Coder model snapshot으로 Kanban에 인계한다. **이 Skill이 신규 Dispatch의 표준이다.**

## 진입 조건

- Plan 승인 완료
- Requirement Delta가 있으면 승인 완료
- `API Spec Gate: REQUIRED`이면 `API Spec Status: APPROVED`
- `Infrastructure Impact: YES`이면 승인된 Desired State snapshot 확보
- Workspace / Branch / 기존 변경 보존 승인 완료
- **Coder Model Tier(DEFAULT|PREMIUM) 승인 완료**
- Primary Repository의 managed `.hermes/project.yaml` 존재

**Reviewer profile DEFAULT**는 별도 모델 승인 없이 사용한다.

## Project / Workspace 경계

```text
Project = Primary Repository
  /workspace/chagok/.hermes/project.yaml

Workspace = Primary 또는 linked worktree
  /workspace/chagok
  /workspace/.worktrees/chagok/<task>
```

`prepare_dispatch.py`는 `git worktree list --porcelain`로 Primary Repository를 해석하고 Primary의 metadata만 사용한다.

```text
PROJECT_REPOSITORY=<primary>
PROJECT_METADATA_FILE=<primary>/.hermes/project.yaml
PROJECT_CONTEXT_SOURCE=primary-worktree
WORKSPACE_PATH=<approved workspace>
LINKED_WORKTREE=true | false
```

linked worktree의 stale `.hermes/project.yaml`은 `WORKSPACE_METADATA_IGNORED`로 보고하고 사용하지 않는다. 승인 Workspace와 Primary만 process-local `safe.directory`로 신뢰하며 global safe.directory를 수정하지 않는다.

## Workspace 준비

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

기존 변경 전체 보존을 이미 승인한 경우 `--confirmed-dirty`를 사용한다.

```text
→ repository-wide dirty/EOL/untracked 분류를 **생략**
→ WORKSPACE_CHANGE_SCAN_MODE=skipped-approved-preservation
→ *_COUNT=-1
→ WORKSPACE_*_DIRTY=unknown
```

`-1/unknown`은 not-scanned다. 보존 승인이 없는 경우에만 batch scan을 수행한다.

```text
git diff --name-only -z HEAD
git diff --name-only -z --ignore-cr-at-eol HEAD
git ls-files -z --others --exclude-standard
WORKSPACE_CLASSIFICATION_TOTAL_SECONDS
```

파일별 반복 `git diff --quiet`는 사용하지 않는다.

`BOARD`는 Primary metadata의 `kanban.board`가 유일한 source이며 `HERMES_KANBAN_BOARD` 또는 default/current board fallback을 사용하지 않는다.

## Infrastructure Desired State persistence

`Infrastructure Impact: YES`이면 `prepare_dispatch.py`가 검증한 `PROJECT_REPOSITORY`에 승인 Desired State를 정확히 한 번 저장한다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/persist_infrastructure_desired.py" \
  --repo "<PROJECT_REPOSITORY>" \
  --application-runtime "<LOCAL_HOST|NETWORK_HOST|CONTAINER>" \
  --application-host "<host|unknown>" \
  --application-port "<port|unknown>" \
  --database-runtime "<LOCAL_HOST|NETWORK_HOST|CONTAINER>" \
  --database-host "<host|unknown>" \
  --database-port "<port|unknown>" \
  --database-platform "<NATIVE|SUPABASE>" \
  --database-vendor "<postgresql|mysql|mariadb|mssql|oracle|unknown>"
```

```text
Plan Approval
→ Workspace / Primary Repository 검증
→ Approved Desired State atomic persist
→ INFRASTRUCTURE_DESIRED_PERSISTENCE=updated | reused
→ 동일 Desired State snapshot을 Task body에 기록
→ dispatch
```

Desired State는 구현 결과가 아니라 사용자 승인 목표다. 구현이 중단되어 Observed와 달라도 다음 reconciliation에서 drift로 사용한다.

금지:
- Plan 승인 전 persist
- linked worktree metadata 수정
- host 필드에 URL/credential 저장
- username/password/token 저장
- 승인 snapshot 재추론
- `Infrastructure Impact: NO`인데 metadata 변경

## Model snapshot

승인 Tier는 정확히 1회 resolve한다.

```bash
python3 /opt/data/shared/scripts/flow_model_policy.py resolve --tier "<DEFAULT|PREMIUM>"
```

`MODEL_TIER`, `MODEL`, `PROVIDER`를 immutable snapshot으로 사용한다.

## Skill Preflight

`skill_view("dev-skill-preflight")` 후 실제 Coder/Reviewer 양쪽에서 사용할 수 있는 skill만 pin한다.

```text
Approved Applicable Skills
→ VALIDATED_SKILLS / REJECTED_SKILLS
→ kanban_create.skills = VALIDATED_SKILLS 전체
```

`REJECTED_SKILLS`는 body에 근거를 남기되 pin하지 않는다. Infrastructure Task의 `dev-infrastructure`, API Task의 `dev-api-spec`, 그리고 `dev-flow-model-policy`처럼 필수 capability가 누락되면 dispatch하지 않는다.

API Task의 `dev-api-spec`은 **Coder/Reviewer가 동일 Markdown contract**를 볼 수 있도록 공통 pin 대상으로 검증한다.

## Kanban 생성 / 알림 Gate

Task는 worker가 가져가기 전에 blocked 상태로 생성하고 **최초 등록 알림** Gate까지 완료한 뒤 unblock한다.

```text
prepare_dispatch.py 정확히 한 번
→ Infrastructure Impact YES면 Desired State persist 정확히 한 번
→ dev-skill-preflight
→ API / model / Infrastructure 승인 snapshot 확인
→ kanban_create(initial_status="blocked", board=BOARD, model=MODEL, provider=PROVIDER, skills=VALIDATED_SKILLS + dev-flow-model-policy) tool 정확히 1회
→ kanban_show(board=BOARD, task_id=<CREATED_TASK_ID>) tool 정확히 1회
→ read-back 검증
→ subscribe_notification.py --board BOARD --task-id <CREATED_TASK_ID> 정확히 1회
→ NOTIFY_STATUS=subscribed + NOTIFY_VERIFIED=true + NOTIFY_REGISTRATION_EVENT=queued
   또는 NOTIFY_STATUS=disabled
→ kanban_unblock(board=BOARD, task_id=<CREATED_TASK_ID>) tool 정확히 1회
```

subscription 확인 뒤 `registered` task event를 enqueue한다. **등록 event**는 Task별 1회다. 알림이 활성화되어 있는데 helper 실패/검증 실패/registration enqueue 실패이면 blocked 상태를 유지한다.

read-back 최소 계약:

```text
board == BOARD
workspace == dir:<APPROVED_WORKSPACE>
assignee == profiles.coder
reviewer == profiles.reviewer
task.skills == VALIDATED_SKILLS (+ dev-flow-model-policy)
status == blocked
model_override == MODEL
provider_override == PROVIDER
Infrastructure Impact YES면 body Desired State == persisted Desired State
```

하나라도 다르면 unblock 금지다.

금지:
- board 인자 생략
- `HERMES_KANBAN_BOARD` fallback
- 알림 실패를 warning으로 무시하고 unblock
- 승인 없는 create/unblock
- Infrastructure Impact YES인데 Desired State persist 없이 create/unblock
- 승인 후 model/provider 재해석
- `hermes project list` / help probe
- Kanban body 임시 파일
- CLI body-file 지원 여부 탐색
- CLI fallback을 탐색하지 않고 BLOCK하지 않는 동작

## Task body canonical snapshot

```text
Workspace Contract:
- Kanban board: <BOARD>
- Workspace: <WORKSPACE_PATH>
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
- Desired State Persistence: UPDATED | REUSED | NOT_REQUIRED
- Application Runtime / Host / Port
- Database Runtime / Host / Port
- Database Platform / Vendor

Model Policy:
- Coder Model Tier: DEFAULT | PREMIUM
- Coder Model: <MODEL>
- Coder Provider: <PROVIDER>
- Reviewer Model: DEFAULT
- Model Escalation: REQUIRE_REAPPROVAL
```

API `DESIGN_FIRST`에서 Coder는 **production API를 변경하기 전에 승인 snapshot을 repository Markdown에 materialize/update**하고, 그 Markdown을 normative contract로 구현한다. `SOURCE_SYNC`는 Application Source 기반 DRAFT 문서화이며 자동 APPROVED 승격을 하지 않는다.

API DESIGN_FIRST의 APPROVED snapshot과 Infrastructure의 persisted Desired State가 각각 Coder/Reviewer normative contract다.

## Coder ↔ Reviewer model transition

```text
Coder approved MODEL/PROVIDER
→ flow_model_policy.py review-enter
→ Reviewer DEFAULT
→ CHANGES_REQUESTED이면 changes-return
→ original Coder MODEL/PROVIDER 복원
```

동일 승인 모델 retry는 재승인하지 않는다. 모델/Provider 변경은 사용자 재승인이 필요하다.

## 성능 불변식

- Workspace 승인 전 working-tree 전체 scan 금지
- `--confirmed-dirty` 뒤 exact count 복구 scan 금지
- Infrastructure detector는 bounded scan 유지
- Coder/Reviewer는 changed scope만 검증
- 모델 snapshot은 승인 시 1회 resolve

## 회귀 검증

```bash
python3 scripts/check_skill_contract.py
python3 scripts/check_api_spec_contract.py
python3 custom-skills/orchestrator/dev-workspace-dispatch/tests/test_prepare_dispatch.py
python3 custom-skills/orchestrator/dev-workspace-dispatch/tests/test_persist_infrastructure_desired.py
python3 custom-skills/orchestrator/dev-workspace-dispatch/tests/test_subscribe_notification.py
python3 shared/scripts/test_kanban_registration_event.py
python3 shared/scripts/test_flow_model_policy.py
```
