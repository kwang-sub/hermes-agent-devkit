---
name: dev-project-bootstrap
description: 기존 Git Repository를 Hermes Project로 idempotent하게 등록하고, Fast Preflight·기술 스택 fingerprint/cache·기존 저장소 refresh·Java toolchain·EOL·Git ignore·Kanban/Profile/Context/.hermes/project.yaml을 보장한다. resolver 값은 사용자가 직접 관리한다.
version: 0.5.1
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, project, bootstrap, kanban, context, orchestration, resolver, preflight, performance, stack, fingerprint, cache, monorepo, eol, java, toolchain, git]
    requires_tools: [terminal]
---

# dev-project-bootstrap

기존 Git Repository를 Hermes 개발 Workflow에 사용할 수 있도록 idempotent하게 준비한다.

핵심 원칙:
- 일반 Bootstrap은 **Fast Preflight**를 사용한다.
- 대용량 Repository/Windows bind mount에서 전체 untracked 탐색과 반복 Git scan을 기본 경로에서 피한다.
- 정확한 untracked/EOL-only 진단이 필요할 때만 `--full-preflight`를 사용한다.
- 동일 Repository에서 Bootstrap process를 중복 실행하지 않는다. 이미 실행 중이면 기존 process를 poll한다.
- 개발환경 preflight를 Project/Board 변경보다 먼저 실행한다.
- Repository를 Git `safe.directory`에 idempotent하게 등록하고 쓰기 가능 여부를 확인한다.
- CRLF/LF-only tracked 변경은 effective change에서 제외한다.
- `dev-tech-dispatch`와 동일한 bounded manifest 탐색 범위에서 Gradle/Maven build root를 찾고 Java target을 감지해 DevKit JDK 8/17/21 중 runtime을 선택한 뒤 Repository의 `.hermes/toolchain.env`에 기록한다.
- 단일 프로젝트, Gradle/Maven multi-module, backend/frontend monorepo를 같은 탐색 계약으로 처리한다.
- 독립 JVM build root가 여러 개이면 동일 Java target/runtime일 때 Repository toolchain을 공유하고, 서로 다른 Java toolchain이 필요하면 잘못된 JDK를 임의 선택하지 않고 Block한다.
- Repository build/dependency manifest에서 기술 스택을 탐지하고 `.hermes/project.yaml technology:`에 fingerprint와 결과를 저장한다.
- 일반 source 변경은 technology cache를 무효화하지 않고 manifest 또는 detector version 변경 때만 재탐지한다.
- `.gitattributes`와 `.gitignore`의 Hermes 관리 정책을 보장하되 기존 사용자 정책은 임의로 덮어쓰지 않는다.
- 이미 유효한 Project/Board/Profile Binding은 재사용한다.
- Resolver와 Legacy/Source-specific Metadata는 보존한다.

## 1. 기본 실행 흐름

```text
bootstrap.py
  ├─ repository process lock
  ├─ bootstrap_preflight.py (fast)
  │   └─ project_builds.py (bounded build-root discovery)
  ├─ ensure_gitignore.py
  ├─ bootstrap_project.py
  └─ stack_cache.py
```

일반 실행:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/bootstrap.py" \
  --repo "/workspace/dashboard"
```

최종 `.hermes/project.yaml`은 schema version 3 technology cache를 포함한다.

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
  backend_skills:
    - "dev-java-guidelines"
    - "dev-spring-guidelines"
  frontend_entry: "dev-frontend-feature"
  frontend_hints:
    - "dev-typescript-guidelines"
    - "dev-frontend-guidelines"
    - "dev-nextjs-feature"
```

Repository stack은 Task 분류가 아니다. Standard Flow의 Orchestrator가 사용자 요구사항과 affected area를 함께 보고 Backend / Frontend / Full-stack을 판단한다.

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

DevKit 업데이트 전에 이미 Bootstrap된 Repository는 Project/Board/Profile을 다시 만들 필요 없이 stack cache만 갱신할 수 있다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/bootstrap.py" \
  --repo "/workspace/product/oc/wsm17-oc" \
  --refresh-stack
```

`--refresh-stack`은 다음만 수행한다.

```text
repository lock
→ ensure_gitignore.py
→ stack_cache.py --force
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
8. 각 JVM build root의 Java target/runtime 선택
9. compatible JVM roots이면 Repository .hermes/toolchain.env ensure
10. .gitattributes ensure
11. 각 build root의 gradlew/mvnw EOL 확인
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

Java 프로젝트에는 Repository 단위 `.hermes/toolchain.env`를 보장한다. Coder/Reviewer는 `hermes-java` launcher를 우선한다.

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

독립 JVM build project가 여러 개여도 모두 동일 target/runtime을 요구하면 Repository `.hermes/toolchain.env`를 공유한다. Java 17과 Java 21처럼 서로 다른 toolchain이 필요하면 현재 `hermes-java`의 `1 repository = 1 toolchain` 계약에서 자동 선택하지 않고 Bootstrap을 Block한다. 이 경우 per-project runtime 계약을 별도 설계하거나 프로젝트 Java 기준을 정렬해야 한다.

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

`.gitignore`에 다음 Hermes 관리 블록을 보장한다.

```gitignore
# >>> Hermes Agent managed >>>
# Hermes 로컬 실행/상태 파일 (프로젝트 공용 파일은 Git 추적 유지)
/.hermes/
/.worktrees/
# <<< Hermes Agent managed <<<
```

따라서 Bootstrap이 생성하는 `project.yaml`, `toolchain.env`, technology cache 등 `.hermes/` 하위 local metadata는 Git 변경으로 잡히지 않는다.

`AGENTS.md`, `.gitattributes`, 소스/빌드 설정 등 프로젝트 공용 파일은 Hermes 관리 블록으로 ignore하지 않는다. 기존 사용자 규칙은 삭제하거나 재정렬하지 않는다.

## 10. Block 조건

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
- Hermes local path ignore 검증 실패
- Base ref resolve 실패
- Common Context 없음
- Metadata identity 충돌
- Project ID가 다른 Repository를 가리킴
- 필수 Profile 없음
- Hermes CLI 실패

## 11. 안전 규칙

절대 하지 않는다.

- 오래 걸린다는 이유로 동일 Repository Bootstrap 재실행
- Application build/dependency file을 stack cache 때문에 수정
- technology/build-root detection을 위해 Repository 전체 source scan
- 서로 다른 JVM toolchain 요구사항 중 하나를 임의 선택
- `.gitattributes` 충돌 정책 자동 덮어쓰기
- 기존 `.gitignore` 사용자 규칙 삭제/재정렬
- `git rm --cached` 자동 실행
- 전체 Repository 자동 renormalize
- EOL noise 제거 목적의 reset/restore/checkout
- Task 중 JDK/Gradle/Maven/npm dependency 임의 설치
- Resolver 값 자동 추론
- Project/Board 삭제
- Git reset/clean/checkout/rebase/merge/commit
- Unmanaged Metadata 덮어쓰기

## 12. 권장 회귀 검증

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
resolver/custom metadata is preserved
technology cache creates/reuses/refreshes correctly
source-only change keeps stack fingerprint stable
manifest change invalidates stack fingerprint
backend/frontend monorepo detection works
refresh-stack does not redo Project/Board/Profile registration
```
