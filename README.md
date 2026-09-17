# Hermes Agent DevKit

Windows + Docker Desktop 환경에서 Hermes Agent를 `orchestrator`, `coder`, `reviewer` 멀티 프로필로 운영하기 위한 개발 환경이다.

핵심 실행 구조는 다음과 같다.

```text
User
  ↓
Orchestrator
├─ Direct Flow    작고 명확한 단일 Work Unit
└─ Standard Flow  설계/분해/승인이 필요한 작업
      ↓
dev-workspace-dispatch
      ↓
Kanban
      ↓
Coder
      ↓
Reviewer DEFAULT
```

**모든 새 mutation request의 실행 진입점은 Orchestrator다.** Coder 대화 세션은 새 작업을 직접 수정하거나 self-dispatch하는 진입점으로 사용하지 않는다.

> [!WARNING]
> `docker compose down -v`는 일반 종료 명령이 아니다. Profile, OAuth, Session, Memory, Kanban 등을 포함한 `hermes-dev-data` volume을 삭제하는 완전 초기화 명령이다.

---

# 0. 사전 준비

- Windows 11 또는 Windows + Docker Desktop
- Docker Desktop 실행 상태
- Git
- PowerShell 5.1 이상
- 기본 Host Workspace: `D:\workspace`
- 저장소 통합 검증용 Git Bash 또는 WSL 권장

확인:

```powershell
docker version
docker compose version
```

---

# 1. 저장소 준비

```powershell
cd D:\workspace
git clone https://github.com/kwang-sub/hermes-agent-devkit.git
cd .\hermes-agent-devkit
git switch dev
```

주요 구조:

```text
hermes-agent-devkit
├─ Dockerfile
├─ compose.yml
├─ init-profiles.ps1
├─ update-devkit.ps1
├─ sample.env
├─ .hermes/
│  └─ project.yaml
├─ custom-skills/
│  ├─ orchestrator/
│  │  ├─ dev-direct-flow/
│  │  ├─ dev-workflow-orchestrate/
│  │  ├─ dev-project-resolve/
│  │  ├─ dev-project-bootstrap/
│  │  ├─ dev-breakdown/
│  │  └─ dev-workspace-dispatch/
│  ├─ coder/
│  │  ├─ dev-implement-plan/
│  │  └─ dev-review-cycle/
│  ├─ reviewer/
│  │  ├─ dev-code-review/
│  │  └─ dev-review-cycle/
│  └─ shared/
│     └─ capability skills
├─ shared/
│  ├─ AGENTS.common.md
│  └─ references/
└─ scripts/
   ├─ verify.sh
   ├─ check_direct_flow_contract.py
   └─ check_skill_contract.py
```

Host/Container 기본 mapping:

```text
D:\workspace
    ↓ bind mount
/workspace
```

`/opt/data`는 Profile/OAuth/Session/Kanban 등의 mutable runtime data를 보관하는 named volume이다.

---

# 2. `.env` 생성

처음 설치에서만:

```powershell
if (Test-Path .env) { throw ".env already exists; update it manually instead of overwriting it." }
Copy-Item sample.env .env
notepad .env
```

`.env`는 Git에 commit하지 않는다.

필수 Dashboard 값:

```dotenv
HERMES_DASHBOARD_USERNAME=admin
HERMES_DASHBOARD_PASSWORD=<strong-password>
HERMES_DASHBOARD_SECRET=<long-random-secret>
```

Workspace 기본값:

```dotenv
HERMES_HOST_WORKSPACE_PATH=D:/workspace
HERMES_CONTAINER_WORKSPACE_PATH=/workspace
```

검증된 Hermes image tag를 사용한다.

```dotenv
HERMES_BASE_IMAGE=nousresearch/hermes-agent:v2026.8.16.2
```

OpenAI-compatible API Server와 Jira는 필요할 때만 활성화한다.

> [!WARNING]
> `.env`, OAuth Token, API Token, Password, Cookie를 source, Kanban body, 로그, 채팅에 그대로 기록하지 않는다.

---

# 3. Docker 실행

구성 확인:

```powershell
docker compose config --quiet
```

최초 빌드/실행:

```powershell
docker compose up -d --build
```

일반 실행:

```powershell
docker compose up -d
```

상태:

```powershell
docker compose ps
```

> [!WARNING]
> Dockerfile/Compose에 `USER hermes`, `user: hermes`를 추가하지 않는다. 공식 이미지의 s6-overlay/root bootstrap이 `/opt/data`와 runtime을 초기화해야 한다. 대화형 Hermes 명령만 `docker exec --user hermes`로 실행한다.

---

# 4. Runtime 확인

Dashboard 기본 주소:

```text
http://127.0.0.1:9119
```

Hermes CLI:

```powershell
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes --help
```

Python/PyYAML:

```powershell
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/python -c "import yaml; print('PYTHON_OK')"
```

---

# 5. Profile 초기화

```powershell
.\init-profiles.ps1
```

생성/보장하는 Profile:

```text
orchestrator
coder
reviewer
```

역할별 External Skill root:

```text
orchestrator -> /opt/custom-skills/orchestrator + shared
coder        -> /opt/custom-skills/coder + shared
reviewer     -> /opt/custom-skills/reviewer + shared
```

역할은 다음처럼 분리한다.

```text
orchestrator
  새 mutation request intake
  Direct | Standard 분류
  승인 Gate
  Kanban dispatch

coder
  할당된 Kanban Task 구현
  verification
  Reviewer handoff

reviewer
  동일 Workspace read-only review
  approve / request changes / block
```

Profile 확인:

```powershell
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes profile list
```

PowerShell 실행 정책에 막힐 때만 현재 session에 한해:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\init-profiles.ps1
```

---

# 6. Model / OAuth 설정

각 Profile의 provider/model/OAuth를 설정한다.

```powershell
docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p orchestrator model
docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p coder model
docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p reviewer model
```

설정 확인:

```powershell
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p orchestrator config get model --json
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p coder config get model --json
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p reviewer config get model --json
```

## Coder 모델 정책

실행 시 Coder는 논리 등급만 승인받는다.

```text
DEFAULT
PREMIUM
```

실제 provider/model은 환경 설정에서 resolve하고 Task snapshot에 고정한다. Reviewer는 항상 Reviewer profile의 DEFAULT를 사용한다.

```text
Coder 승인 model/provider
    ↓ request_review
Reviewer DEFAULT
    ↓ changes_requested
승인 Coder model/provider 복원
```

자동 PREMIUM escalation은 금지한다.

## Fallback Provider

필요한 Profile에만 설정한다.

```powershell
docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p orchestrator fallback add
docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p coder fallback add
```

조회:

```powershell
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p orchestrator fallback list
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p coder fallback list
```

---

# 7. 저장소 통합 검증

Git Bash/WSL에서:

```bash
bash scripts/verify.sh
```

주요 검증:

- Context/Skill compact policy
- Custom Skill Python/frontmatter/reference contract
- **Orchestrator Direct Flow contract**
- Standard Work Unit contract
- Capability Lifecycle contract
- Infrastructure capability contract
- Coder Workspace verification
- Coder↔Reviewer Review Cycle
- Runtime/model/notification contract
- Gradle bounded verification/evidence reuse
- DevKit updater contract
- PowerShell syntax
- Docker Compose configuration

개별 Direct Flow 계약:

```bash
python3 scripts/check_direct_flow_contract.py
```

전체 성공 기준:

```text
[PASS] Repository verification completed.
```

GitHub Actions에서도 동일 회귀와 `direct-flow`, `standard-work-unit`, `capability-lifecycle`, `infrastructure-capability`, Latest Hermes compatibility를 검증한다.

---

# 8. 최초 구성 완료 확인

운영 진입점인 Orchestrator를 확인한다.

```powershell
docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p orchestrator chat
```

Coder/Reviewer Profile은 worker 역할이지만 설정 smoke test 목적으로 chat 시작 여부를 확인할 수 있다.

```powershell
docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p coder chat
docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p reviewer chat
```

**개발 작업 요청은 Orchestrator에 입력한다.** Coder chat에 새 mutation request를 직접 넣어 실행 경로로 사용하지 않는다.

최종 체크리스트:

```text
[ ] hermes-dev 실행/healthy
[ ] Dashboard 접속
[ ] Hermes CLI/Python 정상
[ ] orchestrator/coder/reviewer Profile 존재
[ ] 필요한 OAuth/Fallback 설정
[ ] scripts/verify.sh 통과
[ ] Orchestrator chat 실행 확인
```

---

# 9. 실제 개발 Workflow

사용자는 새 개발 요청을 항상 Orchestrator에 전달한다.

```powershell
docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p orchestrator chat
```

Orchestrator가 요청을 `DIRECT | STANDARD`로 분류한다.

## 9.1 Direct Flow

작고 명확한 단일 작업을 위한 planning shortcut이다.

```text
User
  ↓
Orchestrator
  ↓
Direct eligibility
  ↓
[실행 방식 선택]
  ↓
[Coder 모델 선택]
  ↓
Compact Plan
  ↓
[작업 계획 승인]
  ↓
dev-workspace-dispatch
  ↓
Kanban
  ↓
Coder
  ↓
Reviewer DEFAULT
```

Direct Flow 후보 조건:

```text
managed 단일 Project 명확
current workspace/current branch 사용
Work Unit Class = IMPLEMENTATION | REFACTOR
Work Unit Boundary = SINGLE_UNIT
작고 기존 패턴 기반 변경
요구사항 해석 하나
API Spec Gate = NOT_REQUIRED
Infrastructure Impact = NO
bounded targeted verification 가능
```

예:

- 작은 null/edge-case 버그
- 기존 validation 규칙의 국소 적용
- 메시지/로그 수정
- 기존 패턴 기반 작은 조건/계산 수정
- 테스트 케이스 보완
- 범위가 명확한 작은 refactor

Direct로 처리하지 않는 조건:

```text
DESIGN / MIGRATION Work Unit
DB schema/data migration/DBML 설계
public API 계약 의미 변경
dependency 추가/upgrade
Infrastructure runtime/host/network/container/env delivery 변경
security/authz/transaction/concurrency 정책 변경
architecture/common shared contract 결정
cross-repository 또는 의미 있는 multi-module 변경
요구사항 복수 해석
scope를 알기 위해 broad source 분석 필요
다른 workspace/new branch 필요
```

애매하면 Standard다.

Coder가 실제 source에서 Direct 경계를 넘는 필요사항을 발견하면 범위를 확대하지 않고:

```text
DIRECT_SCOPE_EXCEEDED
Required Flow: STANDARD
```

로 Block한다. Orchestrator가 Standard Flow/Requirement Delta로 재계획한다.

Direct도 Reviewer를 생략하지 않는다.

## 9.2 Standard Flow

설계/분해/승인 또는 복합 영향 분석이 필요한 작업에 사용한다.

```text
Request
  ↓
Orchestrator
  ↓
Project Resolve / Approval
  ↓
Bootstrap (필요 시)
  ↓
dev-breakdown
  ↓
Work Unit Boundary
  ↓
API Spec Gate (필요 시)
  ↓
Workspace / Branch / Coder Model Approval
  ↓
Plan Approval
  ↓
dev-workspace-dispatch
  ↓
Kanban
  ↓
Coder
  ↓
Reviewer DEFAULT
```

대표 Standard 작업:

- 신규 기능/대규모 변경
- 요구사항이 모호한 작업
- DESIGN/MIGRATION
- 여러 module/repository 영향
- public API 의미 변경
- DB schema/data migration
- dependency 변경
- Infrastructure topology/runtime 변경
- security/transaction/concurrency 정책 결정
- architecture 변경

## 9.3 Work Unit Boundary

Standard Flow의 한 Task는 하나의 주 Work Unit을 수행한다.

```text
DESIGN
IMPLEMENTATION
MIGRATION
REFACTOR
AUDIT
```

독립 승인 가능한 artifact가 다음 mutation 단계의 authoritative input이 되면 Task를 분리한다.

대표 예:

```text
Logical DB Model
→ 별도 MIGRATION Task

Architecture Decision
→ 별도 IMPLEMENTATION Task

AUDIT finding
→ 별도 IMPLEMENTATION/REFACTOR Task
```

여러 capability를 사용한다는 사실 자체는 Task 분리 근거가 아니다.

## 9.4 Data DESIGN → MIGRATION

DB 논리 설계와 물리 구현은 별도 Standard Task다.

DESIGN:

```text
Subject Area
responsibility / ownership / lifecycle
relationship / cardinality
logical key/nullability intent
DBML materialization
DBML guard
```

같은 Task에서 Flyway/Liquibase/DDL/JPA physical mapping을 만들지 않는다.

MIGRATION은 완료된 logical model을 입력으로 별도 Standard Flow에서 시작한다.

## 9.5 Capability Handoff

`dev-breakdown`/Direct compact plan은 필요한 `Applicable Skills`를 Task에 보존한다. `dev-workspace-dispatch`의 preflight가 Coder/Reviewer 사용 가능 여부를 검증한다.

Coder/Reviewer는 전체 skill을 무조건 로드하지 않고 실제 affected scope에 필요한 capability만 `skill_view()`한다.

Canonical capability lifecycle은 `custom-skills/shared/capability-lifecycle.json`과 CI가 검증한다.

## 9.6 Reviewer

Direct와 Standard 모두 동일 Review loop를 사용한다.

```text
Coder
  ↓ kanban_request_review
Reviewer DEFAULT
  ├─ APPROVED → done
  ├─ CHANGES_REQUESTED → original coder → re-review
  └─ BLOCKED → human/external input
```

Reviewer는 implementation source를 수정하지 않는다. Risk가 낮다는 이유로 Coder가 self-complete하지 않는다.

## 9.7 Requirement Delta

이미 승인/dispatch된 Task에 새로운 요구사항이 들어오면 Coder가 직접 범위를 늘리지 않는다.

```text
기존 Task 확인
→ Requirement Delta 정규화
→ [추가 요구사항 확인]
→ Work Unit/API/Plan 재평가
→ SAME_TASK_RESUME | FOLLOW_UP_TASK | REPLACEMENT_TASK
```

다른 Work Unit 또는 architecture/API/schema/Infrastructure 경계를 넘는 요구는 별도 Standard Flow로 분리한다.

---

# 10. 일반 운영

상태:

```powershell
docker compose ps
```

로그:

```powershell
docker compose logs -f hermes
```

중지/시작:

```powershell
docker compose stop
docker compose start
```

Runtime data 유지 재생성:

```powershell
docker compose down
docker compose up -d
```

Hermes 사용자 Shell:

```powershell
docker exec -it --user hermes hermes-dev sh
```

Profile 조회:

```powershell
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes profile list
```

---

# 11. DevKit 업데이트

기존 환경에 최신 DevKit을 적용할 때는 `update-devkit.ps1` 계약을 사용한다.

변경 전에는 현재 작업/브랜치 상태를 확인하고 사용자 변경을 덮어쓰지 않는다.

업데이트 후 최소 확인:

```powershell
.\update-devkit.ps1
```

저장소 변경 시 CI에서 반드시 다음을 검증한다.

```text
DevKit updater contract
update-devkit.ps1 PowerShell syntax
Latest Hermes compatibility
```

---

# 12. 특수 상황 / 문제 해결

## 12.1 기존 `.env`가 있는 경우

`sample.env`를 기존 `.env` 위에 강제 복사하지 않는다. 새 non-secret key만 수동 병합하고 기존 credential은 유지한다.

## 12.2 Hermes 데이터 완전 초기화

다음은 Profile/OAuth/Session/Memory/Kanban을 삭제한다.

```powershell
docker compose down -v
```

일반 종료에는 사용하지 않는다.

## 12.3 Workspace 경로 변경

Host 경로만 변경할 때:

```dotenv
HERMES_HOST_WORKSPACE_PATH=C:/Users/example/source
HERMES_CONTAINER_WORKSPACE_PATH=/workspace
```

Container path까지 변경하면 `.hermes/project.yaml`의 repository/worktree metadata를 새 경로 기준으로 Bootstrap하여 수렴시킨다.

## 12.4 Hermes base image 업그레이드

별도 branch에서 image tag 변경 → `scripts/verify.sh` → clean build/runtime smoke test → `init-profiles.ps1` → OAuth/Profile 확인 순으로 검증한다.

`latest`를 운영 기본값으로 사용하지 않는다.

## 12.5 API Server 활성화

필요할 때만:

```dotenv
HERMES_API_SERVER_ENABLED=true
HERMES_API_SERVER_HOST=0.0.0.0
HERMES_API_SERVER_KEY=<strong-api-key>
```

Host publish는 가능하면 loopback을 유지한다.

## 12.6 Jira 연동

필요할 때만 `.env`의 Jira URL/email/token을 설정한다. Credential을 source/Skill/Kanban/log에 기록하지 않는다.

## 12.7 Kanban Task가 실행되지 않음

```powershell
docker compose ps
docker compose logs --tail 200 hermes
```

Dashboard에서 해당 managed Project의 board/task 상태와 registration notification 상태를 확인한다. Direct/Standard 모두 `dev-workspace-dispatch`의 동일 dispatcher/notification Gate를 사용한다.

## 12.8 `ExitCode=127` / Hermes CLI 없음

절대 경로로 확인한다.

```powershell
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes --help
```

## 12.9 Docker build의 `CC ...` 로그

Git source compile 중 나타나는 정상 build 로그일 수 있다. 실제 error 없이 계속 진행되면 중단하지 않는다.

## 12.10 Dashboard가 열리지 않음

```powershell
docker compose ps
docker compose logs --tail 200 hermes
```

Dashboard username/password/secret 설정 여부를 로컬 `.env`에서 확인하되 값을 외부 로그에 출력하지 않는다.

---

# 13. 보안 및 운영 원칙

- `.env`, OAuth Token, API Token, Password, Cookie를 commit하지 않는다.
- Dashboard/API Host publish 기본값은 `127.0.0.1`을 유지한다.
- `/opt/data` volume 삭제는 Hermes 영속 상태 삭제를 의미한다.
- Custom Skill/shared policy bind는 read-only로 유지한다.
- Dockerfile/Compose의 s6 root bootstrap을 깨지 않는다.
- runtime 자동화는 `/opt/hermes/.venv/bin/hermes`, `/opt/hermes/.venv/bin/python` 절대경로를 우선한다.
- 새 mutation request는 Orchestrator에서 시작한다.
- Direct/Standard 모두 Kanban → Coder → Reviewer 단계를 유지한다.
- 구현 요청만으로 commit/push/PR/merge까지 자동 진행하지 않는다.
- destructive Git operation과 Workspace cleanup은 명시적 승인 없이 수행하지 않는다.

---

# 14. 자주 사용하는 명령

| 목적 | 명령 |
|---|---|
| 최초 빌드/실행 | `docker compose up -d --build` |
| 일반 실행 | `docker compose up -d` |
| 상태 확인 | `docker compose ps` |
| 로그 | `docker compose logs -f hermes` |
| Profile 초기화 | `.\init-profiles.ps1` |
| DevKit 업데이트 | `.\update-devkit.ps1` |
| Profile 목록 | `docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes profile list` |
| Fallback 추가 | `docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p <profile> fallback add` |
| Fallback 조회 | `docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p <profile> fallback list` |
| **개발 요청 진입점** | `docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p orchestrator chat` |
| Coder Profile smoke test | `docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p coder chat` |
| Reviewer Profile smoke test | `docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p reviewer chat` |
| Direct Flow 계약 검증 | `python3 scripts/check_direct_flow_contract.py` |
| 통합 검증 | `bash scripts/verify.sh` |
| 데이터 유지 종료 | `docker compose down` |
| **완전 초기화** | `docker compose down -v` |

---

## 핵심 원칙 요약

```text
새 개발 요청
→ Orchestrator
→ Direct 또는 Standard 분류

작고 명확한 단일 구현/리팩터링
→ Direct
→ compact approval
→ Kanban
→ Coder
→ Reviewer

설계/DB/API/Infrastructure/복합 작업
→ Standard
→ Breakdown + Work Unit + approvals
→ Kanban
→ Coder
→ Reviewer

Coder
→ 할당된 Kanban Task만 구현
→ self-dispatch / self-complete 금지

Reviewer
→ DEFAULT profile
→ source 수정 금지

publication
→ 별도 승인 전 commit/push/PR/merge 없음
```
