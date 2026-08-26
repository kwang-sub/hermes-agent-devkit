# dev-project-bootstrap v0.4.0

기존 Git Repository를 Hermes Managed Project로 idempotent하게 등록하고, 실제 개발 작업이 가능한 환경인지 먼저 검증하는 Skill입니다.

## 핵심 정책

- Project / Board / Profile Binding ensure
- `AGENTS.common.md` Managed Block 병합
- `.hermes/project.yaml` Core Metadata 관리
- Resolver는 Skeleton만 생성하고 값은 **사용자 직접 관리**
- 기존 Resolver / Jira / Custom Metadata 보존
- Bootstrap 시작 전에 workspace write / Java toolchain / build wrapper / EOL 정책 검사
- Gradle/Maven의 Java target을 감지해 JDK 8/17/21 중 project runtime 선택
- 선택 결과를 `.hermes/toolchain.env`에 저장
- `.gitattributes`가 없으면 생성하고, 필요한 규칙이 없으면 기존 내용을 보존한 채 추가
- 충돌하는 EOL 규칙은 자동 수정하지 않고 Block
- `git add --renormalize .` 같은 대량 변경은 자동 수행하지 않음

## DevKit Java 환경

```text
/opt/jdks/temurin-8
/opt/jdks/temurin-17
/opt/jdks/temurin-21
```

기본 `JAVA_HOME`은 Java 17입니다. 프로젝트 작업에서는 기본값에 의존하지 않고 Bootstrap 결과를 사용합니다.

예:

```bash
hermes-java ./gradlew test
hermes-java ./mvnw test
```

`hermes-java`는 현재 Git Repository의 `.hermes/toolchain.env`를 읽어 선택된 JDK로 명령을 실행합니다.

Gradle/Maven은 전역 설치하지 않고 Repository Wrapper를 사용합니다.

## Bootstrap이 보장하는 EOL 규칙

```gitattributes
gradlew text eol=lf
mvnw text eol=lf
*.sh text eol=lf
*.bat text eol=crlf
*.cmd text eol=crlf
```

이미 checkout된 wrapper가 CRLF이면 경고만 출력하고 자동 renormalize하지 않습니다.

## 실행

```bash
python3 "${HERMES_SKILL_DIR}/scripts/bootstrap.py" \
  --repo /workspace/dashboard
```

실행 순서:

```text
dev_environment_preflight.py
        ↓
bootstrap_project.py
```

개발환경만 별도로 검사할 수도 있습니다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/dev_environment_preflight.py" \
  --repo /workspace/dashboard
```

## Java target 감지

Gradle의 `JavaLanguageVersion`, `jvmToolchain`, `sourceCompatibility`, `targetCompatibility`와 Maven의 `java.version`, `maven.compiler.*`를 확인합니다.

지원 target은 Java 8 / 17 / 21입니다. target이 명확하지 않으면 Java 17을 기본값으로 사용하고 경고하며, 서로 충돌하는 target이 감지되면 자동 추측하지 않고 중단합니다.

## 신규 프로젝트 기본 Resolver

```yaml
resolver:
  aliases: []
  modules: []
  files: []
  paths: []
```
