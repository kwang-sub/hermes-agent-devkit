# Hermes Agent DevKit

Windows + Docker Desktop 환경에서 Hermes Agent를 `orchestrator`, `coder`, `reviewer` 멀티 프로필로 운영하기 위한 개발 환경이다.

이 문서는 **처음 설치하는 사용자가 위에서 아래로 순서대로 실행하면 환경 구성이 끝나도록** 작성한다. 처음 설치라면 `0. 사전 준비`부터 `8. 최초 구성 완료 확인`까지 순서대로 진행하면 된다. 기존 환경 재사용, 완전 초기화, Workspace 변경, Hermes 버전 업그레이드처럼 일반 설치 흐름과 다른 작업은 뒤쪽의 **특수 상황 가이드**에서 별도로 다룬다.

## 처음 설치 순서

```text
0. 사전 준비
   ↓
1. 저장소 준비
   ↓
2. .env 생성 및 필수값 설정
   ↓
3. Docker 이미지 빌드 및 컨테이너 실행
   ↓
4. 컨테이너 / Dashboard / Runtime 확인
   ↓
5. Profile 초기화
   ↓
6. Profile별 Model / OAuth 설정
   ↓
7. 저장소 통합 검증
   ↓
8. 최초 구성 완료 확인
   ↓
9. 실제 개발 Workflow 사용
```

> [!WARNING]
> `docker compose down -v`는 일반 종료 명령이 아니다. Profile, OAuth, Session, Memory, Kanban 등을 포함한 `hermes-dev-data` volume을 삭제하는 **완전 초기화 명령**이다. 처음 설치 과정에서는 사용할 필요가 없다.

---

# 0. 사전 준비

처음 설치하기 전에 다음 항목을 준비한다.

- Windows 11 또는 Windows + Docker Desktop 사용 가능 환경
- Docker Desktop 실행 상태
- Git
- PowerShell 5.1 이상
- 개발 프로젝트를 둘 Host Workspace
  - 기본값: `D:\workspace`
- 저장소 통합 검증까지 실행하려면 Git Bash 또는 WSL 권장

Docker가 정상 동작하는지 확인한다.

```powershell
docker version
docker compose version
```

두 명령이 정상적으로 Client/Server 및 Compose 버전을 출력하면 다음 단계로 진행한다.

> [!NOTE]
> Docker CLI는 설치되어 있지만 `docker version`에서 daemon 연결 오류가 발생한다면 Docker Desktop을 먼저 실행한 뒤 다시 확인한다.

---

# 1. 저장소 준비

GitHub에서 DevKit을 clone한다.

```powershell
cd D:\workspace
git clone https://github.com/kwang-sub/hermes-agent-devkit.git
cd .\hermes-agent-devkit
```

현재 branch를 확인한다.

```powershell
git branch --show-current
```

기본 운영 branch는 `dev`를 사용한다.

```powershell
git switch dev
```

저장소의 주요 구조는 다음과 같다.

```text
hermes-agent-devkit
├─ Dockerfile
├─ compose.yml
├─ init-profiles.ps1
├─ sample.env
├─ .hermes/
│  └─ project.yaml
├─ custom-skills/
│  ├─ orchestrator/
│  │  ├─ dev-project-pattern/
│  │  ├─ dev-breakdown/
│  │  └─ dev-workspace-dispatch/
│  ├─ coder/
│  │  ├─ dev-fast-flow/
│  │  ├─ dev-implement-plan/
│  │  ├─ dev-spring-guidelines/
│  │  ├─ dev-spring-feature/
│  │  ├─ dev-spring-data/
│  │  ├─ dev-spring-test/
│  │  └─ dev-api-docs/
│  │     └─ references/
│  │        ├─ spring-openapi-reference.md
│  │        └─ postman-reference.md
│  └─ reviewer/
│     └─ dev-code-review/
├─ shared/
│  ├─ AGENTS.common.md
│  └─ references/
│     └─ project-pattern-rules.md
└─ scripts/
   └─ check_skill_contract.py
```

Host Workspace와 컨테이너의 기본 연결 구조는 다음과 같다.

```text
Windows Host
│
├─ D:\workspace\hermes-agent-devkit
│
└─ D:\workspace
   └─ 개발 프로젝트들
        │
        ▼
Docker Container : hermes-dev
├─ /workspace                    bind mount
├─ /opt/custom-skills            bind mount, read-only
├─ /opt/data/shared              bind mount, read-only
└─ /opt/data                     named volume: hermes-dev-data
```

`/opt/data`는 Hermes 공식 Docker 이미지의 mutable runtime data 위치다. Profile, OAuth, Session, Memory, Kanban, Work Item 등이 이 volume에 보관된다.

---

# 2. `.env` 생성 및 필수값 설정

처음 설치에서는 `sample.env`를 `.env`로 복사한 뒤 현재 PC에 맞게 수정한다.

```powershell
if (Test-Path .env) { throw ".env already exists; update it manually instead of overwriting it." }
Copy-Item sample.env .env
notepad .env
```

`.env`는 Git에 commit하지 않는다.

## 2.1 Dashboard 인증값 설정

현재 Compose는 Dashboard를 기본 runtime으로 항상 활성화한다. 따라서 다음 세 값은 반드시 설정한다.

```dotenv
HERMES_DASHBOARD_USERNAME=admin
HERMES_DASHBOARD_PASSWORD=<strong-password>
HERMES_DASHBOARD_SECRET=<long-random-secret>
```

Dashboard Secret은 PowerShell에서 다음처럼 생성할 수 있다.

```powershell
[Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
```

`sample.env`의 credential 필드는 의도적으로 비어 있으므로 실제 값은 로컬 `.env`에만 작성한다.

> [!WARNING]
> `.env`, Dashboard Password/Secret, OAuth Token, Jira API Token은 저장소에 commit하거나 채팅/로그에 그대로 출력하지 않는다.

## 2.2 Host Workspace 경로 확인

기본 설정은 다음과 같다.

```dotenv
HERMES_HOST_WORKSPACE_PATH=D:/workspace
HERMES_CONTAINER_WORKSPACE_PATH=/workspace
```

`D:\workspace`를 그대로 사용할 경우 수정할 필요가 없다.

다른 Host 경로를 사용한다면 **Host 경로만** 변경한다.

```dotenv
HERMES_HOST_WORKSPACE_PATH=C:/Users/example/source
```

컨테이너 내부 경로인 `/workspace`는 특별한 이유가 없다면 그대로 유지한다.

> [!NOTE]
> 이미 Hermes managed project를 사용 중인 상태에서 `HERMES_CONTAINER_WORKSPACE_PATH` 자체를 변경하면 기존 `.hermes/project.yaml`의 repository 경로와 달라질 수 있다. 이런 경우는 일반 설치 흐름이 아니므로 뒤쪽의 `특수 상황 3. Workspace 경로 변경` 절차를 따른다.

## 2.3 기본 Hermes 이미지 확인

DevKit은 `latest`가 아니라 검증한 release tag를 기본값으로 사용한다.

```dotenv
HERMES_BASE_IMAGE=nousresearch/hermes-agent:v2026.8.16.2
```

처음 설치에서는 이 값을 그대로 사용한다.

> [!NOTE]
> Hermes 버전을 올리거나 digest로 완전히 고정하려는 경우에는 처음 설치 중 임의로 값을 바꾸지 말고 뒤쪽의 `특수 상황 4. Hermes base image 업그레이드` 절차를 따른다.

## 2.4 선택 설정은 처음에는 그대로 둔다

OpenAI-compatible API Server는 기본적으로 비활성화되어 있다.

```dotenv
HERMES_API_SERVER_ENABLED=false
```

Jira도 credential을 입력하지 않으면 사용하지 않는다.

```dotenv
JIRA_BASE_URL=
JIRA_EMAIL=
JIRA_API_TOKEN=
```

처음 설치 목적이 Hermes 멀티 프로필 환경 구축이라면 이 값들은 그대로 두고 다음 단계로 진행한다.

> [!TIP]
> API Server 또는 Jira 연동이 필요하면 기본 Hermes 구성을 완료한 뒤 뒤쪽의 `특수 상황 5. API Server 활성화`, `특수 상황 6. Jira 연동` 절차를 적용하는 편이 문제를 분리하기 쉽다.

---

# 3. Docker 이미지 빌드 및 컨테이너 실행

`.env` 설정이 끝났으면 먼저 Compose 구성이 유효한지 확인한다.

```powershell
docker compose config --quiet
```

오류가 없다면 이미지를 빌드하고 컨테이너를 실행한다.

```powershell
docker compose up -d --build
```

처음 빌드에서는 Git 2.55.0을 source에서 compile하므로 `CC ...` 로그가 오래 표시될 수 있다. 이는 오류가 아니라 정상적인 Git build 과정이다.

컨테이너 상태를 확인한다.

```powershell
docker compose ps
```

기본적으로 다음 컨테이너가 실행되어야 한다.

```text
hermes-dev
```

> [!NOTE]
> Dockerfile 변경 없이 이미 build된 이미지를 다시 실행할 때는 이후부터 `docker compose up -d`만 사용해도 된다.

> [!WARNING]
> Dockerfile이나 Compose에 `USER hermes`, `user: hermes`를 추가하지 않는다. 공식 이미지의 s6-overlay/root bootstrap이 `/opt/data`와 Profile runtime을 초기화해야 하므로 컨테이너 시작은 root bootstrap 계약을 유지한다. 대화형 Hermes 명령만 `docker exec --user hermes`로 실행한다.

---

# 4. 컨테이너 / Dashboard / Runtime 확인

컨테이너가 실행되면 Profile을 만들기 전에 기본 runtime이 정상인지 확인한다.

## 4.1 Healthcheck 확인

```powershell
docker compose ps
```

상세 health 상태가 필요하면 다음 명령을 사용한다.

```powershell
docker inspect --format '{{json .State.Health}}' hermes-dev
```

Compose healthcheck는 Dashboard의 container-local `127.0.0.1:9119` listener readiness를 확인한다.

Dashboard 기본 접속 주소는 다음과 같다.

```text
http://127.0.0.1:9119
```

2단계에서 설정한 Dashboard 계정으로 로그인한다.

> [!NOTE]
> `healthy`는 Dashboard listener가 준비되었다는 뜻이다. Profile OAuth나 외부 LLM Provider 인증까지 정상이라는 의미는 아니다. 해당 검증은 뒤의 Profile 설정 단계에서 별도로 수행한다.

## 4.2 Hermes CLI 확인

자동화에서는 login shell의 PATH에 의존하지 않고 공식 이미지의 절대경로를 사용한다.

```powershell
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes --help
```

정상적으로 help가 출력되면 Hermes CLI가 준비된 것이다.

## 4.3 Python / PyYAML 확인

```powershell
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/python -c "import yaml; print('PYTHON_OK')"
```

다음이 출력되면 정상이다.

```text
PYTHON_OK
```

이 단계까지 정상이라면 Profile 초기화를 진행한다.

---

# 5. Profile 초기화

`init-profiles.ps1`은 다음 세 역할 Profile과 역할별 Custom Skill 연결을 생성 또는 보장한다.

```text
orchestrator
coder
reviewer
```

PowerShell에서 실행한다.

```powershell
.\init-profiles.ps1
```

스크립트는 Profile을 수정하기 전에 다음을 먼저 검사한다.

- Docker CLI / daemon
- `hermes-dev` 컨테이너 존재 및 Running 상태
- `/workspace` bind mount
- `/opt/custom-skills` bind mount
- `/opt/data/shared` bind mount
- `/opt/hermes/.venv/bin/hermes`
- `/opt/hermes/.venv/bin/python`
- PyYAML
- 역할별 Custom Skill directory
- `/opt/data/shared/AGENTS.common.md`

Mount 검사는 Docker Go Template을 사용하지 않고 `docker inspect` JSON을 PowerShell `ConvertFrom-Json`으로 파싱한다.

역할별 External Skill 경로는 다음과 같다.

```text
orchestrator -> /opt/custom-skills/orchestrator
coder        -> /opt/custom-skills/coder
reviewer     -> /opt/custom-skills/reviewer
```

Coder External Skill에는 workflow Skill과 Spring/API capability Skill이 함께 제공된다.

```text
dev-fast-flow
dev-implement-plan
dev-spring-guidelines
dev-spring-feature
dev-spring-data
dev-spring-test
dev-api-docs
```

Orchestrator는 복잡한 작업에서 `dev-breakdown`이 `skill_view("dev-project-pattern")`으로 프로젝트 패턴 Skill 본문을 명시적으로 로드한다. Coder worker는 Kanban의 `Applicable Skills`를 읽고 각 capability를 `skill_view()`로 실제 로드한 후 구현한다. Skill 이름/description만으로 세부 규칙을 추측하지 않는다.

각 Profile의 `skills.external_dirs`는 YAML scalar가 아니라 list로 저장된다.

```yaml
skills:
  external_dirs:
    - /opt/custom-skills/coder
```

기존 config에 변경이 필요한 경우 timestamp backup을 만든 뒤 atomic replace하고 저장 후 YAML 구조를 다시 검증한다.

스크립트는 idempotent하므로 정상적으로 한 번 실행된 뒤 다시 실행해도 된다.

```powershell
.\init-profiles.ps1
```

재실행 시 이미 정상인 항목은 `[OK]`로 처리되어야 한다.

> [!NOTE]
> PowerShell에서 `이 시스템에서 스크립트를 실행할 수 없으므로 ... ps1 파일을 로드할 수 없습니다`가 표시되는 경우에만 현재 PowerShell session에 한해 다음을 실행한다.
>
> ```powershell
> Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
> .\init-profiles.ps1
> ```
>
> `Scope Process`는 현재 PowerShell 창을 닫으면 원래 정책으로 돌아간다.

## 5.1 Profile 생성 결과 확인

```powershell
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes profile list
```

최소 다음 Profile을 확인한다.

```text
orchestrator
coder
reviewer
```

---

# 6. Profile별 Model / OAuth 설정

Profile 초기화가 끝났으면 각 역할에 사용할 Model과 OAuth 인증을 설정한다.

## 6.1 Orchestrator

```powershell
docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p orchestrator model
```

안내에 따라 Provider, Model, OpenAI Codex OAuth를 설정한다.

## 6.2 Coder

```powershell
docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p coder model
```

Coder에 사용할 계정과 Model을 설정한다.

## 6.3 Reviewer

```powershell
docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p reviewer model
```

Reviewer에 사용할 계정과 Model을 설정한다.

OAuth 정보는 다음 위치에 저장된다.

```text
/opt/data/profiles/<profile>/auth.json
```

이 파일은 `hermes-dev-data` named volume에 저장되므로 일반적인 컨테이너 재시작이나 `docker compose down`으로 삭제되지 않는다.

> [!WARNING]
> `auth.json`의 내용을 출력하거나 Git에 추가하지 않는다. OAuth 재인증이 필요하지 않은 일반적인 운영에서는 `hermes-dev-data` volume을 유지한다.

## 6.4 Model 설정 확인

```powershell
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p orchestrator config get model --json
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p coder config get model --json
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p reviewer config get model --json
```

세 Profile에서 의도한 Provider/Model이 확인되면 다음 단계로 진행한다.

## 6.5 선택 사항: GitHub Copilot Fallback Provider 설정

Primary Provider가 일시적으로 사용할 수 없을 때 다른 Provider/Model로 요청을 넘기려면 Profile별 Fallback Provider를 설정할 수 있다.

현재 DevKit의 권장 예시는 다음과 같다.

```text
orchestrator
  Primary  : OpenAI Codex
  Fallback : GitHub Copilot

coder
  Primary  : OpenAI Codex
  Fallback : GitHub Copilot

reviewer
  Primary  : GitHub Copilot 또는 별도 Reviewer Provider
```

Fallback은 Profile별 설정이므로 `orchestrator`, `coder`, `reviewer`에 각각 독립적으로 구성한다.

### Fallback 추가

Orchestrator에 Fallback을 추가한다.

```powershell
docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p orchestrator fallback add
```

Coder에 Fallback을 추가한다.

```powershell
docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p coder fallback add
```

대화형 선택 화면에서 `GitHub Copilot`과 사용할 Model을 선택한다. 해당 Provider 인증이 아직 없다면 안내에 따라 GitHub 인증을 진행한다.

> [!NOTE]
> GitHub Copilot 인증은 Hermes가 안내하는 GitHub OAuth/Device Code 흐름을 사용하는 것을 권장한다. 인증정보는 Profile의 Hermes runtime data에 저장되므로 Token을 README나 `.env`에 직접 기록하지 않는다.

### Fallback 설정 확인

```powershell
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p orchestrator fallback list
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p coder fallback list
```

짧은 alias가 지원되는 버전에서는 다음처럼 확인할 수도 있다.

```powershell
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p orchestrator fallback ls
```

설정 파일에서는 개념적으로 다음과 같은 구조를 가진다.

```yaml
fallback_providers:
  - provider: copilot
    model: <selected-model>
```

여러 Fallback을 등록한 경우 등록된 순서대로 대체 Provider를 시도한다.

### Fallback 제거

특정 Fallback을 제거하려면:

```powershell
docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p orchestrator fallback remove
```

전체 Fallback 설정을 비우려면:

```powershell
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p orchestrator fallback clear
```

Fallback 설정은 Primary Provider 자체를 변경하는 설정이 아니다. 정상 상태에서는 기존 Primary Provider를 먼저 사용하고, 해당 요청에서 Provider 오류나 rate limit 등으로 Primary 요청을 처리할 수 없을 때 등록된 Fallback 체인을 사용한다.

> [!WARNING]
> `docker compose down -v`로 `hermes-dev-data` volume을 삭제하면 Profile 설정과 인증정보도 함께 제거된다. 완전 초기화 후에는 Primary Model/OAuth뿐 아니라 필요한 Fallback Provider도 다시 설정한다.

---

# 7. 저장소 통합 검증

Docker runtime 구성이 끝났으면 DevKit 자체의 설정과 Skill 회귀 테스트를 실행한다.

Git Bash 또는 WSL에서 저장소 루트로 이동한 뒤 실행한다.

```bash
bash scripts/verify.sh
```

검증 항목은 다음과 같다.

- compact policy/context invariant
- Custom Skill Python compile
- **Custom Skill frontmatter/name/description/reference/progressive-disclosure contract**
- Hermes SyntaxWarning compatibility helper self-test
- Fast Flow task creation regression tests
- workspace dispatch regression tests
- coder workspace verification tests
- reviewer context tests
- coder/reviewer review-cycle contract
- project bootstrap metadata preservation
- project resolver tests
- breakdown shell syntax
- `sample.env` / Compose / init script environment contract
- `init-profiles.ps1` JSON inspect + absolute runtime path contract
- PowerShell syntax 및 `.env` helper self-test (`pwsh`/`powershell` 사용 가능 시)
- Docker Compose configuration (`docker`/daemon 사용 가능 시)

Skill metadata 검증은 다음 script가 담당한다.

```bash
python3 scripts/check_skill_contract.py
```

주요 검증 내용:

```text
SKILL.md frontmatter 존재
name/description 존재
name과 directory 이름 일치
duplicate skill name 없음
필수 capability skill 존재
OpenAPI/Postman local reference 존재
dev-breakdown의 dev-project-pattern skill_view 계약
dev-implement-plan의 capability skill_view 계약
```

마지막에 다음과 같은 메시지가 출력되면 repository-level 검증이 완료된 것이다.

```text
[PASS] Repository verification completed.
```

실제 `.env`의 Secret은 검증 출력에 표시하지 않는다. Compose 검증은 테스트용 placeholder credential을 process environment로 주입해서 수행한다.

GitHub Actions의 `.github/workflows/verify.yml`도 `dev`, `fix/**`, `feat/**`, `feature/**` push 및 pull request에서 동일한 검증을 실행한다.

> [!NOTE]
> Windows PowerShell만 사용하고 Git Bash/WSL이 없는 경우 이 단계는 나중에 수행할 수 있지만, DevKit 변경을 `dev`에 병합하거나 다른 PC에 배포하기 전에는 반드시 한 번 실행하는 것을 권장한다.

---

# 8. 최초 구성 완료 확인

여기까지 왔다면 설치 과정은 완료된 상태다. 마지막으로 실제 Agent가 실행되는지 각 Profile에서 간단히 확인한다.

## 8.1 Orchestrator 실행

```powershell
docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p orchestrator chat
```

## 8.2 Coder 실행

```powershell
docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p coder chat
```

## 8.3 Reviewer 실행

```powershell
docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p reviewer chat
```

각 Profile이 정상적으로 대화 세션을 시작하면 최초 구성이 완료된 것이다.

최종 체크리스트:

```text
[ ] docker compose ps에서 hermes-dev 실행
[ ] Dashboard http://127.0.0.1:9119 접속
[ ] Hermes CLI 정상
[ ] Python/PyYAML 정상
[ ] orchestrator Profile 존재 및 OAuth 설정
[ ] coder Profile 존재 및 OAuth 설정
[ ] reviewer Profile 존재 및 OAuth 설정
[ ] 필요한 Profile의 Fallback Provider 설정 확인 (선택)
[ ] scripts/verify.sh 통과
[ ] 각 Profile chat 실행 확인
```

---

# 9. 실제 개발 Workflow 사용

DevKit은 작업 크기에 따라 **Fast Flow**와 **Standard Flow** 두 가지 흐름을 사용한다.

```text
                         ┌─ 작고 명확한 작업 ─────────────┐
User Request ────────────┤                               ↓
                         │                         Coder intake
                         │                               ↓
                         │                       Kanban self-dispatch
                         │                               ↓
                         │                          Coder worker
                         │                               ↓
                         │                     capability skill_view
                         │                               ↓
                         │                            Reviewer
                         │
                         └─ 분석/설계가 필요한 작업
                                         ↓
                                   Orchestrator
                                         ↓
                                Project Resolve
                                         ↓
                             dev-project-pattern
                                         ↓
                                    Breakdown
                                         ↓
                                     Approval
                                         ↓
                               Workspace Dispatch
                                         ↓
                       Pattern/Applicable Skills 보존
                                         ↓
                                      Coder
                                         ↓
                             capability skill_view
                                         ↓
                                    Reviewer
```

두 Flow 모두 최종 구현과 Review 기록은 Kanban에 남긴다. 차이는 **작은 작업에서 Orchestrator의 project resolve/breakdown/approval 단계를 생략할 수 있는가**이다.

## 9.1 Fast Flow — Coder에게 직접 요청

Fast Flow는 다음 구조다.

```text
User
  ↓
Coder interactive chat
  ↓
dev-fast-flow
  ↓
Coder가 Kanban Task 등록
  ↓
Gateway dispatcher
  ↓
Coder worker / dev-implement-plan
  ↓
Project Pattern 확인 + capability skill_view
  ↓
Reviewer / dev-code-review
  ↓
Approve / Request Changes / Block
```

사용자는 Kanban CLI를 직접 입력하지 않는다. Coder 대화에 일반적인 개발 요청처럼 작업 내용을 설명한다.

Coder 실행:

```powershell
docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p coder chat
```

요청 예:

```text
/workspace/sample-api 프로젝트에서
UserService의 null 입력 시 발생하는 NPE를 수정해줘.
정상 입력 동작은 유지하고 관련 테스트도 확인해줘.
간단한 작업이면 Fast Flow로 진행해줘.
```

Coder interactive session은 요청을 확인한 뒤 다음 순서로 처리한다.

```text
1. 대상 managed project 확인
2. Fast Flow 적용 가능 여부 판단
3. clean current branch인지 확인
4. Goal / Acceptance Criteria / 최소 구현 단계 / Test Plan 작성
5. dev-fast-flow helper로 Kanban Task 생성
6. assignee=coder, reviewer=reviewer 계약 저장
7. interactive session은 source를 직접 수정하지 않고 종료
8. Gateway dispatcher가 coder worker 실행
9. worker가 project pattern을 확인하고 필요한 capability Skill 본문을 skill_view로 로드
10. 구현/검증 후 reviewer에게 request_review
```

> [!NOTE]
> `Coder가 Kanban을 등록하고 작업한다`는 의미는 **같은 Coder profile이 intake와 implementation 역할을 이어서 담당한다**는 뜻이다. 다만 Kanban lifecycle을 보존하기 위해 interactive chat process가 코드를 직접 수정하는 것이 아니라, 생성된 Task를 Gateway가 동일 `coder` profile의 worker process로 다시 실행한다.

Fast Flow Task에는 최소 다음 계약이 저장된다.

```text
Flow: FAST
Task Key
Goal
Acceptance Criteria
Implementation Tasks
Test Plan
Known Risks
Workspace
Expected Branch
Base SHA
Reviewer Profile
```

### Fast Flow에 적합한 작업

- 작은 버그 수정
- null/edge-case 처리
- 기존 패턴 기반 Validation 추가
- 로그/메시지 변경
- 작은 설정 수정
- 기존 Repository/Query 패턴의 단순 수정
- 테스트 케이스 보완
- 오타/문서/주석 수정
- 범위가 명확한 작은 리팩터링

Fast Flow의 기본 전제는 다음이다.

```text
단일 managed Repository
clean workspace
현재 branch 사용
작고 명확한 요구사항
기존 패턴으로 해결 가능
Reviewer의 검증 기준이 명확함
```

### Fast Flow에서 Standard Flow로 승격

Coder intake 단계에서 다음 조건이 보이면 Task를 Fast Flow로 생성하지 않는다.

```text
대상 Project가 모호함
dirty workspace
새 branch/worktree 결정 필요
신규 기능 설계
여러 Repository 영향
Public API 변경
DB Schema/Migration 변경
Dependency 추가/Upgrade
Architecture/Transaction/Concurrency 정책 결정
요구사항 해석이 여러 가지
```

또한 intake에서는 단순해 보였지만 Coder worker가 실제 source를 읽은 뒤 범위가 커진 것을 발견할 수 있다.

이 경우 구현 범위를 임의로 넓히지 않고 Kanban을 다음 이유로 Block한다.

```text
FAST_FLOW_ESCALATION_REQUIRED
```

그리고 확인한 Evidence와 Standard Flow에서 결정해야 할 항목을 남긴다. 이후 Orchestrator에서 해당 작업을 다시 분석한다.

## 9.2 Standard Flow — Orchestrator부터 시작

신규 기능, 복잡한 버그, 설계/분해가 필요한 작업은 기존 Standard Flow를 사용한다.

```text
Request / Jira
    ↓
Orchestrator
    ↓
Project Resolve
    ↓
Project Approval
    ↓
dev-project-bootstrap (필요 시)
    ↓
dev-breakdown
    ↓
skill_view("dev-project-pattern")
    ↓
Project Pattern Summary / Applicable Skills
    ↓
Plan Approval
    ↓
Workspace / Branch Approval
    ↓
dev-workspace-dispatch
    ↓
Kanban에 Pattern References / Applicable Skills 보존
    ↓
Coder / dev-implement-plan
    ↓
Applicable Skills를 skill_view로 로드
    ↓
Reviewer / dev-code-review
    ↓
Approve / Request Changes / Block
```

Orchestrator 실행:

```powershell
docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p orchestrator chat
```

Standard Flow는 다음 작업에 적합하다.

- 신규 기능
- 요구사항이 모호한 작업
- 여러 module/repository 작업
- Public API 변경
- DB Schema/Migration
- Dependency 추가/Upgrade
- 대규모 리팩터링
- Architecture 변경
- 여러 구현 Task로 나눠야 하는 작업

### Standard Flow Skill Handoff

`dev-breakdown`은 최소 다음을 계획에 남긴다.

```text
Project Pattern Summary
Pattern References
Applicable Skills
Pattern Conflicts
Improvement Candidates
```

`dev-workspace-dispatch`는 이 값을 Kanban body에 그대로 보존한다. Coder는 `Applicable Skills`를 canonical handoff로 사용하며, 각 Skill을 `skill_view()`로 실제 로드한다. 실제 source evidence에서 명백한 누락이 발견될 때만 Coder가 capability를 추가 감지한다.

Spring 프로젝트에서는 기본적으로 다음 후보를 사용한다.

```text
dev-spring-guidelines
  Spring 공통 convention / response / transaction

dev-spring-feature
  Controller / Service / DTO / Validation / Exception

dev-spring-data
  JPA / DataJPA / QueryDSL / Entity / Repository / Converter

dev-spring-test
  Spring/JPA test

dev-api-docs
  OpenAPI / Swagger / Postman
```

JPA query 기본 우선순위는 다음이다.

```text
단순 조회 → Spring Data JPA Method Query
복잡/동적 조회 → QueryDSL
Native Query → 앞 두 방식으로 해결하기 어려운 근거가 있을 때만
```

API 응답은 대상 프로젝트의 기존 공통 Response 규격을 우선한다.

## 9.3 API 문서화 Reference

`dev-api-docs`는 외부 예시 저장소를 매 작업마다 다시 읽지 않고 local reference를 사용한다.

```text
custom-skills/coder/dev-api-docs/references/
├─ spring-openapi-reference.md
└─ postman-reference.md
```

Spring OpenAPI reference는 `backend-lab-archive/level-up-backend-gpt/level2-book-management-system`에서 합의한 다음 패턴을 요약한다.

```text
@Tag
@Operation
API별 ErrorCode example
GroupedOpenApi
OperationCustomizer
실제 인증 방식에 맞는 SecurityScheme
```

예시 프로젝트의 `ResponseEntity<DTO>`는 기본 응답 규격으로 복제하지 않는다. 대상 프로젝트에 공통 Response wrapper가 있으면 OpenAPI/Postman도 해당 contract를 사용한다.

## 9.4 Workspace / Branch 전략

Standard Flow의 `dev-workspace-dispatch`는 다음 전략을 지원한다.

```text
현재 workspace + 현재 branch
현재 workspace + 새 branch
사용자가 지정한 별도 workspace + 현재 branch
사용자가 지정한 별도 workspace + 새 branch
```

Fast Flow는 의도적으로 범위를 단순하게 유지하기 위해 다음만 지원한다.

```text
clean current workspace + current branch
```

새 branch 또는 별도 workspace가 필요하다면 Standard Flow를 사용한다.

`dev-worktree-dispatch`, `dev-worktree-cleanup`은 과거 linked-worktree workflow 호환을 위한 legacy skill이다. 신규 작업에서는 자동 선택하지 않는다.

## 9.5 Reviewer는 두 Flow 모두 유지

Fast Flow라고 해서 Review를 생략하지 않는다.

```text
Coder worker
   ↓
kanban_request_review
   ↓
Reviewer
   ├─ APPROVE → done
   ├─ REQUEST_CHANGES → original coder 재작업
   └─ BLOCKED → 사용자/외부 결정 필요
```

Reviewer는 implementation source를 직접 수정하지 않는다. Reviewer profile에 capability Skill이 실제 설치되어 있으면 `skill_view()`로 전체 계약을 읽고, profile 분리 때문에 Coder capability를 직접 로드할 수 없는 경우에는 Kanban에 보존된 Pattern/Applicable Skills 계약과 Coder handoff evidence를 기준으로 검증한다.

## 9.6 DevKit 자체 managed project

이 DevKit 저장소 자체도 Hermes managed project로 사용할 수 있도록 다음 파일을 둔다.

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

루트 `AGENTS.md`의 `HERMES-PROJECT` block도 이 값과 일치해야 한다.

---

# 10. 일반 운영

최초 설치가 끝난 뒤 일상적인 운영에서는 아래 명령만 주로 사용한다.

## 10.1 상태 확인

```powershell
docker compose ps
```

로그:

```powershell
docker compose logs -f hermes
```

## 10.2 중지 / 시작

중지:

```powershell
docker compose stop
```

다시 시작:

```powershell
docker compose start
```

재시작:

```powershell
docker compose restart
```

## 10.3 컨테이너만 다시 생성

Runtime data를 유지하면서 컨테이너와 Compose network만 제거한다.

```powershell
docker compose down
```

다시 실행한다.

```powershell
docker compose up -d
```

`hermes-dev-data` volume은 유지되므로 Profile/OAuth/Session은 보존된다.

## 10.4 Hermes 사용자 Shell

```powershell
docker exec -it --user hermes hermes-dev sh
```

## 10.5 Profile 조회

```powershell
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes profile list
```

```powershell
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes profile show orchestrator
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes profile show coder
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes profile show reviewer
```

## 10.6 Fallback Provider 조회

```powershell
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p orchestrator fallback list
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p coder fallback list
```

---

# 11. 특수 상황 가이드

아래 절차는 **처음 설치할 때 기본적으로 수행하지 않는다.** 해당 상황이 발생했을 때만 적용한다.

## 특수 상황 1. 기존 `.env`가 이미 있는 경우

새로운 `sample.env`를 기존 `.env` 위에 복사하지 않는다.

> [!WARNING]
> 기존 `.env`에는 Dashboard/Jira credential이 있을 수 있다. `Copy-Item sample.env .env -Force`처럼 덮어쓰지 않는다.

새 key가 추가되었는지 `sample.env`와 비교하고 필요한 non-secret key만 기존 `.env`에 수동으로 추가한다.

특히 현재 DevKit에서는 다음 항목을 확인한다.

```dotenv
HERMES_BASE_IMAGE=nousresearch/hermes-agent:v2026.8.16.2
HERMES_DASHBOARD_HOST=0.0.0.0
HERMES_API_SERVER_ENABLED=false
HERMES_API_SERVER_HOST=0.0.0.0
```

Dashboard credential의 기존 실제 값은 유지한다.

---

## 특수 상황 2. Hermes 데이터를 완전히 초기화해야 하는 경우

다음 상황에서만 완전 초기화를 고려한다.

- Profile/OAuth/Session을 모두 제거하고 처음부터 재검증
- `/opt/data` 상태가 손상되어 재생성이 필요
- 테스트 환경을 완전히 Fresh 상태로 재구성

> [!WARNING]
> 다음 명령은 `hermes-dev-data`를 삭제한다. Profile, OAuth, Session, Memory, Kanban, Work Item 등 `/opt/data`의 Hermes 상태가 삭제된다.

```powershell
docker compose down -v
```

`mssql-data` 등 Hermes와 관계없는 volume을 수동으로 삭제하지 않는다.

삭제 후에는 이 README의 **3단계부터 다시 순서대로** 진행한다.

```text
3. Docker 이미지 빌드 및 컨테이너 실행
4. Runtime 확인
5. Profile 초기화
6. Profile별 Model/OAuth 설정
   └─ 필요한 경우 Fallback Provider 재설정
7. 저장소 통합 검증
8. 최초 구성 완료 확인
```

---

## 특수 상황 3. Workspace 경로 변경

Host Workspace만 변경하는 경우 `.env`의 다음 값만 수정한다.

```dotenv
HERMES_HOST_WORKSPACE_PATH=C:/Users/example/source
```

가능하면 컨테이너 경로는 그대로 유지한다.

```dotenv
HERMES_CONTAINER_WORKSPACE_PATH=/workspace
```

컨테이너 경로까지 변경하면 기존 managed project의 다음 값이 실제 위치와 달라질 수 있다.

```text
.hermes/project.yaml
project.repository
git.worktree_root
```

이 경우 기존 metadata를 그대로 재사용하지 말고 실제 새 container path를 기준으로 `dev-project-bootstrap`을 다시 실행해 metadata를 수렴시킨다.

---

## 특수 상황 4. Hermes base image 업그레이드

기본 이미지는 reproducibility를 위해 release tag로 고정한다.

```dotenv
HERMES_BASE_IMAGE=nousresearch/hermes-agent:v2026.8.16.2
```

새 Hermes release로 올릴 때는 다음 순서로 진행한다.

```text
1. 새 tag/digest 확인
2. 별도 branch에서 HERMES_BASE_IMAGE 변경
3. scripts/verify.sh
4. docker compose build --no-cache
5. docker compose up -d
6. Hermes/Python runtime 확인
7. init-profiles.ps1 재실행
8. Profile/OAuth smoke test
9. 문제 없으면 dev 반영
```

완전히 immutable한 build가 필요하면 검증한 digest를 사용할 수 있다.

```dotenv
HERMES_BASE_IMAGE=nousresearch/hermes-agent@sha256:<verified-digest>
```

> [!NOTE]
> `latest`를 기본값으로 사용하지 않는다. 동일한 DevKit commit이라도 build 시점에 따라 다른 upstream image가 내려와 재현성이 깨질 수 있다.

---

## 특수 상황 5. OpenAI-compatible API Server 활성화

API Server는 기본 비활성화다.

```dotenv
HERMES_API_SERVER_ENABLED=false
```

필요할 때만 `.env`를 다음처럼 설정한다.

```dotenv
HERMES_API_SERVER_ENABLED=true
HERMES_API_SERVER_HOST=0.0.0.0
HERMES_API_SERVER_KEY=<strong-api-key>
```

설정 후 컨테이너를 재생성한다.

```powershell
docker compose up -d
```

기본 publish 주소는 다음 설정으로 Host loopback에 제한한다.

```dotenv
HERMES_PORT_BIND_ADDRESS=127.0.0.1
HERMES_API_SERVER_HOST_PORT=8642
```

> [!WARNING]
> `HERMES_PORT_BIND_ADDRESS=0.0.0.0`으로 바꾸면 Host 외부에서도 접근 가능해질 수 있다. 인증과 네트워크 경계를 검토하지 않은 상태에서는 변경하지 않는다.

---

## 특수 상황 6. Jira 연동

기본 설치에서는 Jira 설정이 비어 있어도 Hermes 멀티 프로필 구성에 문제가 없다.

Jira 연동이 필요할 때 `.env`에 다음 값을 입력한다.

```dotenv
JIRA_BASE_URL=https://<your-domain>.atlassian.net
JIRA_EMAIL=<account-email>
JIRA_API_TOKEN=<api-token>
JIRA_API_VERSION=3
JIRA_ACCEPTANCE_CRITERIA_FIELDS=Acceptance Criteria,완료 조건,인수 조건
JIRA_INCLUDE_FIELD_NAMES=
JIRA_VERIFY_SSL=true
```

설정 후 컨테이너를 재생성한다.

```powershell
docker compose up -d
```

Credential을 source, Skill 문서, Kanban body 또는 로그에 기록하지 않는다.

현재 Compose는 Jira 값을 container process environment로 전달한다. 향후 Hermes의 skill-scoped `required_environment_variables`로 migration하면 credential exposure scope를 더 줄일 수 있다.

---

# 12. 문제 해결

## 12.1 PowerShell `.ps1` 실행 차단

오류 예:

```text
PSSecurityException
이 시스템에서 스크립트를 실행할 수 없으므로 ... init-profiles.ps1 파일을 로드할 수 없습니다.
```

현재 PowerShell session에서만 허용한다.

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\init-profiles.ps1
```

영구적으로 정책을 낮출 필요는 없다.

---

## 12.2 `template parsing error: unexpected "%" in operand`

과거 `init-profiles.ps1`이 Docker Go Template의 `printf`로 mount를 검사할 때 Windows PowerShell quote escaping 차이로 발생하던 오류다.

현재 스크립트는 다음 구조를 사용한다.

```text
docker inspect
    ↓
PowerShell ConvertFrom-Json
    ↓
Mounts 검사
```

현재 branch에서 같은 오류가 난다면 먼저 최신 `init-profiles.ps1`을 사용 중인지 확인한다.

```powershell
git status
git log -1 --oneline
```

---

## 12.3 `ExitCode=127` / `hermes` 명령을 찾지 못함

login shell의 PATH에 의존하면 `hermes` 사용자 환경에서 CLI가 잡히지 않을 수 있다.

다음 절대경로로 직접 확인한다.

```powershell
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes --help
```

```powershell
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/python -c "import yaml; print('PYTHON_OK')"
```

현재 자동화 스크립트도 이 절대경로를 사용한다.

---

## 12.4 Docker build 중 많은 `CC ...` 로그가 출력됨

Dockerfile은 Git 2.55.0을 source에서 compile한다.

다음과 같은 로그는 정상이다.

```text
CC shallow.o
CC sideband.o
CC statinfo.o
...
```

오류 메시지 없이 계속 진행 중이라면 기다린다.

---

## 12.5 Hermes `SyntaxWarning` 관련 build 오류

Docker build 중 `scripts/patch_hermes_syntax_warning.py`가 `/opt/hermes/hermes_cli/update_cmd.py`를 검사한다.

지원 상태:

```text
patched          과거 upstream의 알려진 venv\Scripts 경고를 수정
already-patched  동일 코드가 이미 escape 처리됨
not-needed       최신 upstream에서 해당 코드가 변경/제거됨
```

세 상태 모두 `SyntaxWarning`을 error로 취급하는 strict compile을 통과해야 build가 계속된다.

즉 현재 검증 기준은 특정 과거 문자열의 존재 여부가 아니라 **현재 upstream source가 strict compile 가능한가**이다.

Hermes image를 임의로 `latest`로 바꾼 뒤 오류가 발생했다면 먼저 `HERMES_BASE_IMAGE`를 DevKit 기본 release로 되돌려 재현 여부를 확인한다.

---

## 12.6 Dashboard가 열리지 않음

상태를 확인한다.

```powershell
docker compose ps
docker compose logs --tail 200 hermes
```

`.env`의 다음 항목이 비어 있지 않은지 확인한다.

```dotenv
HERMES_DASHBOARD_USERNAME=
HERMES_DASHBOARD_PASSWORD=
HERMES_DASHBOARD_SECRET=
```

실제 값을 화면이나 로그에 출력할 필요는 없다. 텍스트 편집기로 직접 확인한다.

---

## 12.7 Fast Flow Task가 실행되지 않음

Coder가 Kanban Task를 생성했는데 상태가 `ready`에서 움직이지 않으면 Gateway/dispatcher를 확인한다.

```powershell
docker compose ps
docker compose logs --tail 200 hermes
```

현재 Compose는 다음 command로 Gateway를 실행한다.

```text
gateway run
```

Gateway가 정상이라면 embedded Kanban dispatcher가 Task를 가져간다.

Dashboard에서 해당 project board와 task status를 확인한다.

---

# 13. 보안 및 운영 원칙

- `.env`, OAuth Token, API Token, Password, Cookie를 commit하지 않는다.
- Dashboard/API Host publish 기본값은 `127.0.0.1`을 유지한다.
- Dashboard를 non-loopback container interface에 bind할 때 인증 provider를 반드시 설정한다.
- `docker compose config` 전체 출력에는 Secret이 render될 수 있으므로 외부 공유하지 않는다.
- `/opt/data` volume 삭제는 Profile/OAuth/Session 등 Hermes 영속 상태 삭제를 의미한다.
- Custom Skill과 shared policy bind는 read-only로 유지한다.
- Dockerfile/Compose에 `USER hermes` 또는 `user: hermes`를 지정해 공식 s6 root bootstrap을 깨지 않는다.
- runtime 자동화에서는 `/opt/hermes/.venv/bin/hermes`, `/opt/hermes/.venv/bin/python` 절대경로를 우선한다.
- Fast/Standard Flow 모두 Reviewer 단계를 유지한다.
- 구현 요청만 받은 상태에서 coder/reviewer workflow가 임의로 commit, push, PR, merge까지 진행하지 않는다.
- destructive Git operation과 Workspace cleanup은 명시적인 승인 없이 수행하지 않는다.

---

# 14. 자주 사용하는 명령

| 목적 | 명령 |
|---|---|
| 최초 빌드/실행 | `docker compose up -d --build` |
| 일반 실행 | `docker compose up -d` |
| 상태 확인 | `docker compose ps` |
| 로그 | `docker compose logs -f hermes` |
| Profile 초기화 | `.\init-profiles.ps1` |
| Profile 목록 | `docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes profile list` |
| Fallback 추가 | `docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p <profile> fallback add` |
| Fallback 조회 | `docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p <profile> fallback list` |
| **Fast Flow / Coder 직접 요청** | `docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p coder chat` |
| **Standard Flow / Orchestrator** | `docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p orchestrator chat` |
| Reviewer 직접 확인 | `docker exec -it --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p reviewer chat` |
| Skill 계약 검증 | `python3 scripts/check_skill_contract.py` |
| 통합 검증 | `bash scripts/verify.sh` |
| 데이터 유지 종료 | `docker compose down` |
| **완전 초기화** | `docker compose down -v` |

---

## 핵심 원칙 요약

```text
처음 설치
→ README 0 ~ 8을 순서대로 진행

작고 명확한 개발 작업
→ Coder에게 직접 요청
→ Coder가 Kanban 등록
→ Coder worker
→ project pattern + 필요한 capability skill_view
→ Reviewer

복잡한 개발 작업
→ Orchestrator
→ dev-project-pattern 분석
→ Breakdown에서 Applicable Skills 결정
→ Dispatch에서 Pattern/Skill 계약 보존
→ Coder가 capability skill_view
→ Reviewer

일반 운영
→ 10 참고

예외 상황
→ 11 ~ 12의 해당 항목만 적용

보안/운영 기준
→ 13 참고
```

Fast Flow는 Orchestrator를 생략하기 위한 **작은 작업 최적화**이지 Review, Kanban, Workspace 검증을 생략하는 shortcut이 아니다. 작업이 예상보다 커지면 `FAST_FLOW_ESCALATION_REQUIRED`로 중단하고 Standard Flow로 전환한다.