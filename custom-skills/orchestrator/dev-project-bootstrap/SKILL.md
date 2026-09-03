---
name: dev-project-bootstrap
description: 기존 Git Repository를 Hermes Project로 idempotent하게 등록하고, 개발환경 preflight·프로젝트 Java toolchain·EOL 정책·Hermes 로컬 파일 Git ignore·공유 Kanban Board·Profile Binding·Context·.hermes/project.yaml을 보장한다. resolver 값은 사용자가 직접 관리한다.
version: 0.4.2
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, project, bootstrap, kanban, context, orchestration, resolver, preflight, eol, java, toolchain, git]
    requires_tools: [terminal]
---

# dev-project-bootstrap

기존 Git Repository를 Hermes 개발 Workflow에 사용할 수 있도록 idempotent하게 준비한다.

핵심 원칙:
- 개발환경 preflight를 Project/Board 변경보다 먼저 실행한다.
- Repository를 Hermes runtime user의 Git `safe.directory`에 idempotent하게 등록한다.
- Repository 실제 쓰기 가능 여부를 확인한다.
- Windows bind mount에서 raw `git status`의 CRLF/LF noise를 실제 사용자 변경과 구분한다.
- Gradle/Maven 프로젝트의 Java target을 감지하고 DevKit의 JDK 8/17/21 중 적절한 runtime을 선택한다.
- 프로젝트 build file을 Java toolchain 선택을 위해 임의 수정하지 않는다.
- 선택 결과는 `.hermes/toolchain.env`에 기록한다.
- `.gitattributes`의 Hermes 권장 EOL 규칙을 보장하되 기존 충돌 정책은 덮어쓰지 않는다.
- `.gitignore`에 Hermes 로컬 실행/상태 경로를 강제로 보장하고, 기존 사용자 규칙은 보존한다.
- `AGENTS.md`, `.gitattributes` 같은 프로젝트 공용 파일은 Hermes 규칙으로 ignore하지 않는다.
- 이미 유효한 Project/Board/Profile Binding은 재사용한다.
- Resolver와 Legacy/Source-specific Metadata는 보존한다.

## 1. 책임 범위

```text
Git safe.directory ensure
Git repository validation
Development environment preflight
Workspace write validation
Effective Git dirty/EOL-noise classification
Gradle/Maven detection
Java target detection
JDK 8/17/21 runtime selection
.hermes/toolchain.env ensure
.gitattributes EOL policy ensure
.gitignore Hermes local policy ensure
Hermes Project registration
Kanban Board ensure
Profile bindings
Common/project context managed blocks
Core .hermes/project.yaml metadata
Resolver skeleton ensure
```

Bootstrap 범위 밖:

```text
Jira/Notion/Slack configuration
Work Item fetching
repository resolution
implementation analysis
Task 중 JDK/Gradle/Maven 설치
Application build file의 Java version/toolchain 자동 수정
tracked-file mass renormalization
기존에 Git tracked 상태인 Hermes 파일의 index 자동 제거
```

Gradle/Maven은 전역 설치하지 않고 Repository의 `gradlew`/`mvnw`를 사용한다.

## 2. Development Environment Preflight

순서:

```text
1. git / python3 확인
2. --repo 경로를 Git safe.directory에 등록
3. --repo가 정확한 Git root인지 확인
4. Repository root write probe
5. effective Git changes와 EOL-only noise 분리
6. Gradle/Maven 프로젝트 유형 감지
7. Java target 감지
8. DevKit JDK 8/17/21 중 runtime 선택 및 java/javac self-check
9. .hermes/toolchain.env 생성/갱신
10. .gitattributes 생성/보강
11. gradlew/mvnw 현재 EOL 확인
```

Windows Host의 bind mount는 Host checkout이 CRLF이고 Git index가 LF인 경우 Linux Git의 raw `git status`에서 대량 `M`으로 보일 수 있다. 이 숫자만으로 dirty workspace를 판정하거나 사용자에게 중단 확인을 요청하지 않는다.

Effective change 규칙:

```text
unstaged tracked -> git diff --ignore-cr-at-eol 에 남는 변경만 실제 변경
staged            -> 항상 실제 변경
untracked         -> 항상 실제 변경
CRLF/LF-only      -> EOL-only noise로 집계, 실제 dirty에서는 제외
```

Bootstrap은 이 분류를 위해 reset/restore/checkout/renormalize를 실행하지 않는다.

Java target 감지 근거 예:

```text
Gradle:
- JavaLanguageVersion.of(...)
- jvmToolchain(...)
- sourceCompatibility / targetCompatibility

Maven:
- java.version
- maven.compiler.release
- maven.compiler.source / target
```

지원 target은 `8`, `17`, `21`이다. 명시값을 찾지 못하면 Java 17을 기본으로 선택하고 경고한다. 서로 충돌하는 target이 감지되면 자동 추측하지 않고 Block한다.

Gradle 9처럼 build runtime 자체가 Java 17 이상을 요구하는 경우 Java 8 target 프로젝트라도 `target=8`, `runtime=17`로 분리할 수 있다.

## 3. 프로젝트 Java 실행 계약

Bootstrap 성공 후 Java 프로젝트에는 다음 파일이 존재한다.

```text
.hermes/toolchain.env
```

예:

```bash
# managed-by: dev-project-bootstrap
HERMES_PROJECT_JAVA_TARGET=8
HERMES_PROJECT_JAVA_RUNTIME=8
JAVA_HOME=/opt/jdks/temurin-8
```

Coder/Reviewer는 Java build/test를 직접 `./gradlew` 또는 `./mvnw`로 실행하지 말고 DevKit launcher를 우선한다.

```bash
hermes-java ./gradlew test
hermes-java ./gradlew compileJava
hermes-java ./mvnw test
```

`hermes-java`는 현재 Git root의 `.hermes/toolchain.env`만 읽고 해당 JDK로 command를 실행한다.

## 4. `.gitattributes` 정책

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
.gitattributes 없음 -> 생성
필요 규칙 없음 -> 기존 내용 보존 후 추가
같은 pattern의 충돌 EOL 규칙 -> 덮어쓰지 않고 Block
```

`git add --renormalize .`는 자동 실행하지 않는다. 이미 checkout된 wrapper가 CRLF이면 경고만 출력한다.

## 5. `.gitignore` Hermes 로컬 파일 정책

Bootstrap은 preflight 성공 후 Project/Board 등록 전에 `.gitignore`의 Hermes 관리 블록을 반드시 보장한다.

```gitignore
# >>> Hermes Agent managed >>>
# Hermes 로컬 실행/상태 파일 (프로젝트 공용 파일은 Git 추적 유지)
/.hermes/
/.worktrees/
# <<< Hermes Agent managed <<<
```

처리 규칙:

```text
.gitignore 없음 -> 생성
Hermes 관리 블록 없음 -> 기존 내용 보존 후 추가
Hermes 관리 블록 있음 -> 필수 로컬 경로가 누락되면 관리 블록만 복구
반복 Bootstrap -> 동일 결과 유지
관리 marker 중복/손상 -> 사용자 영역 훼손 방지를 위해 Block
```

Hermes 관리 블록은 `AGENTS.md`, `.gitattributes`, 소스/빌드 설정 등 프로젝트 공용 파일을 ignore하지 않는다. 기존 사용자 `.gitignore` 규칙은 삭제하거나 재정렬하지 않는다.

`/.hermes/`, `/.worktrees/`가 실제로 ignore되는지 `git check-ignore --no-index`로 검증하고, 검증 실패 시 Bootstrap을 중단한다.

이미 Git index에 tracked된 Hermes 파일은 `.gitignore` 추가만으로 untrack되지 않는다. Bootstrap은 `git rm --cached`를 자동 실행하지 않는다.

## 6. 표준 결과

```text
<repo>/
├─ .gitignore       # Hermes 로컬 실행/상태 경로 ignore
├─ .gitattributes   # 프로젝트 공용 정책, Git 추적 대상
├─ <active context file>  # AGENTS.md 포함, Git 추적 가능
└─ .hermes/         # 로컬 Hermes 상태, Git ignore
   ├─ project.yaml
   └─ toolchain.env   # Java 프로젝트
```

Docker image의 Java layout:

```text
/opt/jdks/
├─ temurin-8
├─ temurin-17
└─ temurin-21

JAVA_HOME=/opt/jdks/temurin-17   # DevKit 기본
```

## 7. 실행

일반 실행은 launcher를 사용한다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/bootstrap.py" \
  --repo "/workspace/dashboard"
```

실행 순서:

```text
dev_environment_preflight.py
        ↓ success
ensure_gitignore.py
        ↓ success
bootstrap_project.py
```

## 8. Repository 검증 / Block 조건

다음 경우 중단한다.

- Repo Path 오류 / Git root 불일치
- Git safe.directory 등록 실패
- Repository가 Hermes runtime user에게 writable하지 않음
- 감지된 Java target 값이 서로 충돌
- 감지된 Java target이 DevKit 지원 범위(8/17/21) 밖임
- 선택된 JDK의 java/javac가 없음 또는 self-check 실패
- 기존 `.hermes/toolchain.env`가 bootstrap managed file이 아님
- `.gitattributes`에 Hermes EOL 정책과 충돌하는 규칙이 있음
- `.gitignore`의 Hermes 관리 marker가 중복/손상됨
- Hermes 로컬 경로 ignore 검증 실패
- Base ref가 commit으로 resolve되지 않음
- Common Context Source 없음
- 기존 Managed Core Metadata identity 충돌
- 기존 Hermes Project ID가 다른 Repository를 가리킴
- 필수 Profile 없음
- Hermes CLI 실패

JDK가 없거나 맞지 않을 때 Agent가 Task 중 Temurin을 다운로드하거나 host Java를 탐색해서 우회하지 않는다.

## 9. Metadata / Context 보존 계약

`.hermes/project.yaml`의 bootstrap-managed core는 `version/project/kanban/git/profiles`이며 `resolver` 및 unknown/source-specific top-level section은 보존한다. 기존 unmanaged metadata 파일은 덮어쓰지 않는다.

Context file 우선순위:

```text
.hermes.md
HERMES.md
AGENTS.md
CLAUDE.md
.cursorrules
```

없으면 `AGENTS.md`를 생성한다. Managed Block 밖의 기존 내용은 보존한다.

## 10. 안전 규칙

절대 하지 않는다.

- Java version/toolchain을 맞추기 위한 Application build file 임의 수정
- `.gitattributes` 충돌 정책 자동 덮어쓰기
- 기존 `.gitignore` 사용자 규칙 삭제/재정렬
- Hermes 로컬 파일을 untrack하기 위한 `git rm --cached` 자동 실행
- `AGENTS.md`, `.gitattributes` 등 프로젝트 공용 파일을 Hermes 관리 블록으로 ignore
- 전체 Repository 자동 renormalize
- EOL noise 제거 목적으로 reset/restore/checkout 수행
- Task 중 JDK/Gradle/Maven 임의 설치
- Resolver 값 자동 추론
- Source-system Mapping 자동 생성
- Project/Board 삭제
- Git reset/clean/checkout/rebase/merge/commit
- Unmanaged Metadata 덮어쓰기

## 11. 예상 출력

Preflight:

```text
BUILD_TYPE=gradle|maven|other
TOOLCHAIN_FILE=/workspace/.../.hermes/toolchain.env|none
GITATTRIBUTES=created|updated|unchanged|skipped
EFFECTIVE_DIRTY=true|false
EFFECTIVE_CHANGE_COUNT=...
EOL_ONLY_CHANGE_COUNT=...
WARNINGS=0
PREFLIGHT_STATUS=ready
```

Git ignore ensure:

```text
GITIGNORE=created|updated|unchanged
GITIGNORE_HERMES_LOCAL=ignored
```

Bootstrap:

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

## 12. 권장 검증

```text
safe.directory registration is idempotent
workspace write probe succeeds
CRLF-only tracked changes are EOL noise, not effective dirty
real tracked/staged/untracked changes remain effective dirty
Java 8/17/21 target detection works
selected JDK java/javac self-check succeeds
.hermes/toolchain.env is idempotent
hermes-java uses selected JAVA_HOME
.gitattributes rules are idempotent
conflicting EOL rule blocks without overwrite
.gitignore Hermes managed block is idempotent
existing .gitignore user rules are preserved
/.hermes/ and /.worktrees/ are ignored
AGENTS.md and .gitattributes are not added to Hermes ignore rules
malformed Hermes .gitignore markers block without overwriting user content
wrapper CRLF is reported without mass renormalization
existing Project/Board reused
resolver/custom metadata preserved
```
