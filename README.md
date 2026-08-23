# Hermes Agent DevKit

Windows + Docker Desktop 환경에서 Hermes Agent를 `orchestrator`, `coder`, `reviewer` 멀티 프로필로 운영하기 위한 개발 환경이다.

핵심 원칙은 다음과 같다.

- Windows 개발 Workspace를 컨테이너 `/workspace`에 bind mount한다.
- Hermes의 Profile/OAuth/Session/Memory/Kanban 상태는 `/opt/data` named volume에 영속화한다.
- 역할별 Custom Skill은 read-only bind mount로 제공한다.
- 컨테이너 시작은 공식 이미지의 s6-overlay/root bootstrap 계약을 유지한다.
- 대화형 Hermes 명령은 runtime `hermes` 사용자로 실행한다.
- 스크립트 자동화는 PATH 대신 `/opt/hermes/.venv/bin/hermes`와 `/opt/hermes/.venv/bin/python` 절대경로를 사용한다.

> `docker compose down -v`는 일반 종료 명령이 아니다. Profile, OAuth, Session 등을 포함한 `hermes-dev-data` volume을 삭제하는 **완전 초기화 명령**이다.

---

## 1. 구성

```text
Windows Host
│
├─ hermes-agent-devkit
│  ├─ Dockerfile
│  ├─ compose.yml
│  ├─ init-profiles.ps1
│  ├─ sample.env
│  ├─ custom-skills/
│  ├─ shared/
│  └─ scripts/
│
└─ D:\workspace
   └─ 개발 프로젝트들
        │
        ▼
Docker: hermes-dev
├─ /workspace                    bind
├─ /opt/custom-skills            bind, read-only
├─ /opt/data/shared              bind, read-only
└─ /opt/data                     named volume: hermes-dev-data
```

`/opt/data`는 Hermes 공식 Docker 이미지의 mutable runtime data 위치다. Profile, OAuth, Session, Memory, Kanban, Work Item 등이 이 volume에 보관된다.

---

## 2. 최초 환경 설정

PowerShell에서 저장소 루트로 이동한다.

```powershell
cd D:\workspace\hermes-agent-devkit
```

환경 파일을 만든다.

```powershell
if (Test-Path .env) { throw ".env already exists; update it manually instead of overwriting it." }
Copy-Item sample.env .env
notepad .env
```

`.env`는 Git에 commit하지 않는다.

### 필수 Dashboard 인증값

현재 Compose는 Dashboard를 baseline runtime으로 항상 활성화하며 Hermes의 non-loopback dashboard 보안 계약에 맞춰 username/password/secret을 필수로 요구한다.

최소 다음 값을 실제 `.env`에 설정한다.

```dotenv
HERMES_DASHBOARD_USERNAME=admin
HERMES_DASHBOARD_PASSWORD=<strong-password>
HERMES_DASHBOARD_SECRET=<long-random-secret>
```

Secret 예시는 PowerShell에서 다음처럼 생성할 수 있다.

```powershell
[Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
```

`sample.env`의 credential 필드는 의도적으로 비어 있다.

### Workspace 경로

기본값:

```dotenv
HERMES_HOST_WORKSPACE_PATH=D:/workspace
HERMES_CONTAINER_WORKSPACE_PATH=/workspace
```

다른 PC에서는 host path만 환경에 맞게 변경한다.

```dotenv
HERMES_HOST_WORKSPACE_PATH=C:/Users/example/source
```

`HERMES_CONTAINER_WORKSPACE_PATH`를 변경하면 기존 `.hermes/project.yaml`의 repository 경로와 달라질 수 있으므로 managed project metadata를 다시 bootstrap한다.

### Hermes base image

DevKit의 기본 Hermes release는 다음으로 고정한다.

```dotenv
HERMES_BASE_IMAGE=nousresearch/hermes-agent:v2026.8.16.2
```

이렇게 하면 서로 다른 PC에서 같은 DevKit commit을 build할 때 `latest` 이동으로 인한 차이를 줄일 수 있다. 완전히 immutable한 build가 필요한 시점에는 검증한 digest로 덮어쓴다.

예:

```dotenv
HERMES_BASE_IMAGE=nousresearch/hermes-agent@sha256:<verified-digest>
```

Hermes를 새 release로 올릴 때는 `HERMES_BASE_IMAGE` 기본값을 명시적으로 변경하고 `scripts/verify.sh`, Docker build, Profile 초기화 smoke test를 다시 수행한다.

### OpenAI-compatible API server

API server는 기본적으로 비활성화한다.

```dotenv
HERMES_API_SERVER_ENABLED=false
```

필요할 때만 활성화하고 key를 설정한다.

```dotenv
HERMES_API_SERVER_ENABLED=true
HERMES_API_SERVER_HOST=0.0.0.0
HERMES_API_SERVER_KEY=<strong-api-key>
```

Host publish 기본 주소는 `127.0.0.1`이므로 외부 네트워크에 직접 노출하지 않는다.

---

## 3. 이미지 빌드 및 실행

```powershell
docker compose up -d --build
```

상태 확인:

```powershell
docker compose ps
```

일반 재실행에서는 Dockerfile 변경이 없다면 다음으로 충분하다.

```powershell
docker compose up -d
```

### Hermes/Python runtime 확인

자동화에서는 login shell의 PATH에 의존하지 않는다.

```powershell
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes --help
```

```powershell
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/python -c "import yaml; print('PYTHON_OK')"
```

두 명령이 성공하면 Profile 초기화에 필요한 Hermes CLI와 PyYAML runtime이 준비된 것이다.

### SyntaxWarning compatibility patch

Docker build 중 `scripts/patch_hermes_syntax_warning.py`가 `/opt/hermes/hermes_cli/update_cmd.py`를 검사한다.

지원 상태:

```text
patched          과거 upstream의 알려진 venv\Scripts 경고를 수정
already-patched  동일 코드가 이미 escape 처리됨
not-needed       최신 upstream에서 해당 코드가 변경/제거됨
```

세 경우 모두 `SyntaxWarning`을 error로 취급하는 strict compile을 통과해야 build가 계속된다. 즉 특정 과거 문자열의 존재 자체가 아니라 **현재 upstream source가 strict compile 가능한지**를 최종 계약으로 사용한다.

---

## 4. Healthcheck와 Dashboard

Compose healthcheck는 Dashboard의 container-local `127.0.0.1:9119` listener readiness를 확인한다. API server `8642` 활성화 여부와 독립적이다.

```powershell
docker compose ps
```

상세 health 상태:

```powershell
docker inspect --format '{{json .State.Health}}' hermes-dev
```

Dashboard 기본 접속 주소:

```text
http://127.0.0.1:9119
```

`healthy`는 Dashboard listener가 준비됐음을 의미하며 Profile OAuth 또는 외부 LLM Provider까지 정상임을 보장하지 않는다.

---

## 5. 컨테이너 관리

중지:

```powershell
docker compose stop
```

재시작:

```powershell
docker compose start
```

컨테이너 재시작:

```powershell
docker compose restart
```

컨테이너/Compose network만 제거하고 runtime data 유지:

```powershell
docker compose down
```

Hermes 사용자 shell:

```powershell
docker exec -it --user hermes hermes-dev sh
```

---

## 6. Profile 초기화

최초 생성 또는 설정 복구 시:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\init-profiles.ps1
```

현재 PowerShell session에서 이미 script 실행이 허용된다면 두 번째 명령만 실행한다.

스크립트는 다음을 사전 검증한다.

- Docker CLI/daemon
- `hermes-dev` container 존재 및 Running 상태
- `/workspace`, `/opt/custom-skills`, `/opt/data/shared` bind mount
- `/opt/hermes/.venv/bin/hermes`
- `/opt/hermes/.venv/bin/python`
- PyYAML
- 역할별 Custom Skill directory
- `/opt/data/shared/AGENTS.common.md`

Mount 검사는 Docker Go Template을 사용하지 않고 `docker inspect` JSON을 PowerShell `ConvertFrom-Json`으로 파싱한다. 따라서 Windows PowerShell/Docker CLI의 quote escaping 차이에 의존하지 않는다.

생성/보장하는 Profile:

```text
orchestrator
coder
reviewer
```

External Skill 경로:

```text
orchestrator -> /opt/custom-skills/orchestrator
coder        -> /opt/custom-skills/coder
reviewer     -> /opt/custom-skills/reviewer
```

Profile config의 `skills.external_dirs`는 YAML scalar가 아니라 list로 저장한다.

```yaml
skills:
  external_dirs:
    - /opt/custom-skills/coder
```

기존 config 수정이 필요한 경우 timestamp backup 후 atomic replace하고, 저장 후 YAML 구조를 다시 검증한다.

스크립트는 idempotent하므로 재실행할 수 있다.

```powershell
.\init-profiles.ps1
.\init-profiles.ps1
```

---

## 7. Profile 명령

Profile 목록:

```powershell
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes profile list
```

상세:

```powershell
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes profile show orchestrator
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes profile show coder
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes profile show reviewer
```

Model/OAuth 설정:

```powershell
docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p orchestrator model
docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p coder model
docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p reviewer model
```

Chat:

```powershell
docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p orchestrator chat
docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p coder chat
docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p reviewer chat
```

OAuth 정보는 `/opt/data/profiles/<profile>/auth.json` 아래에 저장되며 named volume에 영속화된다.

---

## 8. 개발 Workflow

표준 역할 흐름:

```text
Request / Jira
    ↓
Orchestrator
    ↓
Project Resolve / Approval
    ↓
dev-breakdown
    ↓
Plan Approval
    ↓
Workspace / Branch Approval
    ↓
dev-workspace-dispatch
    ↓
Coder
    ↓
dev-implement-plan
    ↓
Reviewer
    ↓
dev-code-review
    ↓
Approve / Request Changes / Block
```

현재 신규 표준은 `dev-workspace-dispatch`다. `dev-worktree-dispatch`와 `dev-worktree-cleanup`은 과거 linked-worktree workflow 호환을 위한 legacy skill이므로 신규 작업에서 자동 선택하지 않는다.

`dev-workspace-dispatch`는 사용자가 승인한 current/create branch와 workspace를 인계한다. 자동 linked-worktree 생성은 신규 표준 workflow의 기본 동작이 아니다.

---

## 9. DevKit 자체 managed project metadata

이 저장소 자체도 Hermes로 관리할 수 있도록 다음 canonical metadata를 둔다.

```text
.hermes/project.yaml
```

기본 identity:

```text
Project ID: hermes-agent-devkit
Repository: /workspace/hermes-agent-devkit
Board: hermes-agent-devkit
Base Branch: dev
```

루트 `AGENTS.md`의 project block도 이 값과 일치해야 한다.

---

## 10. Jira

Jira 설정은 `.env`에서 제공한다.

```dotenv
JIRA_BASE_URL=
JIRA_EMAIL=
JIRA_API_TOKEN=
JIRA_API_VERSION=3
JIRA_ACCEPTANCE_CRITERIA_FIELDS=Acceptance Criteria,완료 조건,인수 조건
JIRA_INCLUDE_FIELD_NAMES=
JIRA_VERIFY_SSL=true
```

Credential을 source, Skill 문서, Kanban body 또는 로그에 기록하지 않는다.

현재 Compose는 Jira 값을 container process environment로 전달한다. 향후 Hermes의 skill-scoped `required_environment_variables`로 migration하면 credential exposure scope를 더 줄일 수 있다.

---

## 11. 완전 초기화

다음 경우에만 사용한다.

- Profile/OAuth/Session을 전부 제거하고 fresh 검증
- `/opt/data` 상태를 완전히 재생성
- 테스트 환경을 처음부터 재구성

삭제:

```powershell
docker compose down -v
```

삭제 대상에는 `hermes-dev-data`가 포함된다. `mssql-data` 등 Hermes와 관계없는 volume을 수동으로 삭제하지 않는다.

재구성:

```powershell
docker compose up -d --build
.\init-profiles.ps1
```

그 후 각 Profile의 Model/OAuth를 다시 설정한다.

---

## 12. 저장소 통합 검증

```bash
bash scripts/verify.sh
```

검증 항목:

- compact policy/context invariant
- Custom Skill Python compile
- Hermes SyntaxWarning compatibility helper self-test
- workspace dispatch regression tests
- coder workspace verification tests
- reviewer context tests
- coder/reviewer review-cycle contract
- project bootstrap metadata preservation
- project resolver tests
- breakdown shell syntax
- `sample.env` / Compose / init script environment contract
- `init-profiles.ps1`의 JSON inspect + absolute runtime path contract
- PowerShell syntax와 `.env` helper self-test (`pwsh`/`powershell` 사용 가능 시)
- Docker Compose configuration (`docker`/daemon 사용 가능 시)

실제 `.env`의 secret은 검증 출력에 표시하지 않는다. Compose 검증은 test placeholder credential을 process environment로 주입해서 수행한다.

GitHub Actions의 `.github/workflows/verify.yml`도 branch push와 pull request에서 동일한 repository verification을 실행한다.

---

## 13. 보안 및 운영 규칙

- `.env`, OAuth token, API token, password, cookie를 commit하지 않는다.
- Dashboard/API host publish 기본값은 `127.0.0.1`을 유지한다.
- Dashboard를 non-loopback container interface에 bind할 때 인증 provider를 반드시 설정한다.
- `docker compose config` 출력에는 secret이 render될 수 있으므로 외부 공유하지 않는다.
- `/opt/data` volume 삭제는 인증과 세션 삭제를 의미한다.
- Custom Skill과 shared policy bind는 read-only로 유지한다.
- Dockerfile/Compose에 `USER hermes` 또는 `user: hermes`를 지정해 공식 s6 root bootstrap을 깨지 않는다.
- runtime 자동화는 `/opt/hermes/.venv/bin/*` 절대경로를 우선한다.

---

## 자주 사용하는 명령

| 목적 | 명령 |
|---|---|
| 빌드/실행 | `docker compose up -d --build` |
| 일반 실행 | `docker compose up -d` |
| 상태 | `docker compose ps` |
| 로그 | `docker compose logs -f hermes` |
| Profile 초기화 | `.\init-profiles.ps1` |
| Profile 목록 | `docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes profile list` |
| Orchestrator | `docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p orchestrator chat` |
| Coder | `docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p coder chat` |
| Reviewer | `docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p reviewer chat` |
| 통합 검증 | `bash scripts/verify.sh` |
| 데이터 유지 종료 | `docker compose down` |
| 완전 초기화 | `docker compose down -v` |
