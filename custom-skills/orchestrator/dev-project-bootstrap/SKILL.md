---
name: dev-project-bootstrap
description: 기존 Git Repository를 Hermes Project로 idempotent하게 등록하고, 공유 Kanban Board·Profile Binding·Context·.hermes/project.yaml을 보장한다. resolver 값은 사용자가 직접 관리한다.
version: 0.2.1
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, project, bootstrap, kanban, context, orchestration, resolver]
    requires_tools: [terminal]
---

# dev-project-bootstrap

**이미 존재하는 Git Repository**를 표준 Hermes 개발 Workflow에 사용할 수 있도록 준비한다.

이 Skill은 idempotent하게 동작한다.

- 이미 유효한 Project/Board 상태는 재사용한다.
- 빠진 Hermes 상태만 생성한다.
- 충돌하는 Identity는 Block한다.
- 사용자가 관리하는 Resolver Metadata는 보존한다.
- Legacy/Source-specific Metadata도 보존한다.
- Application Source Code는 수정하지 않는다.

이 Skill은 Application Repository 자체를 새로 만드는 기능이 아니다.

---

# 1. 책임 범위

`dev-project-bootstrap`은 Project Infrastructure만 관리한다.

```text
Git repository validation
Hermes Project registration
Kanban Board ensure
Profile bindings
Common/project context managed blocks
Core .hermes/project.yaml metadata
Resolver skeleton ensure
```

외부 Work Source 설정은 관리하지 않는다.

Bootstrap 범위 밖:

```text
Jira configuration
Notion configuration
Slack configuration
source project-key mappings
Work Item fetching
repository resolution
implementation analysis
```

이 영역은 `dev-work-intake`, `dev-project-resolve` 등 별도 Skill 책임이다.

---

# 2. 표준 결과

성공 후 Repository:

```text
<repo>/
├─ <active context file>
└─ .hermes/
   └─ project.yaml
```

Hermes 상태:

```text
Shared Kanban
└─ <board>

orchestrator
└─ Project <project-id> → <repo> → <board>

coder
└─ Project <project-id> → <repo> → <board>

reviewer
└─ Project <project-id> → <repo> → <board>
```

공통 정책 Source:

```text
/opt/data/shared/AGENTS.common.md
```

---

# 3. Canonical `.hermes/project.yaml`

신규 Managed Project의 기본 구조:

```yaml
# managed-by: dev-project-bootstrap
version: 2

project:
  id: dashboard
  name: dashboard
  repository: /workspace/dashboard

kanban:
  board: dashboard

git:
  default_base_branch: dev
  worktree_root: /workspace/.worktrees/dashboard

profiles:
  orchestrator: orchestrator
  coder: coder
  reviewer: reviewer

resolver:
  aliases: []
  modules: []
  files: []
  paths: []
```

Section별 소유권이 다르다.

## Bootstrap 관리 영역

```text
version
project
kanban
git
profiles
```

Bootstrap이 필요한 경우 이 값을 수렴시킬 수 있다.

## 사용자 관리 영역

```text
resolver
```

Bootstrap은 `resolver:` Section이 없을 때만 빈 Skeleton을 생성한다.

그 이후 값은 **사용자가 직접 편집**한다.

예:

```yaml
resolver:
  aliases:
    - XCommServer
    - xcomm-server

  modules:
    - XCommServer

  files:
    - properties.cfg

  paths: []
```

재실행 시 Bootstrap은 Resolver 값을 추론·추가·삭제·정렬·교체하지 않는다.

---

# 4. Source-specific Metadata

Bootstrap v0.2.x는 다음 Section을 새로 만들지 않는다.

```yaml
jira:
```

또는:

```yaml
work_sources:
```

기존 Managed `project.yaml`에 Legacy/Source-specific Section이 이미 있으면 Additional Top-level Metadata로 그대로 보존한다.

예:

```yaml
jira:
  project_keys:
    - POBA
```

Bootstrap 재실행 시 이 값을 삭제하지 않고, 새로운 Jira Mapping도 만들지 않는다.

Source-specific Migration이 필요하면 별도 명시적 Workflow에서 수행한다.

---

# 5. 입력

필수:

```text
repo_path
```

선택:

```text
project_id
name
board
base_branch
profiles
orchestrator_profile
coder_profile
reviewer_profile
description
common_context
```

의도적으로 `--jira-key`나 Resolver 값 입력용 CLI Option은 제공하지 않는다.

Resolver 값은 사용자가 `.hermes/project.yaml`에서 직접 관리한다.

---

# 6. 실행

일반 실행:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/bootstrap_project.py" \
  --repo "/workspace/dashboard"
```

명시 실행:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/bootstrap_project.py" \
  --repo "/workspace/xcomm-server-jre17" \
  --project-id "xcomm-server-jre17" \
  --name "XCommServer" \
  --board "xcomm-server-jre17" \
  --base "dev"
```

`dev-workflow-orchestrate`에서 Managed Project가 아닌 Repository를 Bootstrap할 때는 **사용자가 정확한 Repository를 명시했고 Bootstrap을 승인한 경우에만** 호출한다.

---

# 7. Repository 검증

다음 경우 중단한다.

- Repo Path가 절대경로가 아님
- Path가 존재하지 않음
- Git Repository Root가 아님
- 요청 Base가 Commit으로 Resolve되지 않음
- Common Context Source가 없음
- 기존 Managed Core Metadata가 요청 Identity와 충돌
- 기존 Hermes Project ID가 다른 Repository를 가리킴
- 필수 Profile이 없음
- Hermes CLI 동작 실패

다른 Repository로 탐색 범위를 넓히지 않는다.

특히 아직 Initial Commit이 없어 Base Branch가 Commit으로 Resolve되지 않으면 Bootstrap이 Commit을 대신 생성하지 않는다.

---

# 8. Kanban / Project Ensure

Board:

- 기존 Board가 있으면 재사용
- 없으면 생성
- Bootstrap 중 삭제/이름변경 금지

Project State는 Profile별로 관리된다.

필수 Role Profile마다:

- Profile 존재 확인
- Project가 없으면 생성
- Primary Repository 검증
- Shared Board Binding
- Repository Identity Conflict는 Block

---

# 9. Context File

Repository Root의 Context는 다음 우선순위로 선택한다.

```text
.hermes.md
HERMES.md
AGENTS.md
CLAUDE.md
.cursorrules
```

없으면 다음을 생성한다.

```text
AGENTS.md
```

Managed Block:

```text
<!-- HERMES-COMMON:START -->
...
<!-- HERMES-COMMON:END -->
```

그리고:

```text
<!-- HERMES-PROJECT:START -->
...
<!-- HERMES-PROJECT:END -->
```

Managed Block 밖의 기존 내용은 보존한다.

Project Block에는 Resolver 값이 User-managed이며 자동 추론하면 안 된다는 정책을 포함한다.

---

# 10. Metadata 보존 계약

`.hermes/project.yaml`이 이미 있고 상단에 다음 Marker가 있으면:

```text
# managed-by: dev-project-bootstrap
```

Helper는:

1. Bootstrap-managed Top-level Section만 갱신한다.
2. 기존 `resolver:` Text를 그대로 보존한다.
3. Resolver가 없을 때만 빈 `resolver:`를 생성한다.
4. Unknown/Source-specific Top-level Section을 보존한다.
5. Legacy Jira Metadata를 Migration/Delete하지 않는다.
6. 보존된 User-managed Section 내부 순서를 바꾸지 않는다.

파일이 이 Skill의 Managed Marker를 갖고 있지 않으면 덮어쓰지 않고 거부한다.

---

# 11. Resolver Workflow

최초 Bootstrap:

```text
dev-project-bootstrap
        ↓
resolver skeleton:
  aliases: []
  modules: []
  files: []
  paths: []
```

그 후 사용자가 직접:

```text
.hermes/project.yaml
```

에 안정적인 Project Identity를 추가한다.

권장 값:

```text
aliases
modules
distinctive files
stable paths
```

단일 Ticket을 억지로 Match시키기 위한 일회성 Issue 문구나 Customer Name을 추가하지 않는다.

Resolver Metadata가 준비되면 `dev-project-resolve`가 Managed Project Metadata만을 기준으로 Work Item과 매칭한다.

---

# 12. 안전 규칙

절대 하지 않는다.

- Application Source 수정
- Resolver 값 자동 추론
- Resolver 생성을 위한 Source Scan
- Source-system Mapping 자동 생성
- Project/Board 삭제
- Git reset/clean/checkout/rebase/merge/commit
- Unmanaged Metadata 덮어쓰기
- Legacy/Custom Top-level Metadata 삭제

Project ID와 Board Slug는 안정적인 Identity로 취급한다.

---

# 13. 예상 출력

성공:

```text
PROJECT_ID=...
REPOSITORY=...
BOARD=...
BASE_BRANCH=...
WORKTREE_ROOT=...
CONTEXT_FILE=...
METADATA_FILE=...
PROFILES=...
RESOLVER_MODE=user-managed
STATUS=ready
```

---

# 14. 권장 검증

## 기존 프로젝트 재실행

예: `dashboard`

기대:

```text
existing Project reused
existing Board reused
existing resolver values preserved
legacy/custom metadata preserved
no duplicate Project/Board
```

## 신규 Managed Repository

실제 Git Repository 하나를 Bootstrap한다.

기대:

```text
.hermes/project.yaml created
resolver empty skeleton created
```

그 후 사용자가 `resolver:`를 수정하고 Bootstrap을 다시 실행한다.

기대:

```text
resolver values unchanged
```

이 보존 검증은 많은 Repository에 적용하기 전에 반드시 확인한다.
