---
name: dev-project-bootstrap
description: 기존 Git Repository를 Hermes Project로 idempotent하게 등록하고, 개발환경 preflight·공유 Kanban Board·Profile Binding·Context·.hermes/project.yaml을 보장한다. resolver 값은 사용자가 직접 관리한다.
version: 0.3.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, project, bootstrap, kanban, context, orchestration, resolver, preflight, eol]
    requires_tools: [terminal]
---

# dev-project-bootstrap

**이미 존재하는 Git Repository**를 표준 Hermes 개발 Workflow에 사용할 수 있도록 준비한다.

이 Skill은 idempotent하게 동작한다.

- 개발환경 preflight를 먼저 실행한다.
- Repository가 실제로 쓰기 가능한지 확인한다.
- Gradle/Maven 프로젝트면 Java/Javac 사용 가능 여부를 확인한다.
- `.gitattributes`의 Hermes 권장 EOL 규칙을 보장한다.
- 이미 유효한 Project/Board 상태는 재사용한다.
- 빠진 Hermes 상태만 생성한다.
- 충돌하는 Identity 또는 EOL 정책은 Block한다.
- 사용자가 관리하는 Resolver Metadata는 보존한다.
- Legacy/Source-specific Metadata도 보존한다.

이 Skill은 Application Repository 자체를 새로 만드는 기능이 아니다.

---

# 1. 책임 범위

`dev-project-bootstrap`은 Project Infrastructure와 Hermes 개발 준비 상태를 관리한다.

```text
Git repository validation
Development environment preflight
Workspace write validation
Java toolchain validation for Gradle/Maven projects
.gitattributes EOL policy ensure
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
JDK/Gradle/Maven installation at task time
tracked-file mass renormalization
```

JDK와 공통 개발 도구는 DevKit Docker image가 제공해야 한다. Gradle/Maven 프로젝트는 전역 설치본보다 Repository의 `gradlew`/`mvnw`를 우선한다.

---

# 2. Development Environment Preflight

Project/Board를 변경하기 전에 다음을 검사한다.

```text
1. git / python3 존재
2. --repo가 정확한 Git root인지 확인
3. Repository root에 임시 파일을 생성/삭제해 write 가능 여부 확인
4. Gradle/Maven 프로젝트 유형 감지
5. Gradle/Maven 프로젝트이면 java / javac 확인
6. .gitattributes 생성/보강
7. gradlew/mvnw 현재 EOL 확인
```

Preflight 실패 시 Project/Board Bootstrap을 시작하지 않는다.

실행:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/dev_environment_preflight.py" \
  --repo "/workspace/dashboard"
```

일반 Bootstrap에서는 직접 실행하지 않고 `bootstrap.py` launcher가 먼저 호출한다.

---

# 3. `.gitattributes` 정책

Repository에 다음 규칙을 보장한다.

```gitattributes
gradlew text eol=lf
mvnw text eol=lf
*.sh text eol=lf
*.bat text eol=crlf
*.cmd text eol=crlf
```

처리 규칙:

```text
.gitattributes 없음
  -> 생성

파일 있음 + 필요한 규칙 없음
  -> 기존 내용 보존 후 필요한 규칙만 추가

같은 pattern에 충돌하는 eol 규칙 존재
  -> 자동 덮어쓰기 금지
  -> Bootstrap Block
```

`git add --renormalize .` 같은 전체 Repository renormalize는 자동 실행하지 않는다.

이미 checkout된 `gradlew`/`mvnw`가 CRLF이면 경고만 출력한다. Repository 정책 변경과 기존 tracked file의 대량 변경을 하나의 Bootstrap 작업에서 섞지 않는다.

---

# 4. 표준 결과

성공 후 Repository:

```text
<repo>/
├─ .gitattributes
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

# 5. Canonical `.hermes/project.yaml`

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

Bootstrap 관리 영역:

```text
version
project
kanban
git
profiles
```

사용자 관리 영역:

```text
resolver
```

Bootstrap은 `resolver:` Section이 없을 때만 빈 Skeleton을 생성한다. 그 이후 Resolver 값은 사용자가 직접 관리한다.

---

# 6. Source-specific Metadata

Bootstrap은 다음 Section을 새로 만들지 않는다.

```yaml
jira:
```

또는:

```yaml
work_sources:
```

기존 Managed `project.yaml`에 Legacy/Source-specific Section이 이미 있으면 Additional Top-level Metadata로 그대로 보존한다.

---

# 7. 입력

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

Resolver 값은 사용자가 `.hermes/project.yaml`에서 직접 관리한다.

---

# 8. 실행

일반 실행은 반드시 launcher를 사용한다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/bootstrap.py" \
  --repo "/workspace/dashboard"
```

명시 실행:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/bootstrap.py" \
  --repo "/workspace/xcomm-server-jre17" \
  --project-id "xcomm-server-jre17" \
  --name "XCommServer" \
  --board "xcomm-server-jre17" \
  --base "dev"
```

`bootstrap.py` 실행 순서:

```text
dev_environment_preflight.py
        ↓ success
bootstrap_project.py
```

`dev-workflow-orchestrate`에서 Managed Project가 아닌 Repository를 Bootstrap할 때는 사용자가 정확한 Repository를 명시했고 Bootstrap을 승인한 경우에만 호출한다.

---

# 9. Repository 검증 / Block 조건

다음 경우 중단한다.

- Repo Path가 절대경로가 아님
- Path가 존재하지 않음
- Git Repository Root가 아님
- Repository가 Hermes runtime user에게 writable하지 않음
- Gradle/Maven 프로젝트인데 `java` 또는 `javac`가 없음
- `.gitattributes`에 Hermes EOL 정책과 충돌하는 규칙이 있음
- 요청 Base가 Commit으로 Resolve되지 않음
- Common Context Source가 없음
- 기존 Managed Core Metadata가 요청 Identity와 충돌
- 기존 Hermes Project ID가 다른 Repository를 가리킴
- 필수 Profile이 없음
- Hermes CLI 동작 실패

Java/JDK가 없을 때 Agent가 작업 중 JDK를 다운로드하거나 Windows host Java를 탐색해서 우회하지 않는다. DevKit image를 수정한 뒤 재실행한다.

---

# 10. Kanban / Project Ensure

Board:

- 기존 Board가 있으면 재사용
- 없으면 생성
- Bootstrap 중 삭제/이름변경 금지

필수 Role Profile마다:

- Profile 존재 확인
- Project가 없으면 생성
- Primary Repository 검증
- Shared Board Binding
- Repository Identity Conflict는 Block

---

# 11. Context File

Repository Root의 Context는 다음 우선순위로 선택한다.

```text
.hermes.md
HERMES.md
AGENTS.md
CLAUDE.md
.cursorrules
```

없으면 `AGENTS.md`를 생성한다.

Managed Block 밖의 기존 내용은 보존한다.

---

# 12. Metadata 보존 계약

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

# 13. 안전 규칙

절대 하지 않는다.

- Application Source Code 임의 수정
- `.gitattributes` 충돌 정책 자동 덮어쓰기
- 전체 Repository 자동 renormalize
- Task 중 JDK/Gradle/Maven 임의 설치
- Resolver 값 자동 추론
- Resolver 생성을 위한 Source Scan
- Source-system Mapping 자동 생성
- Project/Board 삭제
- Git reset/clean/checkout/rebase/merge/commit
- Unmanaged Metadata 덮어쓰기
- Legacy/Custom Top-level Metadata 삭제

예외적으로 `.gitattributes`는 Hermes 개발환경 호환성을 위해 Bootstrap 관리 대상이며, 기존 내용은 보존하고 필요한 비충돌 규칙만 추가한다.

---

# 14. 예상 출력

Preflight:

```text
BUILD_TYPE=gradle|maven|other
GITATTRIBUTES=created|updated|unchanged|skipped
WARNINGS=0
PREFLIGHT_STATUS=ready
```

Bootstrap 성공:

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

# 15. 권장 검증

신규/기존 Repository 모두 다음을 확인한다.

```text
workspace write probe succeeds
java/javac available for Gradle/Maven
.gitattributes rules are idempotent
existing .gitattributes contents are preserved
conflicting EOL rule blocks without overwrite
gradlew/mvnw CRLF is reported without mass renormalization
existing Project/Board reused
resolver values preserved
legacy/custom metadata preserved
no duplicate Project/Board
```
