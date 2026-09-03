---
name: dev-workspace-dispatch
description: 승인된 구현 계획과 project pattern/capability 계약을 Git workspace와 Kanban으로 인계한다.
version: 0.6.1
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, git, workspace, branch, kanban, dispatch, orchestrator, capability, preflight, notification]
    related_skills: [dev-project-bootstrap, dev-project-pattern, dev-breakdown, dev-skill-preflight, dev-workflow-orchestrate]
    requires_tools: [terminal, skill_view, kanban_create, kanban_show, clarify]
---

# dev-workspace-dispatch

사용자 승인까지 완료된 READY 구현 계획을 사용자가 승인한 Git workspace와 branch 전략에 맞춰 Kanban 작업으로 인계한다.

이 Skill이 신규 Dispatch의 표준이다. deprecated `dev-worktree-dispatch`와 달리 기본 동작으로 git worktree add를 실행하지 않는다. 작업 위치와 branch 전략은 사람에게 보여주고 승인받은 뒤 사용한다.

## 1. 사용 시점

다음 조건을 모두 만족할 때 사용한다.

- dev-breakdown이 구현 계획을 생성했다.
- 계획의 Dispatch Readiness가 READY다.
- `Project Pattern Summary`, `Pattern References`, `Applicable Skills`, `Pattern Conflicts`가 계획에 존재한다.
- 사용자가 현재 Implementation Plan을 명시적으로 승인했다.
- 사용자가 Git Workspace / Branch 방식을 명시적으로 승인했다.
- 대상 Repository가 dev-project-bootstrap으로 관리되고 있다.
- 구현을 프로젝트 metadata의 profiles.coder에게 인계해야 한다.

사용하지 않을 경우:

- Plan이 BLOCKED다.
- Plan 승인 또는 Workspace/Branch 승인이 없다.
- project pattern/capability handoff 필드가 누락되어 Coder가 승인된 판단을 재현할 수 없다.
- workspace가 Git repository root가 아니다.
- workspace가 project metadata의 repository와 같은 Git common dir에 속하지 않는다.
- workspace에 기존 **effective project change**가 있는데 사용자가 그 상태를 승인하지 않았다.

## 2. 승인 Gate

이 Skill은 Plan Approval과 Git Workspace / Branch Approval이 모두 끝난 뒤에만 실행한다.

Workspace / Branch Approval에서 사용자에게 보여줄 최소 항목:

```text
Project:
Repository:
Approved workspace:
Current branch:
Base branch:
Effective project changes: <count>
EOL-only changes: <count>
Hermes managed files: <count>
Suggested new branch: feature/<TASK-KEY>
```

변경 상태는 반드시 다음 세 범주로 분리한다.

1. **Effective project changes**: 실제 프로젝트 content 변경 및 `.hermes/` 밖의 untracked 파일. 사용자 승인 대상이다.
2. **EOL-only changes**: CRLF/LF 차이만 있는 tracked 파일. 사용자 변경으로 승격하지 않는다.
3. **Hermes managed files**: `.hermes/` 아래의 tracked/untracked 관리 파일. 프로젝트 사용자 변경 개수에 포함하지 않는다.

`dirty`, `많음`, `매우 많음`, `대량`처럼 개수를 추측하는 표현을 사용하지 않는다. 항상 helper가 반환한 정확한 count와 필요 시 path를 그대로 제시한다.

Effective project changes가 0이고 EOL-only/Hermes managed file만 존재하면 `--confirmed-dirty` 승인을 요구하지 않는다. 파일을 reset/restore/stash/line-ending rewrite하지 않는다.

사용자 선택지는 다음이다.

```text
1. 현재 workspace + 현재 branch 사용
2. 현재 workspace + 새 branch 생성
3. 사용자가 지정한 별도 workspace + 현재 branch 사용
4. 사용자가 지정한 별도 workspace + 새 branch 생성
```

Effective project changes가 있으면 helper가 반환한 `EFFECTIVE_CHANGED_COUNT`와 path를 사용자에게 보여주고, 사용자가 해당 변경을 유지한 채 작업해도 된다고 승인해야 한다.

## 3. Helper 실행

현재 branch를 그대로 사용할 때:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/prepare_dispatch.py" \
  --task-key "<TASK-KEY>" \
  --workspace "<APPROVED_WORKSPACE>" \
  --branch-mode current
```

새 branch를 만들 때:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/prepare_dispatch.py" \
  --task-key "<TASK-KEY>" \
  --workspace "<APPROVED_WORKSPACE>" \
  --branch-mode create \
  --branch "feature/<TASK-KEY>"
```

Effective project changes가 있고 사용자가 이를 승인한 경우에만 `--confirmed-dirty`를 추가한다.

Helper 검증 항목:

1. Task Key가 안전한지 확인한다.
2. Workspace가 Git repository root인지 확인한다.
3. `.hermes/project.yaml`이 managed metadata인지 확인한다.
4. Metadata repository와 실제 repository가 일치하는지 확인한다.
5. Approved workspace가 managed repository와 같은 Git common dir인지 확인한다.
6. Base branch/ref와 base SHA를 확정한다.
7. tracked/untracked 상태를 effective/EOL-only/Hermes managed로 분류한다.
8. 현재 branch 또는 새 branch 생성 결과를 검증한다.

변경 상태 분류는 파일별 `git diff` 반복 호출을 금지하고 다음 batch scan으로 수행한다.

```text
git diff --name-only -z HEAD
git diff --name-only -z --ignore-cr-at-eol HEAD
git ls-files -z --others --exclude-standard
```

세 결과는 Python set 연산으로 `effective`, `EOL-only`, `Hermes managed`로 분리한다. 대량 EOL-only 변경이 있는 Windows bind mount에서도 파일 수만큼 Git subprocess를 반복하지 않는다.

성능 관찰을 위해 helper는 다음 timing을 함께 출력한다.

```text
GIT_TRACKED_SCAN_SECONDS=<seconds>
GIT_EFFECTIVE_SCAN_SECONDS=<seconds>
GIT_UNTRACKED_SCAN_SECONDS=<seconds>
CLASSIFICATION_SECONDS=<seconds>
WORKSPACE_CLASSIFICATION_TOTAL_SECONDS=<seconds>
```

이 값은 진단 정보이며 승인 판단에는 사용하지 않는다. 지연이 남으면 어떤 Git scan이 병목인지 판단하는 데 사용한다.

`WORKSPACE_DIRTY`는 raw 작업트리에 어떤 변경이든 존재하는지 나타내는 정보용 필드다. 승인/위험 판단에는 `WORKSPACE_EFFECTIVE_DIRTY`와 `EFFECTIVE_CHANGED_COUNT`를 사용한다.

Helper가 non-zero로 종료되면 Kanban Task를 만들지 않는다.

## 4. Skill Preflight Gate

Workspace helper가 성공한 뒤 Kanban Task를 만들기 전에 반드시 `skill_view("dev-skill-preflight")`로 전체 계약을 로드한다.

`Applicable Skills`는 계획상의 capability 후보이고 `task.skills`는 Hermes worker가 시작 시 강제로 로드할 runtime pinned skill이다. 둘을 직접 복사하지 않는다.

Standard Flow에서는 `ASSIGNEE`와 `REVIEWER` 두 profile을 대상으로 계획의 Applicable Skills를 검증한다.

```bash
python3 /opt/custom-skills/orchestrator/dev-skill-preflight/scripts/validate_skills.py \
  --profile "<ASSIGNEE>" \
  --profile "<REVIEWER>" \
  --skill "<APPLICABLE_SKILL_1>" \
  --skill "<APPLICABLE_SKILL_2>"
```

규칙:

1. helper가 exit code 2 등 non-zero로 실패하면 preflight 결과를 신뢰할 수 없으므로 Kanban Task를 만들지 않는다.
2. `VALIDATED_SKILLS`만 `kanban_create.skills`에 전달한다.
3. `REJECTED_SKILLS`는 `Rejected Pinned Skills`에 기록하고 runtime pin에서는 제외한다.
4. rejected 이름을 비슷한 이름으로 자동 교체하지 않는다.
5. validated skill이 없으면 `skills=[]`를 허용한다.
6. 배열의 첫 번째 skill만 선택하지 말고 `VALIDATED_SKILLS` 전체를 전달한다.
7. Task 생성 직후 `kanban_show`로 실제 `task.skills`를 확인하고 `VALIDATED_SKILLS`와 정확히 일치하지 않으면 dispatch하지 않는다.

## 5. Kanban Body 계약

Body에는 `dev-breakdown`의 승인된 기술 판단을 축약하지 말고 Goal, Acceptance Criteria, Implementation Tasks, Test Plan, Dependencies, Known Risks, Project Pattern Summary, Pattern References, Applicable Skills, Validated/Rejected Pinned Skills, Pattern Conflicts, Improvement Candidates, Reviewer Profile, Implementation/Review Skill, Workspace Contract를 보존한다.

Workspace Contract에는 최소 다음을 기록한다.

```text
- Workspace: <WORKSPACE_PATH>
- Branch mode: current | create
- Expected branch: <BRANCH>
- Base branch: <BASE_BRANCH>
- Base SHA: <BASE_SHA>
- Effective project changes at dispatch: <EFFECTIVE_CHANGED_COUNT>
- EOL-only changes at dispatch: <EOL_ONLY_COUNT>
- Hermes managed files at dispatch: <HERMES_MANAGED_COUNT>
- Effective project changes가 있었다면 사용자가 해당 상태를 승인했다.
- Coder는 기존 변경을 reset/restore/stash하지 않는다.
- Coder는 할당된 Workspace 밖을 수정하지 않는다.
- Coder는 Branch를 전환하지 않는다.
- Coder는 다른 Git Worktree를 만들지 않는다.
```

Task body의 기존 변경 설명에도 `많음/매우 많음/대량`을 사용하지 않는다. helper의 숫자를 그대로 기록한다. EOL-only/Hermes managed 파일을 `사용자 변경`이라고 표현하지 않는다.

## 6. Kanban 알림 구독

`kanban_create` 성공 후 생성된 Task ID를 확보하고, `kanban_show`로 `task.skills` 검증까지 끝난 즉시 아래 helper를 정확히 한 번 실행한다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/subscribe_notification.py" --task-id "<KANBAN_TASK_ID>"
```

환경변수 계약:

```text
HERMES_KANBAN_NOTIFY_ENABLED=false | true
HERMES_KANBAN_NOTIFY_PLATFORM=discord | slack | telegram | <Hermes 지원 플랫폼>
HERMES_KANBAN_NOTIFY_TARGET=<gateway chat/channel id>
HERMES_KANBAN_NOTIFY_DELIVERY_MODE=notify | wake | notify+wake
HERMES_KANBAN_NOTIFY_CHAT_TYPE=<optional chat type>
```

규칙:

1. 기본값은 `HERMES_KANBAN_NOTIFY_ENABLED=false`다.
2. 활성화 시 Hermes 공식 `kanban notify-subscribe` 명령을 사용한다.
3. 플랫폼별 명령을 Skill 본문에 하드코딩하지 않는다. `PLATFORM`, `TARGET`, `DELIVERY_MODE`, `CHAT_TYPE`만 공통 helper에 전달한다.
4. Discord 인증은 `DISCORD_BOT_TOKEN`을 로컬 `.env`에서 Gateway로 전달하며 Task body/comment/log에 token을 기록하지 않는다.
5. `NOTIFY_STATUS=subscribed`면 정상 등록이다.
6. `NOTIFY_STATUS=disabled` 또는 `NOTIFY_STATUS=warning`이어도 Kanban 생성/dispatch를 취소하거나 `BLOCKED`로 바꾸지 않는다.
7. 알림 helper 실패를 이유로 재시도 loop, approval 대기, source 수정, 별도 notification Task 생성을 하지 않는다.
8. 신규 Task에만 자동 구독하며 기존 Task를 임의로 재구독하지 않는다.

## 7. 성공 기준

- Plan Readiness = READY
- Plan 승인 확인됨
- Workspace/Branch 승인 확인됨
- Approved workspace가 Git repository root임
- Approved workspace가 managed repository와 같은 Git common dir에 속함
- Expected Branch가 실제 현재 branch와 일치함
- Base SHA가 기록됨
- Effective/EOL-only/Hermes managed 변경 개수가 분리되어 기록됨
- Existing effective project changes가 있었다면 사용자 승인 확인됨
- Skill Preflight가 성공함
- `task.skills`가 `VALIDATED_SKILLS`와 정확히 일치함
- Kanban Workspace가 dir:<approved-workspace>임
- Goal/AC/Implementation Plan/Test/Risks가 보존됨
- Project Pattern Summary/Pattern References/Applicable Skills/Pattern Conflicts가 보존됨
- Validated/Rejected pinned skill 결과가 보존됨
- Reviewer 정보와 Workspace Contract가 보존됨
- 알림이 활성화된 경우 notification helper를 1회 호출했으며 성공/경고 여부와 무관하게 dispatch lifecycle을 유지함

## 8. 회귀 검증

```bash
python3 custom-skills/orchestrator/dev-skill-preflight/tests/test_validate_skills.py
python3 custom-skills/orchestrator/dev-workspace-dispatch/tests/test_prepare_dispatch.py
python3 custom-skills/orchestrator/dev-workspace-dispatch/tests/test_subscribe_notification.py
```

관련 orchestrator 회귀 검증 전체:

```bash
python3 -m compileall -q custom-skills
python3 scripts/check_skill_contract.py
python3 custom-skills/orchestrator/dev-skill-preflight/tests/test_validate_skills.py
python3 custom-skills/orchestrator/dev-workspace-dispatch/tests/test_prepare_dispatch.py
python3 custom-skills/orchestrator/dev-workspace-dispatch/tests/test_subscribe_notification.py
python3 custom-skills/orchestrator/dev-project-bootstrap/tests/test_metadata_preservation.py
python3 custom-skills/orchestrator/dev-project-resolve/tests/test_project_resolve.py
```
