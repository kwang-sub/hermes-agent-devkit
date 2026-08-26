# dev-project-bootstrap v0.3.0

기존 Git Repository를 Hermes Managed Project로 idempotent하게 등록하고, 실제 개발 작업이 가능한 환경인지 먼저 검증하는 Skill입니다.

## 핵심 정책

- Project / Board / Profile Binding ensure
- `AGENTS.common.md` Managed Block 병합
- `.hermes/project.yaml` Core Metadata 관리
- Resolver는 Skeleton만 생성하고 값은 **사용자 직접 관리**
- 기존 Resolver / Jira / Custom Metadata 보존
- Bootstrap 시작 전에 workspace write / Java toolchain / build wrapper / EOL 정책 검사
- `.gitattributes`가 없으면 생성하고, 필요한 규칙이 없으면 기존 내용을 보존한 채 추가
- 충돌하는 EOL 규칙은 자동 수정하지 않고 Block
- `git add --renormalize .` 같은 대량 변경은 자동 수행하지 않음

## 개발환경 전제

DevKit Docker image가 다음 공통 도구를 제공합니다.

```text
JDK 21
Git
Python 3
bash/sh
curl
unzip/zip
```

Gradle/Maven은 전역 설치본을 강제하지 않고 Repository의 Wrapper를 우선합니다.

```text
./gradlew
./mvnw
```

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

일반 Bootstrap은 preflight launcher를 사용합니다.

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

## 신규 프로젝트 기본 Resolver

```yaml
resolver:
  aliases: []
  modules: []
  files: []
  paths: []
```
