---
name: dev-project-bootstrap
description: Git Project와 사용자 승인 Non-Git Project를 Hermes Managed Project로 idempotent하게 등록하고, Version Control Gate·Fast Preflight·기술 스택/Infrastructure cache·Java toolchain·환경설정 보안·Kanban/Profile/Context/.hermes/project.yaml을 보장한다. resolver 값은 사용자가 직접 관리한다.
version: 0.7.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, project, bootstrap, kanban, context, orchestration, resolver, preflight, performance, stack, fingerprint, cache, monorepo, eol, java, toolchain, git, env, secret, security]
    requires_tools: [terminal]
---

# dev-project-bootstrap

Git Repository 또는 사용자가 변경 추적 부재를 승인한 Non-Git 디렉터리를 Hermes 개발 Workflow에 사용할 수 있도록 idempotent하게 준비한다.

애플리케이션 환경설정/Secret 정책은 `/opt/data/shared/references/application-configuration-security.md`를 따른다.

핵심 원칙:
- 일반 Bootstrap은 **Fast Preflight**를 사용한다.
- 대용량 Repository/Windows bind mount에서 전체 untracked 탐색과 반복 Git scan을 기본 경로에서 피한다.
- 정확한 untracked/EOL-only 진단이 필요할 때만 `--full-preflight`를 사용한다.
- 동일 Repository에서 Bootstrap process를 중복 실행하지 않는다. 이미 실행 중이면 기존 process를 poll한다.
- 개발환경 preflight를 Project/Board 변경보다 먼저 실행한다.
- Git Project는 Git `safe.directory`에 idempotent하게 등록하고 쓰기 가능 여부를 확인한다.
- Non-Git Project는 최초 등록 시 Version Control Gate에서 명시적 사용자 승인을 받아야 하며, 승인 후에는 `.hermes/project.yaml`의 `version_control.non_git_write_acknowledged=true`를 재사용해 반복 확인하지 않는다.
- Non-Git 승인은 snapshot/VCS 대체 기능을 만들지 않는다. Git diff/history/rollback/branch/worktree가 제공되지 않는 상태에서 직접 파일 변경을 허용한다는 의미다.
- CRLF/LF-only tracked 변경은 effective change에서 제외한다.
- `dev-tech-dispatch`와 동일한 bounded manifest 탐색 범위에서 Gradle/Maven build root를 찾고 Java target을 감지해 DevKit JDK 8/17/21 중 runtime을 선택한 뒤 Repository의 `.hermes/toolchain.env`에 기록한다.
- 단일 프로젝트, Gradle/Maven multi-module, backend/frontend monorepo를 같은 탐색 계약으로 처리한다.
- 독립 JVM build root가 여러 개이면 동일 Java target/runtime일 때 Repository toolchain을 공유하고, 서로 다른 Java toolchain이 필요하면 잘못된 JDK를 임의 선택하지 않고 Block한다.
- Repository build/dependency manifest에서 기술 스택을 탐지하고 `.hermes/project.yaml technology:`에 fingerprint와 결과를 저장한다.
- 일반 source 변경은 technology cache를 무효화하지 않고 manifest 또는 detector version 변경 때만 재탐지한다.
- `.gitattributes`와 `.gitignore`의 Hermes 관리 정책을 보장하되 기존 사용자 정책은 임의로 덮어쓰지 않는다.
- `.env.example`을 환경변수 계약 파일의 기본 관행으로 사용하고 실제 `.env*` 값은 Git에서 분리한다.
- Spring 공통 `application.yml|yaml|properties`를 모두 지원한다. 신규/변경 구성은 `${ENV_VAR}` 외부화를 우선하되 기존 하드코딩 설정은 자동 변경하지 않는다.
- 이미 Git 추적 중인 local/secret 설정 또는 하드코딩 runtime 값을 발견해도 값 자체를 출력하지 않고 `WARN` 후 기존 상태를 보존하며 Bootstrap을 계속한다.
- 이미 유효한 Project/Board/Profile Binding은 재사용한다.
- Resolver와 Legacy/Source-specific Metadata는 보존한다.

## 1. 기본 실행 흐름

```text
bootstrap.py
  ├─ project process lock
  ├─ Version Control detection / acknowledgement
  ├─ bootstrap_preflight.py (fast)
  │   └─ project_builds.py (bounded build-root discovery)
  ├─ ensure_gitignore.py (Git only)
  ├─ ensure_config_security.py
  ├─ bootstrap_project.py
  ├─ stack_cache.py
  └─ infrastructure_cache.py
```

일반 실행:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/bootstrap.py" \
  --repo "/workspace/dashboard"
```

최종 `.hermes/project.yaml`은 technology cache와 Infrastructure Desired State를 포함할 수 있다.

### Version Control Gate

Project root가 Git 저장소가 아니면 자동 실패하거나 자동 승인하지 않는다. 최초 등록에서 반드시 독립 `clarify` Gate를 수행한다.

```text
question:
  [버전 관리 확인]
  현재 Project는 Git 저장소가 아닙니다. Git diff/history/rollback/branch/worktree 없이 직접 파일 변경을 허용할까요?
choices:
  - Non-Git 상태로 작업 허용
  - Git 초기화 후 진행
  - 취소
```

- `Non-Git 상태로 작업 허용`: 승인 후에만 bootstrap을 `--allow-non-git`으로 실행한다.
- `Git 초기화 후 진행`: 사용자 승인 후 `git init`을 수행하고 가능한 경우 현재 상태를 initial commit으로 고정한 뒤 일반 Git bootstrap으로 진행한다. Git identity나 commit 조건이 충족되지 않으면 임의 identity를 만들지 않고 Block한다.
- `취소`: 등록과 source mutation을 수행하지 않는다.
- 이미 managed metadata에 `version_control.type=none` + `non_git_write_acknowledged=true`가 있으면 Gate를 다시 묻지 않는다.

Non-Git metadata 예:

```yaml
version_control:
  type: "none"
  non_git_write_acknowledged: true

git:
  default_base_branch: ""
  worktree_root: ""
```

상위 Project가 Non-Git이어도 하위에 독립 Git Repository 또는 독립 Non-Git 프로젝트가 여러 개 존재할 수 있다. Project 등록은 상위 metadata를 기준으로 하고, 실제 Standard Flow Workspace가 하위 Git root이면 해당 Workspace의 branch/diff/toolchain 계약을 사용한다. 하위 Non-Git Workspace는 branch/diff를 `N/A`로 처리하되 실행 Workspace별 toolchain을 준비할 수 있다.


예:

```yaml
technology:
  detector_version: "2"
  fingerprint: "sha256:..."
  inputs:
    - "backend/build.gradle"
    - "frontend/package.json"
    - "frontend/tsconfig.json"
  stacks:
    - "java"
    - "spring"
    - "typescript"
    - "react"
    - "nextjs"
  backend_entries:
    - "dev-spring-feature"
  backend_hints:
    - "dev-java-guidelines"
    - "dev-spring-guidelines"
  backend_skills:
    - "dev-java-guidelines"   # legacy compatibility alias
    - "dev-spring-guidelines"
  frontend_entry: "dev-frontend-feature"
  frontend_hints:
    - "dev-typescript-guidelines"
    - "dev-frontend-guidelines"
    - "dev-nextjs-feature"

infrastructure:
  version: "1"
  defaults:
    application_runtime: "CONTAINER"
    database_runtime: "CONTAINER"
  desired:
    application_runtime: "CONTAINER"
    database_runtime: "CONTAINER"
    database_platform: "NATIVE"
    database_vendor: "postgresql"
```

Repository stack은 Task 분류가 아니다. Standard Flow의 Orchestrator가 사용자 요구사항과 affected area를 함께 보고 Backend / Frontend / Full-stack을 판단한다.

Backend technology cache는 framework/domain entry와 guideline hint를 분리한다.

```text
backend_entries
→ 실제 Backend Work Unit의 실행 진입 capability 후보

backend_hints
→ language/framework guideline 후보

backend_skills
→ 기존 managed project/reader 호환용 legacy alias
```

현재 detector가 지원하는 Backend는 JVM/Spring이지만 이 metadata 구조는 특정 Backend 생태계에 고정하지 않는다. 향후 실제 Python/FastAPI 등 capability를 추가할 때 detector mapping과 Skill/CI만 확장하고 project metadata schema를 다시 바꾸지 않는 것을 목표로 한다.

## 2. Technology Stack Cache

Stack detector는 application source 전체를 훑지 않고 root 및 최대 3단계 하위의 build/dependency manifest만 본다.

대표 input:

```text
build.gradle / build.gradle.kts / settings.gradle*
pom.xml / gradle.properties / libs.versions.toml
package.json / package-lock.json / pnpm-lock.yaml / pnpm-workspace.yaml
yarn.lock / bun.lock*
tsconfig*.json
```

따라서 다음 형태도 지원한다.

```text
repo/
├─ backend/
│  └─ build.gradle
└─ frontend/
   ├─ package.json
   └─ tsconfig.json
```

Bootstrap Java preflight도 별도 무제한 재귀 탐색을 하지 않고 이 detector의 bounded manifest 결과를 재사용한다. 따라서 stack detection과 Java build-root detection이 서로 다른 디렉터리를 보는 문제를 만들지 않는다.

fingerprint는 input path + file content + detector version으로 계산한다.

```text
manifest 변화 없음
→ STACK_CACHE=reused
→ full detector 생략

manifest 또는 detector version 변화
→ detector 재실행
→ technology cache 갱신
```

일반 `.java`, `.kt`, `.ts`, `.tsx`, CSS 등 source 변경은 fingerprint에 포함하지 않는다.

## 3. 기존 Bootstrap Repository 갱신

DevKit 업데이트 전에 이미 Bootstrap된 Repository는 Project/Board/Profile을 다시 만들 필요 없이 cache/security 계약만 갱신할 수 있다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/bootstrap.py" \
  --repo "/workspace/product/oc/wsm17-oc" \
  --refresh-stack
```

`--refresh-stack`은 다음만 수행한다.

```text
repository lock
→ ensure_gitignore.py
→ ensure_config_security.py
→ stack_cache.py --force
→ infrastructure_cache.py
```

Project/Board/Profile/Context를 다시 등록하거나 Full Git scan을 하지 않는다.

여러 Bootstrap-managed Repository는 일괄 갱신할 수 있다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/refresh_stacks.py" \
  --root "/workspace/product"
```

`# managed-by: dev-project-bootstrap` metadata와 Repository identity가 확인되는 경로만 대상으로 한다. Bootstrap되지 않은 Repository는 대상으로 삼지 않는다.

## 4. Fast Preflight

일반 Bootstrap의 기본 모드다.

```text
1. git / python3 확인
2. Git safe.directory 등록
3. Git root 확인
4. Repository write probe
5. Fast 모드에서는 repository-wide Git change scan 생략
6. bounded manifest에서 Gradle/Maven build root 탐색
7. Gradle/Maven multi-module root와 sibling build root 구분
8. 단일 실행 영역이면 JVM build root의 Java target/runtime 선택
9. Non-Git 상위 Project에서 독립 JVM build root가 여러 개면 toolchain 결정을 Workspace 선택 시점으로 지연
10. Git Project 또는 단일 Non-Git 실행 영역이면 .hermes/toolchain.env ensure
11. Git Project만 .gitattributes ensure
12. 각 root-owned build root의 gradlew/mvnw EOL 확인
```

Build root 출력 예:

```text
Build      : gradle
Build roots: 1
[INFO] Build project: chagok-backend (gradle)

BUILD_TYPE=gradle
BUILD_PROJECT_COUNT=1
BUILD_PROJECTS=gradle:chagok-backend
```

Fast Preflight에서는 성능을 위해 다음을 생략한다.

```text
git ls-files --others --exclude-standard
EOL-only 개수 산출용 normal git diff
Preflight 변경 이후 두 번째 repository-wide Git scan
```

따라서 Fast 출력의 의미는 다음과 같다.

```text
GIT_SCAN_MODE=fast
EFFECTIVE_SCOPE=not-scanned
EFFECTIVE_DIRTY=unknown
EFFECTIVE_CHANGE_COUNT=-1
EOL_ONLY_CHANGE_COUNT=-1
UNTRACKED_CHANGE_COUNT=-1
```

`-1`은 0건이 아니라 Fast Path에서 전체 개수 산출을 생략했다는 뜻이다.

## 5. Full Preflight

정확한 untracked/EOL-only 진단이 필요한 경우에만 사용한다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/bootstrap.py" \
  --repo "/workspace/dashboard" \
  --full-preflight
```

Full 모드는 Fast 검사에 normal tracked diff, untracked 전체 enumeration, EOL-only noise count를 추가한다.

대용량 설치 패키지 저장소나 Windows/Docker bind mount에서는 Full 모드를 일반 Bootstrap에서 자동 선택하지 않는다.

## 6. Bootstrap 중복 실행 방지

`bootstrap.py`는 Repository 절대경로 SHA-256을 이용해 `/tmp/hermes-bootstrap-<hash>.lock`을 사용한다.

같은 Repository Bootstrap이 이미 실행 중이면 두 번째 실행은 즉시 Block한다.

Agent 규칙:

```text
Bootstrap은 한 번만 시작한다.
오래 걸리더라도 같은 명령을 재실행하지 않는다.
최초 process handle을 poll한다.
중복 실행 Block 메시지가 나오면 새 process를 만들지 않는다.
```

## 7. Java 실행 계약

Java 프로젝트에는 실행 Workspace에 적용 가능한 `.hermes/toolchain.env`를 보장한다. Coder/Reviewer는 `hermes-java` launcher를 우선한다. Git linked worktree에서는 기존처럼 Primary Worktree의 canonical toolchain을 읽는다. Non-Git Project에서는 가장 가까운 상위 `.hermes/toolchain.env`를 사용한다. 상위 Non-Git Project 아래 독립 child Workspace가 Git이든 Non-Git이든, Project root와 다른 실행 Workspace가 선택되면 해당 Workspace 기준으로 toolchain을 별도 준비한다. Gradle project-cache/build-output/workspace-lock은 Workspace 경로 기준으로 격리한다.

```bash
hermes-java ./gradlew test
hermes-java ./gradlew compileJava
hermes-java ./mvnw test
```

지원 target/runtime은 Java 8/17/21이다.

지원 구조:

```text
# 단일 프로젝트
repo/
├─ build.gradle.kts
└─ src/

# Gradle multi-module
repo/
├─ settings.gradle.kts
├─ build.gradle.kts
├─ domain/build.gradle.kts
└─ api/build.gradle.kts

# backend/frontend monorepo
repo/
├─ chagok-backend/build.gradle.kts
└─ chagok-frontend/package.json
```

Gradle/Maven multi-module의 nested module manifest는 동일 ancestor build root 아래 하나의 build project로 취급한다. 반대로 sibling Gradle/Maven root는 독립 build project로 유지한다.

하나의 Git Repository 안에서 독립 JVM build project가 여러 개이면 기존 계약대로 동일 target/runtime일 때만 `.hermes/toolchain.env`를 공유하고 서로 다르면 Block한다. Non-Git Managed Project에서는 독립 JVM build root가 2개 이상이면 Project 등록 단계에서 하나의 Java 버전을 강제하지 않고 `TOOLCHAIN_FILE=deferred-workspace`로 기록한다. 이후 승인된 child Workspace가 자신의 toolchain을 결정한다. 단일 Non-Git 실행 영역은 기존처럼 하나의 `.hermes/toolchain.env`를 사용한다.

Frontend-only `package.json` 등은 Java build root로 취급하지 않는다.

## 8. EOL 정책

`.gitattributes`에 다음 규칙을 보장한다.

```gitattributes
gradlew text eol=lf
mvnw text eol=lf
*.sh text eol=lf
*.bat text eol=crlf
*.cmd text eol=crlf
```

기존 충돌 규칙은 덮어쓰지 않고 Block한다. `git add --renormalize .`는 자동 실행하지 않는다.

## 9. Git ignore 정책

`.gitignore`의 Hermes 관리 블록에 workflow local state와 application runtime secret 파일을 보장한다.

```gitignore
# >>> Hermes Agent managed >>>
# Hermes 로컬 실행/상태 파일
/.hermes/
/.worktrees/

# Application runtime environment / secrets
.env
.env.*
!.env.example

# Spring local/private configuration
application-local.yml
application-local.yaml
application-local.properties
application-secret.yml
application-secret.yaml
application-secret.properties
application-private.yml
application-private.yaml
application-private.properties

# Private key / keystore artifacts
private.pem
*-private.pem
*.private.pem
*.p12
*.pfx
*.jks
# <<< Hermes Agent managed <<<
```

따라서 Bootstrap이 생성하는 `.hermes/` local metadata와 실제 runtime secret 파일은 Git 변경으로 잡히지 않는다.

다음은 Git 추적 가능 상태를 유지한다.

```text
.env.example
application.yml / application.yaml / application.properties
*-public.pem
AGENTS.md
.gitattributes
source/build configuration
```

기존 사용자 `.gitignore` 규칙은 삭제하거나 재정렬하지 않는다.

## 10. Application Configuration Security

Bootstrap은 root 및 bounded application root를 기준으로 Backend/Frontend 환경설정 계약을 점검한다.

### Frontend / Next.js

```text
frontend/
├─ .env.example   Git 추적
└─ .env.local     Git ignore
```

`.env.example`이 없고 local env 파일이 있으면 **값은 복사하지 않고 key 이름만** 추출한다.

예:

```dotenv
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=
SUPABASE_SECRET_KEY=
```

`NEXT_PUBLIC_*`는 browser-visible 값이므로 Secret으로 간주하지 않는다. 단 실제 Supabase URL/publishable key는 환경별 runtime configuration이므로 실제 값을 Git example/source에 하드코딩하지 않는다.

### Spring Boot

공통 `application.yml`, `application.yaml`, `application.properties`를 모두 지원하고 Git 추적을 유지한다.

YAML 예:

```yaml
spring:
  datasource:
    url: ${DB_URL}
    username: ${DB_USERNAME}
    password: ${DB_PASSWORD}

supabase:
  url: ${SUPABASE_URL}
  secret-key: ${SUPABASE_SECRET_KEY}
```

Properties 예:

```properties
spring.datasource.url=${DB_URL}
spring.datasource.username=${DB_USERNAME}
spring.datasource.password=${DB_PASSWORD}
supabase.url=${SUPABASE_URL}
supabase.secret-key=${SUPABASE_SECRET_KEY}
```

Bootstrap은 YAML/Properties 양쪽에서 `${ENV_VAR}` placeholder 이름을 Backend `.env.example` 계약에 반영한다. 기존 하드코딩 값도 두 형식 모두 감지하지만 자동 변환하지 않는다.

중요:

```text
Spring Boot 자체는 일반적인 .env 파일을 자동 로드하지 않는다.
```

실제 값 전달 경로는 Runtime에 따라 다르다.

```text
Application Runtime = LOCAL_HOST
→ IntelliJ Run Configuration 또는 OS Environment
→ Spring Environment
→ ${DB_USERNAME} 등으로 해석

Application Runtime = CONTAINER
→ .env / deployment environment
→ Compose env_file/environment
→ Container Environment
→ Spring Environment
```

`application-local.*`, `application-secret.*`, `application-private.*` 같은 기존 local 파일을 사용할 수는 있지만 Git ignore 대상이다. 신규 구성은 공통 `application.*` + environment variable 방식을 우선한다.

### 공개키 / 비밀키

```text
*-public.pem  → Git 추적 가능
*-private.pem / private.pem → Git ignore
*.p12 / *.pfx / *.jks → Git ignore 기본값
```

### 기존 Repository 안전 처리

기존 Repository는 **Preserve First**다. 이미 Git에 추적된 `.env.local`, `application-local.*`, private key/keystore 또는 Spring 공통 설정의 하드코딩 credential/runtime 값이 있어도 Bootstrap이 기존 파일을 자동 변경하지 않는다.

```text
tracked protected file / hardcoded runtime value 발견
→ WARN
→ 실제 값이 아닌 경로/키만 보고
→ 기존 파일 유지
→ git rm --cached / placeholder 자동 치환 금지
→ BOOTSTRAP CONTINUE
```

권장되지 않는 보안 상태는 이후 별도 migration/refactor Task에서 개선한다. 기존 `.env.example`은 사용자 계약으로 보고 자동 덮어쓰지 않는다.

## 11. Block 조건

- 같은 Repository의 Bootstrap이 이미 실행 중
- Repo Path/Git root 오류
- Git safe.directory 등록 실패
- Repository write 불가
- 동일 build root의 Java target 충돌 또는 지원 범위 밖
- 독립 JVM build root 간 Java target/runtime 불일치
- 선택 JDK self-check 실패
- unmanaged `.hermes/toolchain.env` 또는 `.hermes/project.yaml`
- 충돌하는 `.gitattributes` EOL 정책
- 손상된 `.gitignore` Hermes marker
- Hermes local/application secret path ignore 검증 실패
- Base ref resolve 실패
- Common Context 없음
- Metadata identity 충돌
- Project ID가 다른 Repository를 가리킴
- 필수 Profile 없음
- Hermes CLI 실패

`tracked protected config`와 `tracked Spring hardcoded runtime/credential`은 Block 조건이 아니라 기본 `WARN + CONTINUE` 대상이다.

## 12. 안전 규칙

절대 하지 않는다.

- 오래 걸린다는 이유로 동일 Repository Bootstrap 재실행
- Application build/dependency file을 stack cache 때문에 수정
- technology/build-root detection을 위해 Repository 전체 source scan
- 서로 다른 JVM toolchain 요구사항 중 하나를 임의 선택
- `.gitattributes` 충돌 정책 자동 덮어쓰기
- 기존 `.gitignore` 사용자 규칙 삭제/재정렬
- `git rm --cached` 자동 실행
- tracked secret 파일 삭제/untrack 자동화
- 기존 Spring 설정의 하드코딩 값을 `${ENV_VAR}`로 자동 치환
- `.env.example`에 실제 credential/token/환경별 key 값을 복사
- Spring이 `.env`를 직접 자동 로드한다고 가정
- 전체 Repository 자동 renormalize
- EOL noise 제거 목적의 reset/restore/checkout
- Task 중 JDK/Gradle/Maven/npm dependency 임의 설치
- Resolver 값 자동 추론
- Project/Board 삭제
- Git reset/clean/checkout/rebase/merge/commit
- Unmanaged Metadata 덮어쓰기

## 13. 권장 회귀 검증

```text
Fast preflight skips repository-wide change scan
Full scan counts EOL-only/untracked changes
same-repository duplicate bootstrap is blocked
safe.directory registration is idempotent
Java 8/17/21 detection works
single-root Gradle/Maven project discovery works
nested backend + frontend monorepo detects only JVM build root for Java toolchain
Gradle/Maven multi-module candidates collapse to ancestor build root
sibling JVM build roots remain independent
same-Java sibling JVM roots share repository toolchain
different-Java sibling JVM roots fail closed
.gitattributes/.gitignore policies are idempotent
.env/.env.local/Spring private config/private key are ignored
.env.example/application.yml/public key remain trackable
.env.example generation copies keys only, never values
Spring YAML ${ENV_VAR} placeholders populate backend .env.example contract
Spring Properties ${ENV_VAR} placeholders populate backend .env.example contract
tracked protected config warns and continues without git rm --cached
hardcoded Spring YAML credential/runtime values warn and remain unchanged
hardcoded Spring Properties credential/runtime values warn and remain unchanged
resolver/custom metadata is preserved
technology cache creates/reuses/refreshes correctly
infrastructure desired state creates/reuses correctly
source-only change keeps stack fingerprint stable
manifest change invalidates stack fingerprint
backend/frontend monorepo detection works
refresh-stack does not redo Project/Board/Profile registration
Git CI and update-devkit contract remain valid
```
