---
name: dev-project-resolve
description: 정규화된 Work Item을 .hermes/project.yaml이 있는 Hermes Managed Project Metadata에만 매칭한다. Source Code Scan이나 Unmanaged Repository 탐색은 하지 않으며 결과는 사용자 승인 전까지 후보일 뿐이다.
version: 0.2.1
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, project, resolver, workspace, metadata, orchestrator]
    related_skills: [dev-work-intake, dev-project-bootstrap, dev-breakdown, dev-workflow-orchestrate]
    requires_tools: [terminal]
---

# dev-project-resolve

정규화된 Work Item을 `/workspace` 아래의 하나 이상의 **Hermes Managed Project**와 매칭한다.

검색 범위는 다음 파일이 있는 프로젝트로 의도적으로 제한한다.

```text
.hermes/project.yaml
```

Unmanaged Repository나 Repository Source Code는 Scan하지 않는다.

이 Skill은 **orchestrator 전용 Read-only Resolver**다.

중요:

```text
RESOLVED_SINGLE / RESOLVED_MULTI
= Agent가 찾은 프로젝트 후보
≠ 사용자가 승인한 작업 대상
```

Resolver가 프로젝트를 추론했다면 `dev-workflow-orchestrate`는 반드시 사용자에게 확인받은 뒤 `dev-breakdown`으로 진행해야 한다.

---

# 1. Managed Project만 사용하는 이유

Workspace에는 현재 Hermes Workflow와 관계없는 Repository가 많이 있을 수 있다.

전체 Repository를 Scan하면:

- 불필요한 Latency
- 과도한 Filesystem Traversal
- 과도한 Context/Evidence 수집
- 관계없는 Project가 Candidate가 됨
- Resolution 결과가 불안정해짐

따라서 Resolver Boundary는 Managed Project Metadata다.

```text
/workspace/<project>/.hermes/project.yaml
```

이 파일이 있는 Project만 후보가 된다.

Unmanaged Repository는 완전히 무시한다.

---

# 2. 표준 흐름

```text
Work Source
    ↓
dev-work-intake (필요 시)
    ↓
Normalized Work Item
    ↓
dev-project-resolve
    ↓
only .hermes/project.yaml projects
    ↓
RESOLVED_SINGLE / RESOLVED_MULTI / BLOCKED
    ↓
사용자 Project Approval Gate
    ↓
dev-breakdown
```

이 Resolver는 Unknown Repository를 자동 Bootstrap하지 않는다.

Resolver가 읽는 대상은 이미 Managed Project이므로 정상 Resolution 뒤에 Bootstrap을 새로 수행할 필요는 없다. 단, 사용자가 명시한 Repository가 아직 Managed Project가 아니라면 별도의 사용자 승인 후 `dev-project-bootstrap`을 수행한다.

---

# 3. Candidate 탐색

기본 Workspace:

```text
/workspace
```

기본 Managed Project Layout:

```text
/workspace/dashboard/.hermes/project.yaml
/workspace/server/.hermes/project.yaml
/workspace/manager/.hermes/project.yaml
```

이 Metadata File만 읽는다.

명시적으로 제외:

```text
/workspace/.worktrees/**
```

다음은 Resolver가 검사하지 않는다.

```text
source files
pom.xml
build.gradle
package.json
README
Git history
repository contents
unmanaged Git repositories
```

---

# 4. `.hermes/project.yaml`이 Resolution Index

각 Managed Project는 안정적인 Project Identity를 기술해야 한다.

권장 구조:

```yaml
project:
  id: server
  name: server
  repository: /workspace/server

resolver:
  aliases:
    - wowsoft-server
    - backend-server

  modules:
    - scApi
    - XCommServer
    - XApprovalPushAPI
    - XAgentStatus

  files:
    - application.properties

  paths:
    - scApi
    - XCommServer

work_sources:
  jira:
    project_keys:
      - DSB

    components:
      - Backend

    labels:
      - backend
```

안정적인 Project Fact만 추가한다.

특정 Ticket 하나를 Resolve시키기 위해 임시 Issue 문구를 Metadata에 넣지 않는다.

Resolver 값은 `dev-project-bootstrap`이 자동 생성하지 않고 사용자가 직접 관리한다.

---

# 5. 중요 규칙: Source Project Key는 약한 근거

예:

```text
DSB-39
DSB = 대신저축은행 Jira project
```

이 정보만으로 Code Repository를 식별할 수 없다.

따라서:

```yaml
work_sources:
  jira:
    project_keys:
      - DSB
```

는 약한 Context Evidence로만 취급하며 단독으로 Repository를 Resolve하지 못한다.

좋은 Resolution:

```text
Work Item mentions XCommServer
+
project.yaml resolver.modules contains XCommServer
→ strong match
```

잘못된 Resolution:

```text
Jira key DSB
→ select server
```

절대 이렇게 처리하지 않는다.

---

# 6. 사용하는 Evidence

Resolver는 Normalized Work Item과 Metadata만 비교한다.

Strong Evidence:

```text
resolver.aliases
resolver.modules
resolver.files
resolver.paths
project.id
project.name
repository basename
explicit repository supplied by user
```

Supporting Evidence:

```text
work_sources.<source>.components
work_sources.<source>.labels
```

Weak / Non-resolving Evidence:

```text
work_sources.jira.project_keys
legacy jira.project_keys
```

v0.2.x에는 Code-content Evidence가 없다.

---

# 7. 입력 계약

권장 입력:

```text
/opt/data/work-items/jira/DSB-39.json
```

실행:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/project_resolve.py" \
  --work-item /opt/data/work-items/jira/DSB-39.json
```

명시적 Repository 선택:

```bash
--explicit-repository /workspace/server
```

Explicit Repository도 `.hermes/project.yaml`이 있는 Managed Project여야 한다.

Unmanaged Explicit Path는 거부한다.

사용자가 처음부터 정확한 Managed Project를 직접 지정했다면 `dev-workflow-orchestrate`가 Resolver 자체를 생략할 수 있다.

---

# 8. Resolution 상태

## `RESOLVED_SINGLE`

정확히 하나의 Managed Project가 충분한 Strong Metadata Evidence를 가진다.

이 결과는 **Candidate가 하나라는 뜻**이며 사용자 승인 완료를 의미하지 않는다.

## `RESOLVED_MULTI`

여러 Managed Project가 서로 다른 Strong Term에 독립적으로 Match한다.

예:

```text
DSB-39

server project.yaml:
  modules:
    - scApi
    - XCommServer

xorg-sync project.yaml:
  modules:
    - XOrgSyncTool

sso project.yaml:
  aliases:
    - 통합SSO
  files:
    - jdbc.properties

→ RESOLVED_MULTI
```

사용자가 실제 대상 Project를 선택해야 한다.

## `BLOCKED`

다음 경우:

- Managed Project Match 없음
- Jira/Source Project Key만 Match
- Candidate가 모호함
- Target Repository는 존재하지만 Hermes Managed가 아님
- Metadata가 불충분함

Source Code Scan으로 Fallback하지 않는다.

---

# 9. BLOCKED 처리

Managed Project가 Resolve되지 않으면:

```text
BLOCKED
REASON=no_managed_project_match
```

Orchestrator는 다음 취지로 보고한다.

```text
No registered Hermes project has sufficient metadata for this Work Item.

Possible actions:
1. identify the correct managed project and add stable resolver metadata;
2. bootstrap the intended repository first;
3. explicitly specify an already managed repository.
```

`/workspace`의 모든 Repository로 Search 범위를 자동 확대하지 않는다.

---

# 10. 출력

기본 Artifact:

```text
/opt/data/work-items/resolutions/<WORK-ID>.json
/opt/data/work-items/resolutions/<WORK-ID>.md
```

Console 예:

```text
WORK_ID=DSB-39
STATUS=RESOLVED_SINGLE
REASON=single_strong_managed_project
RESOLVED_COUNT=1
PROJECT_1=/workspace/server
PROJECT_1_ID=server
PROJECT_1_SCORE=...
MANAGED_PROJECTS_SCANNED=3
```

`STATUS=RESOLVED_SINGLE`이어도 다음 Workflow 단계는 Project Approval Gate다.

---

# 11. Side Effect 규칙

허용 Write:

```text
/opt/data/work-items/resolutions/**
```

절대 하지 않는다.

- Source Code 수정
- Repository Content 검사
- `.hermes/project.yaml` 수정
- Unmanaged Git Repository 탐색
- Branch/Worktree 생성
- Bootstrap
- Kanban Task 생성
- Jira/Notion/Slack 수정

---

# 12. 성능 경계

기본 탐색:

```text
/workspace/*/.hermes/project.yaml
```

표준 Workspace Layout에 맞춰 대형 Repository Recursive Scan을 피한다.

Managed Project를 의도적으로 중첩하는 경우:

```text
--project-depth 2
```

를 사용할 수 있다.

이 경우에도 `.hermes/project.yaml` Discovery만 수행하며 `.worktrees`는 계속 제외한다.

---

# 13. 검증 순서

```text
1. Managed project + module metadata match
   → RESOLVED_SINGLE

2. Multiple managed projects + distinct module metadata
   → RESOLVED_MULTI

3. Jira project key only
   → BLOCKED

4. Matching unmanaged repository exists
   → ignored, BLOCKED

5. /workspace/.worktrees/.../.hermes/project.yaml exists
   → ignored
```

추가 Workflow 검증:

```text
RESOLVED_SINGLE
→ 사용자에게 Project Candidate 제시
→ 승인 전 dev-breakdown 실행 금지
```

---

# 14. 설계 원칙

Workspace 자체가 Resolver Index가 아니다.

Resolver Index는:

```text
.hermes/project.yaml
```

이 구조는 Resolution을 다음 특성으로 유지한다.

- Bounded
- Deterministic
- Fast
- Reviewable
- Workspace Size와 독립적

자동 Resolution에 참여해야 하는 Project는 먼저 Hermes Managed Project가 되고, 사용자가 적절한 Stable Resolver Metadata를 추가해야 한다.

최종 작업 대상 선택권은 Resolver가 아니라 사용자에게 있다.
