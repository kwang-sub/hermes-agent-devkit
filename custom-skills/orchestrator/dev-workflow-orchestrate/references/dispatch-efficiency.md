# Dispatch Efficiency Contract

Standard Flow에서 repository-wide I/O를 최소화하는 성능 계약이다.

## 1. Orchestrator

Workspace 승인 전에는 identity 조회만 수행하고 다음 전체 scan을 하지 않는다.

```text
git status
git diff --name-only
git diff --ignore-cr-at-eol
git ls-files --others
inline Python tracked/effective/EOL 분류
```

### 기존 변경 전체 보존 승인 전

정확한 dirty 상태가 꼭 필요한 경우 `prepare_dispatch.py`가 full classification을 정확히 한 번 수행한다.

```text
GIT_TRACKED_SCAN_SECONDS
GIT_EFFECTIVE_SCAN_SECONDS
GIT_UNTRACKED_SCAN_SECONDS
WORKSPACE_CLASSIFICATION_TOTAL_SECONDS
```

### 기존 변경 전체 보존 승인 후

`prepare_dispatch.py --confirmed-dirty`를 사용하고 repository-wide Git change/EOL/untracked scan을 생략한다.

```text
WORKSPACE_CHANGE_SCAN_MODE=skipped-approved-preservation
EFFECTIVE_CHANGED_COUNT=-1
EOL_ONLY_COUNT=-1
HERMES_MANAGED_COUNT=-1
```

`-1`은 not-scanned이다. exact count를 복원하기 위한 추가 scan을 금지한다.

## 2. Coder

Coder는 구현 과정에서 실제 Changed Files를 확정하고 최종 검증 시 해당 path만 넘긴다.

```text
change_summary.py --include <changed-path-1> --include <changed-path-2>
```

tracked와 untracked 모두 Git pathspec으로 제한한다. scope 없는 full scan은 Standard Flow에서 금지하고 `--allow-full-scan`은 진단 전용이다.

## 3. Reviewer

Reviewer는 Coder handoff의 Changed Files를 재사용한다.

```text
review_context.py --include <changed-path-1> --include <changed-path-2>
```

Coder scope가 누락됐으면 repository-wide 탐색으로 복구하지 않고 evidence 부족으로 BLOCK한다.

## 4. Kanban 생성

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
CLI fallback
```

## 5. 원칙

- 큰 파일을 임의의 MB threshold로 제외하지 않는다.
- 불필요한 전체 저장소 scan 자체를 생략한다.
- 실제 작업 파일이 크더라도 task scope에 포함되면 correctness 검증 대상이다.
- 대형 Windows bind mount에서는 repository-wide EOL/untracked 탐색을 정상 경로에서 반복하지 않는다.
- full diagnostic이 필요하면 명시적으로 실행하고 timing 값으로 병목을 조사한다.
