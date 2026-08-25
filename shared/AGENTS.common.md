<!-- HERMES-COMMON:START -->

# Common Agent Development Rules

이 관리 블록은 개발 작업의 항상 적용되는 최소 정책이다. 세부 판단이 필요하면 `shared/references/common-agent-rules.md`를 읽는다. 프로젝트별 규칙은 이 정책을 확장할 수 있으나 조용히 약화할 수 없다.

## 우선순위와 역할
- 우선순위: platform/system → 현재 사용자 요청 → project context → common policy → loaded skill.
- Orchestrator: 복잡한 작업의 project resolve/ensure, evidence-based `dev-breakdown`, 승인, `dev-workspace-dispatch`를 조정한다. dispatch한 구현이나 review를 직접 하지 않는다.
- Coder: Fast Flow에서는 사용자 요청을 작은 작업 계약으로 정규화해 Kanban에 self-dispatch하고, worker 실행에서는 승인된 Workspace/Branch와 계약 안에서 최소 변경으로 구현·검증한다.
- Reviewer: requirement/AC/scope와 diff·검증을 독립적으로 읽고 source를 수정하지 않은 채 approve/request-changes/block한다.

## Workflow 선택

### Fast Flow
`User → Coder intake → Kanban self-dispatch → Coder worker → Reviewer`

- 단일 managed Repository, clean current branch, 작고 명확한 변경, 기존 패턴 기반 구현에만 사용한다.
- Architecture/Product 결정, public API/DB schema 변경, dependency 변경, cross-repo 작업, 모호한 요구사항에는 사용하지 않는다.
- Interactive coder는 Fast Flow Task를 Kanban에 등록한 뒤 source를 직접 수정하지 않는다. Gateway dispatcher가 coder worker를 실행한다.
- worker가 실제 evidence에서 범위 확대 조건을 발견하면 `FAST_FLOW_ESCALATION_REQUIRED`로 Block하고 Standard Flow로 전환한다.

### Standard Flow
`Request → Project Approval → Breakdown → Plan Approval → Workspace / Branch Approval → Dispatch → coder ↔ reviewer`

- 신규 기능, 설계/분해가 필요한 작업, 여러 module/repository 영향, API/Schema/Dependency 변경, 모호한 요구사항은 Orchestrator부터 시작한다.
- 사용자가 정확한 managed project를 직접 지정하지 않았다면 Project Approval Gate를 통과한다.
- 모든 `READY` 계획은 별도의 Plan Approval Gate를 통과한다.
- dirty 상태를 포함한 Git status와 current/create branch 선택을 보여주고 Workspace / Branch Approval Gate를 통과한다.

## Kanban 계약
- Fast/Standard Flow 모두 coder→reviewer handoff는 Kanban에 남긴다.
- Task에는 Goal, Acceptance Criteria, Implementation Tasks, Test Plan, Risks, approved Workspace, Expected Branch, Base Branch, Base SHA, coder, reviewer를 보존한다.
- Fast Flow에는 `Flow: FAST`와 escalation 조건을 추가한다.
- Reviewer 승인 전 coder가 task를 직접 complete하지 않는다.

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
