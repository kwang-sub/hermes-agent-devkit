---
name: dev-project-bootstrap
description: 기존 Git Repository를 Hermes Project로 idempotent하게 등록하고, 개발환경 preflight·프로젝트 Java toolchain·EOL 정책·공유 Kanban Board·Profile Binding·Context·.hermes/project.yaml을 보장한다. resolver 값은 사용자가 직접 관리한다.
version: 0.4.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, project, bootstrap, kanban, context, orchestration, resolver, preflight, eol, java, toolchain]
    requires_tools: [terminal]
---

# dev-project-bootstrap

기존 Git Repository를 Hermes 개발 Workflow에 사용할 수 있도록 idempotent하게 준비한다.

핵심 원칙:
- 개발환경 preflight를 Project/Board 변경보다 먼저 실행한다.
- Repository 실제 쓰기 가능 여부를 확인한다.
- Gradle/Maven 프로젝트의 Java target을 감지하고 DevKit의 JDK 8/17/21 중 적절한 runtime을 선택한다.
- 프로젝트 build file을 Java toolchain 선택을 위해 임의 수정하지 않는다.
- 선택 결과는 `.hermes/toolchain.env`에 기록한다.
- `.gitattributes`의 Hermes 권장 EOL 규칙을 보장하되 기존 충돌 정책은 덮어쓰지 않는다.
- 이미 유효한 Project/Board/Profile Binding은 재사용한다.
- Resolver와 Legacy/Source-specific Metadata는 보존한다.

## 1. 책임 범위

```text
Git repository validation
Development environment preflight
Workspace write validation
Gradle/Maven detection
Java target detection
JDK 8/17/21 runtime selection
.hermes/toolchain.env ensure
.gitattributes EOL policy ensure
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
```

Gradle/Maven은 전역 설치하지 않고 Repository의 `gradlew`/`mvnw`를 사용한다.

## 2. Development Environment Preflight

순서:

```text
1. git / python3 확인
2. --repo가 정확한 Git root인지 확인
3. Repository root write probe
4. Gradle/Maven 프로젝트 유형 감지
5. Java target 감지
6. DevKit JDK 8/17/21 중 runtime 선택 및 java/javac self-check
7. .hermes/toolchain.env 생성/갱신
8. .gitattributes 생성/보강
9. gradlew/mvnw 현재 EOL 확인
```

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

## 5. 표준 결과

```text
<repo>/
├─ .gitattributes
├─ <active context file>
└─ .hermes/
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

## 6. 실행

일반 실행은 launcher를 사용한다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/bootstrap.py" \
  --repo "/workspace/dashboard"
```

실행 순서:

```text
dev_environment_preflight.py
        ↓ success
bootstrap_project.py
```

## 7. Repository 검증 / Block 조건

다음 경우 중단한다.

- Repo Path 오류 / Git root 불일치
- Repository가 Hermes runtime user에게 writable하지 않음
- 감지된 Java target 값이 서로 충돌
- 감지된 Java target이 DevKit 지원 범위(8/17/21) 밖임
- 선택된 JDK의 java/javac가 없음 또는 self-check 실패
- 기존 `.hermes/toolchain.env`가 bootstrap managed file이 아님
- `.gitattributes`에 Hermes EOL 정책과 충돌하는 규칙이 있음
- Base ref가 commit으로 resolve되지 않음
- Common Context Source 없음
- 기존 Managed Core Metadata identity 충돌
- 기존 Hermes Project ID가 다른 Repository를 가리킴
- 필수 Profile 없음
- Hermes CLI 실패

JDK가 없거나 맞지 않을 때 Agent가 Task 중 Temurin을 다운로드하거나 host Java를 탐색해서 우회하지 않는다.

## 8. Metadata / Context 보존 계약

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

## 9. 안전 규칙

절대 하지 않는다.

- Java version/toolchain을 맞추기 위한 Application build file 임의 수정
- `.gitattributes` 충돌 정책 자동 덮어쓰기
- 전체 Repository 자동 renormalize
- Task 중 JDK/Gradle/Maven 임의 설치
- Resolver 값 자동 추론
- Source-system Mapping 자동 생성
- Project/Board 삭제
- Git reset/clean/checkout/rebase/merge/commit
- Unmanaged Metadata 덮어쓰기

## 10. 예상 출력

Preflight:

```text
BUILD_TYPE=gradle|maven|other
TOOLCHAIN_FILE=/workspace/.../.hermes/toolchain.env|none
GITATTRIBUTES=created|updated|unchanged|skipped
WARNINGS=0
PREFLIGHT_STATUS=ready
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

## 11. 권장 검증

```text
workspace write probe succeeds
Java 8/17/21 target detection works
selected JDK java/javac self-check succeeds
.hermes/toolchain.env is idempotent
hermes-java uses selected JAVA_HOME
.gitattributes rules are idempotent
conflicting EOL rule blocks without overwrite
wrapper CRLF is reported without mass renormalization
existing Project/Board reused
resolver/custom metadata preserved
```
