# Dispatch Efficiency Contract

이 문서는 Standard Flow에서 작업 생성 전후의 중복 I/O와 capability probing을 방지하는 성능 계약이다.

## 1. Working-tree scan 단일화

정상 경로에서 working-tree 전체 상태 분류는 `dev-workspace-dispatch/scripts/prepare_dispatch.py`가 정확히 한 번 수행한다.

Plan 승인 전후의 Orchestrator는 repository/workspace/branch identity 확인만 수행하고 다음 명령을 별도로 실행하지 않는다.

```text
git status
git diff --name-only
git diff --ignore-cr-at-eol
git ls-files --others
inline Python tracked/effective/EOL 분류
```

`prepare_dispatch.py`가 반환하는 다음 값이 유일한 dispatch dirty evidence다.

```text
EFFECTIVE_CHANGED_COUNT
EOL_ONLY_COUNT
HERMES_MANAGED_COUNT
GIT_TRACKED_SCAN_SECONDS
GIT_EFFECTIVE_SCAN_SECONDS
GIT_UNTRACKED_SCAN_SECONDS
CLASSIFICATION_SECONDS
WORKSPACE_CLASSIFICATION_TOTAL_SECONDS
```

사용자가 현재 dirty workspace 보존을 승인했다면 `--confirmed-dirty`를 사용하고, helper 이전에 정확한 dirty count를 얻기 위한 별도 scan을 하지 않는다.

## 2. Kanban 생성 단일 경로

Workspace helper와 skill preflight 성공 후 다음 순서를 유지한다.

```text
kanban_create
→ kanban_show
→ subscribe_notification.py
→ worker dispatch
```

금지:

```text
hermes kanban create --help
hermes project list
hermes project --help
Kanban body 임시 파일 생성
CLI body-file capability probing
동일 Task를 CLI로 재생성하는 fallback
```

Task body는 `kanban_create` tool의 body 인자로 직접 전달한다.

## 3. 예외 처리

- `prepare_dispatch.py` 실패: Kanban을 만들지 않고 원인을 사용자에게 보고한다.
- `validate_skills.py` 실패: Kanban을 만들지 않는다.
- `kanban_create` tool 실패: CLI fallback을 탐색하지 않고 BLOCK한다.
- `kanban_show` 검증 실패: 재생성하거나 CLI를 탐색하지 않고 BLOCK한다.
- notification 실패: 기존 정책대로 warning이며 dispatch를 막지 않는다.

## 4. 성능 판정

`prepare_dispatch.py`가 여전히 오래 걸리면 helper의 timing 값으로 병목을 구분한다. Orchestrator가 같은 scan을 다시 실행해 비교하지 않는다.

예:

```text
GIT_TRACKED_SCAN_SECONDS=3.1
GIT_EFFECTIVE_SCAN_SECONDS=82.4
GIT_UNTRACKED_SCAN_SECONDS=0.3
WORKSPACE_CLASSIFICATION_TOTAL_SECONDS=85.9
```

이 경우 `--ignore-cr-at-eol` batch scan 또는 Windows bind mount 성능을 후속 조사하며, workflow 레벨의 추가 Git scan으로 우회하지 않는다.
