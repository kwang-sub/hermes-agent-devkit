---
name: dev-project-bootstrap
description: 기존 Git Repository를 Hermes Project로 idempotent하게 등록하고, 대용량 저장소용 Fast Preflight·선택적 Full Git 진단·중복 실행 방지·Java toolchain·EOL 정책·Hermes 로컬 파일 Git ignore·Kanban/Profile/Context/.hermes/project.yaml을 보장한다. resolver 값은 사용자가 직접 관리한다.
version: 0.4.3
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, project, bootstrap, kanban, context, orchestration, resolver, preflight, performance, eol, java, toolchain, git]
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
- Gradle/Maven Java target을 감지해 DevKit JDK 8/17/21 중 runtime을 선택하고 `.hermes/toolchain.env`에 기록한다.
- `.gitattributes`와 `.gitignore`의 Hermes 관리 정책을 보장하되 기존 사용자 정책은 임의로 덮어쓰지 않는다.
- 이미 유효한 Project/Board/Profile Binding은 재사용한다.
- Resolver와 Legacy/Source-specific Metadata는 보존한다.

## 1. 기본 실행 흐름

```text
bootstrap.py
  ├─ repository process lock
  ├─ bootstrap_preflight.py (fast)
  ├─ ensure_gitignore.py
  └─ bootstrap_project.py
```

일반 실행:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/bootstrap.py" \
  --repo "/workspace/dashboard"
```

## 2. Fast Preflight

일반 Bootstrap의 기본 모드다.

```text
1. git / python3 확인
2. Git safe.directory 등록
3. Git root 확인
4. Repository write probe
5. tracked unstaged effective change 검사
6. staged change 검사
7. Gradle/Maven 감지
8. Java target/runtime 선택
9. .hermes/toolchain.env ensure
10. .gitattributes ensure
11. gradlew/mvnw EOL 확인
```

tracked unstaged 검사는 다음 형태를 사용한다.

```text
git diff --numstat -z --ignore-cr-at-eol --no-renames ...
```

단순 `git diff --name-only --ignore-cr-at-eol`은 CRLF/LF-only 파일명이 남을 수 있으므로 Fast Path 판정에 사용하지 않는다.

Fast Preflight에서는 성능을 위해 다음을 생략한다.

```text
git ls-files --others --exclude-standard
EOL-only 개수 산출용 normal git diff
Preflight 변경 이후 두 번째 repository-wide Git scan
```

따라서 Fast 출력의 의미는 다음과 같다.

```text
GIT_SCAN_MODE=fast
EFFECTIVE_SCOPE=tracked-only
EFFECTIVE_DIRTY=true|false
EFFECTIVE_CHANGE_COUNT=<tracked effective count>
EOL_ONLY_CHANGE_COUNT=-1
UNTRACKED_CHANGE_COUNT=-1
```

`-1`은 0건이 아니라 **Fast Path에서 전체 개수 산출을 생략**했다는 뜻이다.

Fast Preflight는 Git dirty 여부만으로 Bootstrap을 자동 중단하지 않는다.

## 3. Full Preflight

정확한 untracked/EOL-only 진단이 필요한 경우에만 사용한다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/bootstrap.py" \
  --repo "/workspace/dashboard" \
  --full-preflight
```

Full 모드는 Fast 검사에 다음을 추가한다.

```text
normal tracked diff
untracked 전체 enumeration
EOL-only noise count
```

출력:

```text
GIT_SCAN_MODE=full
EFFECTIVE_SCOPE=all
EFFECTIVE_CHANGE_COUNT=<tracked + staged + untracked>
EOL_ONLY_CHANGE_COUNT=<number>
UNTRACKED_CHANGE_COUNT=<number>
```

대용량 설치 패키지 저장소나 Windows/Docker bind mount에서는 Full 모드를 일반 Bootstrap에서 자동 선택하지 않는다.

## 4. Bootstrap 중복 실행 방지

`bootstrap.py`는 Repository 절대경로의 SHA-256을 이용해 다음 lock을 사용한다.

```text
/tmp/hermes-bootstrap-<hash>.lock
```

같은 Repository Bootstrap이 이미 실행 중이면 두 번째 실행은 즉시 Block한다.

Agent 규칙:

```text
Bootstrap은 한 번만 시작한다.
오래 걸리더라도 같은 명령을 재실행하지 않는다.
최초 process handle을 poll한다.
중복 실행 Block 메시지가 나오면 새 process를 만들지 않는다.
```

## 5. Java 실행 계약

Java 프로젝트에는 다음 파일을 보장한다.

```text
.hermes/toolchain.env
```

Coder/Reviewer는 `hermes-java` launcher를 우선한다.

```bash
hermes-java ./gradlew test
hermes-java ./gradlew compileJava
hermes-java ./mvnw test
```

지원 target/runtime은 Java 8/17/21이다. Gradle 9처럼 build runtime 요구 버전이 더 높은 경우 target과 runtime을 분리할 수 있다.

## 6. EOL 정책

`.gitattributes`에 다음 규칙을 보장한다.

```gitattributes
gradlew text eol=lf
mvnw text eol=lf
*.sh text eol=lf
*.bat text eol=crlf
*.cmd text eol=crlf
```

기존 충돌 규칙은 덮어쓰지 않고 Block한다. `git add --renormalize .`는 자동 실행하지 않는다.

## 7. Git ignore 정책

`.gitignore`에 다음 Hermes 관리 블록을 보장한다.

```gitignore
# >>> Hermes Agent managed >>>
# Hermes 로컬 실행/상태 파일 (프로젝트 공용 파일은 Git 추적 유지)
/.hermes/
/.worktrees/
# <<< Hermes Agent managed <<<
```

`AGENTS.md`, `.gitattributes`, 소스/빌드 설정 등 프로젝트 공용 파일은 Hermes 관리 블록으로 ignore하지 않는다. 기존 사용자 규칙은 삭제하거나 재정렬하지 않는다.

## 8. Preflight 단독 실행

Fast:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/bootstrap_preflight.py" \
  --repo "/workspace/dashboard"
```

Full:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/bootstrap_preflight.py" \
  --repo "/workspace/dashboard" \
  --full
```

기존 `dev_environment_preflight.py`는 Java/EOL 등의 공유 helper와 호환성 검증용으로 유지하되, 일반 Bootstrap launcher의 Git change 분류 경로에는 사용하지 않는다.

## 9. Block 조건

- 같은 Repository의 Bootstrap이 이미 실행 중
- Repo Path/Git root 오류
- Git safe.directory 등록 실패
- Repository write 불가
- Java target 충돌 또는 지원 범위 밖
- 선택 JDK self-check 실패
- unmanaged `.hermes/toolchain.env`
- 충돌하는 `.gitattributes` EOL 정책
- 손상된 `.gitignore` Hermes marker
- Hermes local path ignore 검증 실패
- Base ref resolve 실패
- Common Context 없음
- Metadata identity 충돌
- Project ID가 다른 Repository를 가리킴
- 필수 Profile 없음
- Hermes CLI 실패

## 10. 안전 규칙

절대 하지 않는다.

- 오래 걸린다는 이유로 동일 Repository Bootstrap 재실행
- Application build file Java 설정 임의 수정
- `.gitattributes` 충돌 정책 자동 덮어쓰기
- 기존 `.gitignore` 사용자 규칙 삭제/재정렬
- `git rm --cached` 자동 실행
- 전체 Repository 자동 renormalize
- EOL noise 제거 목적의 reset/restore/checkout
- Task 중 JDK/Gradle/Maven 임의 설치
- Resolver 값 자동 추론
- Project/Board 삭제
- Git reset/clean/checkout/rebase/merge/commit
- Unmanaged Metadata 덮어쓰기

## 11. 권장 회귀 검증

```text
Fast scan ignores CRLF-only tracked noise
Fast scan keeps real tracked/staged changes
Fast scan skips untracked enumeration
Full scan counts EOL-only/untracked changes
same-repository duplicate bootstrap is blocked
safe.directory registration is idempotent
Java 8/17/21 detection works
.gitattributes/.gitignore policies are idempotent
resolver/custom metadata is preserved
```
