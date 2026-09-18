# dev-project-bootstrap v0.6.2

기존 Git Repository를 Hermes Managed Project로 idempotent하게 등록하는 Skill입니다.

## 기본 정책

대용량 Repository와 Windows/Docker bind mount에서 Bootstrap 초기화가 오래 걸리는 문제를 줄이기 위해 일반 실행은 **Fast Preflight**를 사용합니다.

Fast Preflight는 repository-wide Git change/EOL/untracked scan을 기본 경로에서 생략하고, 정확한 진단이 필요할 때만 `--full-preflight`를 사용합니다.

```text
bootstrap.py
  ├─ repository process lock
  ├─ bootstrap_preflight.py (fast)
  │   └─ project_builds.py (bounded build-root discovery)
  ├─ ensure_gitignore.py
  ├─ bootstrap_project.py
  └─ stack_cache.py
```

Fast 출력 예:

```text
GIT_SCAN_MODE=fast
EFFECTIVE_SCOPE=not-scanned
EFFECTIVE_DIRTY=unknown
EFFECTIVE_CHANGE_COUNT=-1
EOL_ONLY_CHANGE_COUNT=-1
UNTRACKED_CHANGE_COUNT=-1
```

`-1`은 0건이 아니라 Fast Path에서 전체 개수 계산을 생략했다는 의미입니다.

## 일반 실행

```bash
python3 "${HERMES_SKILL_DIR}/scripts/bootstrap.py" \
  --repo /workspace/dashboard
```

## 단일 프로젝트 / 멀티 프로젝트

Java preflight는 `dev-tech-dispatch`와 동일한 bounded manifest 탐색 정책을 재사용합니다. 따라서 Git Repository root에 `build.gradle(.kts)` 또는 `pom.xml`이 없어도 최대 탐색 범위 안의 실제 JVM build root를 찾습니다.

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

처리 기준:

- Repository root JVM 프로젝트는 기존 동작을 그대로 유지합니다.
- Gradle/Maven multi-module의 nested module은 ancestor build root 하나로 취급합니다.
- sibling Gradle/Maven root는 독립 build project로 유지합니다.
- frontend-only `package.json`은 Java toolchain 대상이 아닙니다.
- 독립 JVM project가 여러 개여도 Java target/runtime이 같으면 Repository `.hermes/toolchain.env`를 공유합니다.
- 서로 다른 Java toolchain이 필요하면 현재 `1 repository = 1 toolchain` 계약에서 임의 선택하지 않고 Bootstrap을 Block합니다.

Bootstrap 출력에는 탐지된 build root가 추가됩니다.

```text
BUILD_TYPE=gradle
BUILD_PROJECT_COUNT=1
BUILD_PROJECTS=gradle:chagok-backend
```


## Backend capability cache

기술 감지 결과는 Backend의 실행 진입점과 보조 guideline을 분리해 저장합니다.

```yaml
technology:
  stacks:
    - java
    - spring
  backend_entries:
    - dev-spring-feature
  backend_hints:
    - dev-java-guidelines
    - dev-spring-guidelines
  backend_skills:
    - dev-java-guidelines
    - dev-spring-guidelines
```

`backend_skills`는 기존 managed project/reader 호환을 위한 legacy alias입니다. 신규 consumer는 `backend_entries + backend_hints`를 사용합니다.

현재 detector는 JVM/Spring을 지원하며 Python/FastAPI 같은 미지원 Backend Skill을 미리 생성하지 않습니다. 향후 실제 Stack을 추가할 때 stack evidence와 entry/hint mapping을 확장하는 방식으로 동일 metadata contract를 유지합니다.

## Full Preflight

정확한 untracked 및 EOL-only 개수가 필요한 진단 상황에서만 사용합니다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/bootstrap.py" \
  --repo /workspace/dashboard \
  --full-preflight
```

Full 모드에서는 tracked diff와 `git ls-files --others --exclude-standard`를 추가 실행합니다. CRLF/LF-only tracked 변경은 `git diff --numstat -z --ignore-cr-at-eol` 기반으로 의미 변경에서 제외합니다.

```text
GIT_SCAN_MODE=full
EFFECTIVE_SCOPE=all
EOL_ONLY_CHANGE_COUNT=<number>
UNTRACKED_CHANGE_COUNT=<number>
```

## 중복 Bootstrap 방지

동일 Repository에서 Bootstrap이 이미 실행 중이면 두 번째 실행은 즉시 차단됩니다.

Repository 절대경로를 기준으로 다음 lock을 사용합니다.

```text
/tmp/hermes-bootstrap-<hash>.lock
```

따라서 Agent는 오래 걸리는 Bootstrap을 다시 실행하지 않고 최초 process handle을 poll해야 합니다.

## 보장 사항

- Git `safe.directory` 등록
- Repository write probe
- bounded Gradle/Maven build-root discovery
- Java target 감지 및 JDK 8/17/21 runtime 선택
- `.hermes/toolchain.env` 관리
- `.gitattributes` EOL 정책
- `.gitignore`의 `/.hermes/`, `/.worktrees/` 관리
- Project / Board / Profile Binding ensure
- `AGENTS.common.md` Managed Block 병합
- `.hermes/project.yaml` Core Metadata / technology cache 관리
- Resolver / Custom Metadata 보존

## Java 실행

```bash
hermes-java ./gradlew test
hermes-java ./gradlew compileJava
hermes-java ./mvnw test
```

## EOL 정책

```gitattributes
gradlew text eol=lf
mvnw text eol=lf
*.sh text eol=lf
*.bat text eol=crlf
*.cmd text eol=crlf
```

충돌 규칙은 자동 덮어쓰지 않으며 전체 renormalize도 수행하지 않습니다.

## Git ignore 정책

```gitignore
# >>> Hermes Agent managed >>>
# Hermes 로컬 실행/상태 파일 (프로젝트 공용 파일은 Git 추적 유지)
/.hermes/
/.worktrees/
# <<< Hermes Agent managed <<<
```

`AGENTS.md`, `.gitattributes` 등 프로젝트 공용 파일은 Git 추적 대상으로 유지합니다.
