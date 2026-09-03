# dev-project-bootstrap v0.4.3

기존 Git Repository를 Hermes Managed Project로 idempotent하게 등록하는 Skill입니다.

## 변경된 기본 정책

대용량 Repository와 Windows/Docker bind mount에서 Bootstrap 초기화가 오래 걸리는 문제를 줄이기 위해 일반 실행은 **Fast Preflight**를 사용합니다.

기존처럼 preflight 전후에 전체 Git 변경/EOL 분류를 반복하지 않습니다. 기본 경로는 tracked unstaged 의미 변경 1회와 staged index 변경 1회만 확인합니다.

```text
bootstrap.py
  ├─ repository process lock
  ├─ bootstrap_preflight.py (fast)
  ├─ ensure_gitignore.py
  └─ bootstrap_project.py
```

Fast Preflight에서는 다음을 생략합니다.

```text
- untracked 전체 enumeration
- EOL-only 개수 산출용 normal git diff
- preflight 변경 후 두 번째 repository-wide Git scan
```

CRLF/LF-only tracked 변경은 `git diff --numstat -z --ignore-cr-at-eol` 방식으로 effective change에서 제외합니다.

Fast 출력 예:

```text
GIT_SCAN_MODE=fast
EFFECTIVE_SCOPE=tracked-only
EFFECTIVE_DIRTY=false
EFFECTIVE_CHANGE_COUNT=0
EOL_ONLY_CHANGE_COUNT=-1
UNTRACKED_CHANGE_COUNT=-1
```

`-1`은 0건이 아니라 Fast Path에서 전체 개수 계산을 생략했다는 의미입니다.

## 일반 실행

```bash
python3 "${HERMES_SKILL_DIR}/scripts/bootstrap.py" \
  --repo /workspace/dashboard
```

## Full Preflight

정확한 untracked 및 EOL-only 개수가 필요한 진단 상황에서만 사용합니다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/bootstrap.py" \
  --repo /workspace/dashboard \
  --full-preflight
```

Full 모드에서는 normal tracked diff와 `git ls-files --others --exclude-standard`를 추가 실행합니다.

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

## 기존 보장 사항

- Git `safe.directory` 등록
- Repository write probe
- Java target 감지 및 JDK 8/17/21 runtime 선택
- `.hermes/toolchain.env` 관리
- `.gitattributes` EOL 정책
- `.gitignore`의 `/.hermes/`, `/.worktrees/` 관리
- Project / Board / Profile Binding ensure
- `AGENTS.common.md` Managed Block 병합
- `.hermes/project.yaml` Core Metadata 관리
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
