---
name: dev-workspace-dispatch
description: 승인된 단일 Work Unit 계획과 Git/Non-Git workspace의 버전관리 계약·Coder 모델·capability를 Kanban으로 인계한다. 알림은 동일 컨테이너의 DevKit Notification Bridge가 task_events를 비동기로 관찰한다.
version: 0.22.1
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, git, workspace, branch, kanban, dispatch, orchestrator, work-unit, capability, infrastructure, desired-state, preflight, notification, model, api, spec, performance]
    related_skills: [dev-project-bootstrap, dev-project-pattern, dev-breakdown, dev-api-spec, dev-infrastructure, dev-skill-preflight, dev-workflow-orchestrate, dev-flow-model-policy, dev-feature-docs]
    requires_tools: [terminal, skill_view, kanban_create, kanban_show, kanban_unblock, clarify]
---

# dev-workspace-dispatch

사용자 승인까지 완료된 READY **단일 Work Unit** 계획을 승인된 workspace와 Coder model snapshot과 함께 Kanban으로 인계한다. Git Workspace는 branch/diff 계약을 유지하고, 승인된 Non-Git Workspace는 branch/diff를 `N/A`로 처리한다. 이 Skill이 신규 Standard Dispatch의 표준이다.

`/opt/data/shared/references/standard-work-unit-rules.md`, `/opt/data/shared/references/parent-tracking-rules.md`, `/opt/data/shared/references/session-history-rules.md`를 적용한다.

## 선택적 기능 문서 인계

Standard 승인 계획에 관련 기능 문서가 있으면 문서 경로·해당 범위·사용 방식(`상태 갱신 대상` 또는 `참고 전용`)·쓰기 workspace를 기존 Task 본문의 한국어 자유 형식 설명으로 보존한다. 별도 기계 파싱 키/필수 field는 만들지 않는다. 연결이 없으면 기존 본문을 그대로 사용한다.

이 정보는 진입 조건이나 새로운 승인 Gate가 아니다. `prepare_dispatch.py`, `kanban_create` args/schema, read-back 검증, unblock 횟수, `kanban_create.skills`를 변경하지 않는다. Orchestrator 전용 `dev-feature-docs`를 Coder/Reviewer에 필수 pin하지 않는다. 문서 누락/모호함/반영 실패만으로 dispatch를 차단하지 않는다.

Coder/Reviewer는 기존 구현·검증 근거를 제공하며 문서 검색·연결 변경·기능 범위 확장을 반복하지 않는다. Orchestrator가 기존 진행 조회/마무리에서 문서 상태를 관찰 기반으로 보완한다. 카드 생성/대기만으로 진행 중으로 기록하지 않는다. 문서 상태를 위해 새 Task, callback, notifier 변경을 만들지 않는다.

## 1. 진입 조건
- 실행 계획 + 검증 계획 승인 완료
- Verification Contract에 Target/Method/Provider/Environment Dependency/Required Environment/Lifecycle/Fallback Policy 존재
- `Work Unit Class`가 `DESIGN | IMPLEMENTATION | MIGRATION | REFACTOR | AUDIT` 중 하나
- `Work Unit Boundary`와 Current/Follow-up/Excluded scope가 승인 Plan에 존재
- `SPLIT_REQUIRED`이면 현재 Plan의 Implementation Tasks/AC가 **Current Deliverable만** 포함하고 Follow-up scope를 구현 범위에서 제외
- 승인 이후 요구사항 변경 작업이면 Requirement Delta 승인 완료
- `API Spec Gate: REQUIRED`이면 `API Spec Status: APPROVED` 및 승인된 Markdown snapshot 확보
- `API Spec Gate: NOT_REQUIRED`이면 Mode가 `SOURCE_SYNC | AUDIT | NOT_REQUIRED` 중 하나임을 확인
- `Infrastructure Impact: YES`이면 승인된 Infrastructure Desired State snapshot 확보
- workspace 승인 완료
- Git Workspace면 current 또는 create branch 승인 완료
- Non-Git Workspace면 Project 등록 시 `non_git_write_acknowledged=true`가 확인되어 Branch Gate/기존 Git 변경 보존 Gate가 `NOT_REQUIRED`
- Git Workspace에 기존 변경이 있을 수 있다면 reset/restore/stash 없이 전부 보존할지 승인 완료
- Coder Model Tier(DEFAULT|PREMIUM) 승인 완료
- 승인 Tier를 `flow_model_policy.py resolve`로 해석한 `MODEL/PROVIDER` snapshot 확보
- Managed Project root의 `.hermes/project.yaml` metadata 존재
- Parent Tracking Mode가 `NEW_PARENT | LINK_EXISTING_PARENT | PROMOTE_TO_PARENT`이면 `[작업 관리 방식 승인]` 완료 및 Parent Task ID 확보

Reviewer는 별도 모델 승인을 받지 않고 항상 Reviewer profile DEFAULT를 사용한다.

`SPLIT_REQUIRED`의 Follow-up Work Unit은 Task metadata로만 보존한다. Dispatch가 같은 승인으로 후속 Task를 자동 생성하거나 pin/dispatch하면 안 된다.

## 2. Project / Workspace 분리 계약

Project와 Workspace의 Version Control을 별도로 판정한다.

```text
A. 기존 Git Project
Project = Git Primary Repository
Workspace = Primary 또는 linked worktree

B. Composite Project
Project = Non-Git managed root
├─ docs/                    ← Non-Git
├─ old/service-a/.git       ← nested Git
└─ new/service-a/.git       ← nested Git

Workspace = 승인된 child Git root 또는 승인된 Non-Git directory
```

Managed Project root의 `.hermes/project.yaml`이 Project/Board의 canonical metadata다. Git Project에서는 기존처럼 `git worktree list --porcelain`로 Primary Worktree를 해석한다. Non-Git Project에서는 승인 Workspace가 Project root 하위인지 확인하고, Workspace 자체가 정확한 Git root이면 Git branch/diff/toolchain 계약을 사용한다.

Helper 경계:

```text
PROJECT_ROOT=<managed project root>
PROJECT_REPOSITORY=<managed project root>   # legacy compatibility output
PROJECT_VERSION_CONTROL=git | none
NON_GIT_WRITE_ACKNOWLEDGED=true | false

WORKSPACE_PATH=<approved workspace>
WORKSPACE_VERSION_CONTROL=git | none
NESTED_GIT_WORKSPACE=true | false
LINKED_WORKTREE=true | false
```

- `PROJECT_VERSION_CONTROL=git`: Workspace는 같은 Git common-dir에 속해야 한다.
- `PROJECT_VERSION_CONTROL=none + WORKSPACE_VERSION_CONTROL=git`: child Git Repository가 자신의 branch/Base SHA/diff/toolchain을 소유한다.
- `PROJECT_VERSION_CONTROL=none + child Non-Git Workspace`: `branch-mode=none`을 사용하며, Project root와 다른 실행 Workspace라면 해당 child 기준 Java toolchain을 준비한다.
- `WORKSPACE_VERSION_CONTROL=none`: Branch/Base SHA는 `NONE`, Git change scan은 `unsupported-non-git`이다. Hermes는 snapshot을 생성하지 않는다.
- linked worktree의 stale `.hermes/project.yaml`은 기존처럼 `WORKSPACE_METADATA_IGNORED`로 처리한다.
- process-local `safe.directory`만 사용하며 global safe.directory 변경은 금지한다.

## 3. 대형 Git Workspace Fast Path

Git Workspace에서 사용자가 기존 변경 전체 보존을 이미 승인한 경우:

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


Non-Git Managed Project / Workspace:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/prepare_dispatch.py" \
  --task-key "<TASK-KEY>" \
  --repo "<MANAGED_PROJECT_ROOT>" \
  --workspace "<APPROVED_WORKSPACE>" \
  --branch-mode none
```

Non-Git 상위 Project 아래 child Git Repository를 선택한 경우에는 `--repo <MANAGED_PROJECT_ROOT>`를 함께 전달하고 `--branch-mode current|create`를 사용한다. child Non-Git directory를 선택하면 동일하게 `--repo`를 전달하되 `--branch-mode none`을 사용한다. 두 경우 모두 Project root와 다른 실행 Workspace면 Dispatch가 해당 child Workspace의 Java toolchain을 독립적으로 준비한다.

Helper 출력의 `BOARD`는 Managed Project root `.hermes/project.yaml`의 `kanban.board`이며 유일한 board source다.

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

## 7. Parent Tracking Dispatch 계약

Parent Tracking Mode가 `NONE`이면 기존 단건 제목/dispatch를 그대로 사용한다.

Parent Tracking이 활성화되면 다음 제목 규칙을 적용한다.

```text
Parent title: [부모] <전체 작업 제목>
Child title:  [자식] <현재 Work Unit 제목>
```

- Parent는 `Execution: NON_DISPATCH` tracking card다.
- Parent 생성 시 `kanban_create`는 가능하지만 `kanban_unblock`/worker dispatch는 금지한다.
- Parent/Child 관계는 반드시 Parent Task ID로 기록한다. 제목 접두어는 사용자 식별용일 뿐 관계 key가 아니다.
- `kanban_create.parents`는 **승인된 구조적 Parent Task ID 전용**이다. 직전 Task/선행 Task를 실행 순서 목적으로 넣지 않는다.
- 실행 순서는 Task body의 `Execution Ordering: Mode / Depends On Task IDs`로 별도 기록한다.
- `SEQUENTIAL`이면 `Depends On Task IDs`의 모든 Task가 `DONE`인지 확인한 뒤에만 현재 Child를 unblock/dispatch한다. Parent의 상태는 이 확인 대상이 아니다.
- 현재 Standard Task만 Child로 생성한다. 계획된 후속 Child는 선생성하지 않는다.
- `PROMOTE_TO_PARENT`는 기존 Task를 복제하지 않고 새 Parent의 첫 연결 이력으로 기록한다.
- Child가 DONE되면 Parent에 `Task ID / Job ID / Title / Session IDs / Result / Implementation Summary`를 append한다. Job ID는 확인 불가 시 `UNKNOWN`, Session IDs는 child `TASK_SESSION_HISTORY`에서 실제 값을 찾지 못하면 `UNAVAILABLE`로 기록하며 추측하지 않는다.
- Child 완료 뒤 다음 Child를 자동 생성/dispatch하지 않는다. 후속 작업은 새 Standard Flow에서 기존 Parent를 선택해 진행한다.

## 7. Kanban 생성·Dispatch 단일 경로

```text
prepare_dispatch.py 정확히 한 번
→ Work Unit Contract 확인
→ Infrastructure Impact=YES이면 approved Desired persist 정확히 한 번
→ dev-skill-preflight
→ approved API Spec contract 확인 (REQUIRED일 때)
→ approved model snapshot 확인
→ Parent Tracking이면 kanban_create.parents=<APPROVED_PARENT_TASK_ID>만 사용
→ 실행 순서는 Task body의 Execution Ordering / Depends On Task IDs로 기록
→ kanban_create(board=BOARD, initial_status="blocked", model=MODEL, provider=PROVIDER, skills=VALIDATED_SKILLS + dev-flow-model-policy)
→ kanban_show 정확히 1회
→ 등록 read-back 계약 검증(Parent Tracking이면 actual parent == approved Parent Task ID)
→ SEQUENTIAL이면 Depends On Task IDs가 모두 DONE인지 검증
→ parent mismatch면 PARENT_RELATION_MISMATCH로 중단
→ 선행 Task 미완료면 EXECUTION_DEPENDENCY_PENDING으로 blocked 유지
→ kanban_unblock tool 정확히 1회
→ ready 전환 후 worker dispatch
```

Kanban 등록 성공 기준은 `kanban_create + kanban_show` read-back이다. `initial_status="blocked"`는 알림 Gate가 아니라 **검증 완료 전 worker claim을 막는 짧은 dispatch barrier**다.

알림은 dispatch와 독립적이다. 같은 `hermes-dev` 컨테이너에서 s6가 감독하는 `devkit-notifier` 프로세스가 Hermes의 기존 `task_events`를 read-only로 관찰한다.

```text
Hermes task_events
→ DevKit Notification Bridge
→ 업무용 한국어 formatter
→ hermes send
→ Discord / configured platform
```

Bridge는 Hermes source를 patch하거나 custom task event를 삽입하지 않는다. 최초 카드 등록은 Hermes가 원래 기록하는 `created` event로 알리고, `initial_status` 때문에 생성되는 내부 `blocked` event는 알림에서 제외한다. Bridge 전송 실패는 개발 Task lifecycle을 차단하지 않으며 자체 cursor를 성공 전송 뒤에만 전진시켜 재시도한다.

호출 횟수 계약:

```text
prepare_dispatch.py 정확히 한 번
persist_infrastructure_desired.py 0회 또는 정확히 1회
kanban_create tool 정확히 1회
kanban_show tool 정확히 1회
kanban_unblock tool 정확히 1회
```

금지:

```text
Work Unit Contract 없는 Standard Task dispatch
SPLIT_REQUIRED인데 Follow-up scope를 같은 Task에 포함
Follow-up Work Unit 자동 Kanban 생성/dispatch
Parent tracking card를 kanban_unblock/worker dispatch
Parent 관계를 제목 문자열만으로 판정
- 실행 선행 Task를 `kanban_create.parents`에 넣어 구조적 Parent처럼 연결
- 승인된 Parent Task ID와 read-back 실제 Parent가 다른데도 unblock/dispatch
- Parent의 BLOCKED/NON_DISPATCH 상태를 Child 실행 dependency로 사용
Parent 연결 Task에 `[자식]` 제목 접두어 또는 Parent Task ID 기록 누락
실행 카드의 Session History를 단일 Session ID 값으로 덮어쓰기
발견되지 않은 Session ID를 추측해 Task/Parent에 기록
Follow-up capability를 현재 Applicable Skills에 자동 추가
board 인자 생략
HERMES_KANBAN_BOARD fallback
default/current board fallback
Infrastructure Impact=YES인데 Desired State persistence 생략
Plan에 없는 Infrastructure Desired 값을 dispatch 시 재추론
승인되지 않은 Verification Provider를 Task body에 추가하거나 자동 fallback
Infrastructure metadata에 credential/secret 기록
native notify-subscribe를 DevKit dispatch 경로에서 호출
custom registration event 생성
registration delivery ACK Gate
Discord formatter/session-context를 Hermes notifier source에 patch
알림 전송 실패를 이유로 blocked 상태 유지
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

## 8. Session History 계약

Parent 없는 일반 실행 카드와 `[자식]` 카드는 동일한 Session History 계약을 사용한다.

```text
worker start
→ task_session_history.py capture
→ 새 session이면 TASK_SESSION_HISTORY durable comment
→ 기존 구현/review
```

Task 생성 시점에는 NEW worker의 최종 Session ID가 아직 만들어지지 않을 수 있으므로 Task Body에 추측값을 선기록하지 않는다. 실제 worker가 시작된 뒤 profile `state.db`와 Kanban context를 대조해 기록한다.

Parent는 NON_DISPATCH이므로 Coder/Reviewer execution session을 갖지 않는다. 완료 자식의 Session IDs를 Parent Completed Work에 요약하고, Orchestrator management session은 실제 ID가 확인 가능한 경우에만 기록한다.

## 8. Task Body Contract

Parent가 있는 실제 Standard Task에는 다음 블록을 먼저 기록한다.

```text
Parent Tracking:
- Parent Task ID: <task-id>
- Parent Title: [부모] <title>
- Relation: CHILD_WORK_UNIT
```

그 뒤 기존 Task Body Contract를 그대로 유지한다.

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
- Project root: <PROJECT_ROOT>
- Project version control: git | none
- Non-Git write acknowledged: true | false
- Workspace: <WORKSPACE_PATH>
- Workspace version control: git | none
- Branch mode: current | create | none
- Expected branch: <BRANCH | NONE>
- Base branch: <BASE_BRANCH | NONE>
- Base SHA: <BASE_SHA | NONE>
- Existing changes preservation approved: true | false | NOT_REQUIRED
- Workspace change scan mode: full | skipped-approved-preservation | unsupported-non-git

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

Verification Contract:
- Verification Target: <...>
- Verification Method: <...>
- Verification Provider: PROJECT_CANONICAL | LOCAL_RUNTIME | DOCKER | TESTCONTAINERS | CI | EXTERNAL_SERVICE | NONE
- Environment Dependency: NONE | REQUIRED
- Required Environment: <... | NONE>
- Lifecycle: <reuse | ephemeral+cleanup | externally-managed | NONE>
- Fallback Policy: REAPPROVAL_REQUIRED | NOT_REQUIRED
- Verification Approval: APPROVED

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
python3 shared/scripts/test_flow_model_policy.py
```
