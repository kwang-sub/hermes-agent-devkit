<!-- HERMES-COMMON:START -->

# Common Agent Development Rules

이 관리 블록은 개발 작업의 항상 적용되는 최소 정책이다. 세부 판단이 필요하면 `shared/references/common-agent-rules.md`를 읽는다. 프로젝트별 규칙은 이 정책을 확장할 수 있으나 조용히 약화할 수 없다.

## 우선순위와 역할
- 우선순위: platform/system → 현재 사용자 요청 → project context → common policy → loaded skill.
- Orchestrator: project resolve/ensure, evidence-based `dev-breakdown`, 승인, `dev-workspace-dispatch`만 조정한다. dispatch한 구현이나 review를 직접 하지 않는다.
- Coder: 승인된 Workspace/Branch에서 승인 계획만 최소 변경으로 구현·검증한다. workspace 밖 수정, branch 전환, 추가 worktree를 하지 않는다.
- Reviewer: requirement/AC/plan과 diff·검증을 독립적으로 읽고 source를 수정하지 않은 채 approve/request-changes/block한다.

## 필수 Gate와 계약
`Request → Project Approval → Breakdown → Plan Approval → Workspace / Branch Approval → Dispatch → coder ↔ reviewer`

- 사용자가 정확한 managed project를 직접 지정하지 않았다면 Project Approval Gate를 통과한다.
- 모든 `READY` 계획은 별도의 Plan Approval Gate를 통과한다.
- dirty 상태를 포함한 Git status와 current/create branch 선택을 보여주고 Workspace / Branch Approval Gate를 통과한다.
- dispatch에는 Goal, Acceptance Criteria, Implementation Tasks, Test Plan, Dependencies, Risks, approved Workspace, Expected Branch, Base Branch, Base SHA, coder, reviewer를 보존한다.

## Evidence, scope, safety
- source, call flow, tests, config, schema, history와 기존 pattern을 확인하고 product intent를 추측하지 않는다.
- 요구사항에 직접 필요한 최소 diff만 만들며 unrelated refactor/format/dependency upgrade를 섞지 않는다.
- 관련 있을 때 failure/null/input/state, compatibility, transaction, concurrency, idempotency/retry, security와 rollback을 확인한다.
- credential, token, password, cookie, raw PII 등 secret을 source/context/skill/Kanban/log에 기록하지 않는다.
- 기존 사용자 변경을 reset/restore/clean/stash/commit하거나 덮어쓰지 않는다. 승인 없는 destructive git, force push/history rewrite/worktree removal을 금지한다.
- publication 단계가 명시되지 않으면 commit, push, PR, merge를 하지 않는다.

## Metadata, verification, completion
- local automation source는 `<repo>/.hermes/project.yaml`이며 Board/repository/base/profile을 추측하지 않는다. 이 파일을 Hermes 공식 필수 파일로 간주하지 않는다.
- context file discovery는 Hermes 공식 규칙을 따르고 기존 project instructions를 보존한다.
- 위험 기반 targeted test부터 실행하고 실제 command/result, 미실행 이유와 residual risk를 보고한다.
- BLOCKED에는 확인된 사실, blocker, 필요한 입력, 재개 조건을 기록한다.
- 계획과 사용자 진행 보고는 한국어로 작성한다.

<!-- HERMES-COMMON:END -->

<!-- HERMES-PROJECT:START -->

## Hermes Project Configuration

> 이 블록은 `dev-project-bootstrap`이 관리한다. 프로젝트 자동화의 canonical 값은 `.hermes/project.yaml`이다.

- Project ID: `hermes-agent-devkit`
- Project Name: `hermes-agent-devkit`
- Repository: `/workspace/hermes-agent-devkit`
- Kanban Board: `hermes-agent-devkit`
- Default Base Branch: `dev`
- Worktree Root: `/workspace/.worktrees/hermes-agent-devkit`
- Orchestrator Profile: `orchestrator`
- Coder Profile: `coder`
- Reviewer Profile: `reviewer`

`resolver:` 값은 사용자가 직접 관리한다. Agent는 Bootstrap 중 resolver alias/module/file/path를 추측해서 기록하지 않는다.

개발 작업은 프로젝트 metadata를 먼저 확인하고, 사용자가 승인한 Workspace/Branch만 사용한다.

<!-- HERMES-PROJECT:END -->
