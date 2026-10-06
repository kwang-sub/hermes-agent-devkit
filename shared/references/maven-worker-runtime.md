# Maven worker 실행 계약

Direct / Standard / Recovery / CHANGES_REQUESTED의 Coder와 Reviewer가 같은 경로를 사용한다. 추가 사용자 승인 Gate가 아니라 기존 승인 검증을 실행하는 방법이다.

## 시작 순서와 실행 경로

실제 Kanban spawn argv에 `DEVKIT_WORKER_STARTUP_V1` 안내를 넣어 새/재개 worker가 현재 역할 Skill을 로드하도록 한다. 이것은 실행 지침 전달이며 tool-level 강제 차단이나 승인 우회 장치가 아니다. Coder는 초기 `kanban_show`의 context를 재사용하고 `dev-implement-plan`의 세션 기록 → Worker Context Gate → `verify_workspace.py` 단독 1회 → source 순서를 따른다. 이전 세션에서 Gate를 통과했다는 이유로 새 run의 workspace 검증을 생략하지 않는다.

- `task_session_history.py`는 `/opt/devkit/bin/task_session_history.py`, workspace helper는 `/opt/custom-skills/coder/dev-implement-plan/scripts/verify_workspace.py`다. `find`/`--help`/raw Git probe로 같은 위치·사용법을 매번 재탐색하지 않는다.
- Codex context는 초기 `kanban_show`의 worker_context/current_run_id를 확인한다. native shell에 scrub된 Kanban ownership 변수를 재주입하지 않는다.
- 미확인 세션은 `SESSION_HISTORY_BEST_EFFORT_V1`, pending 기록은 기존 `SESSION_HISTORY_FINALIZE`를 그대로 따른다.

Maven canonical launcher는 `/usr/local/bin/hermes-maven`이다. `hermes-java ./mvnw ...`와 `hermes-java mvn ...`도 Maven launcher로 위임하며 raw Wrapper/global Maven으로 조용히 fallback하지 않는다. `mvn` 입력도 현재 build root에 Wrapper properties가 있으면 프로젝트 버전을 우선한다. Wrapper가 없는 프로젝트의 명시적 `mvn` 입력만 기존 설치된 executable을 사용한다. 새로운 전역 설치, 사내 의존성 임의 대체, Maven 버전 변경은 하지 않는다.

Git Workspace는 primary worktree의 `.hermes/toolchain.env`, Non-Git은 현재 위치에서 가장 가까운 canonical toolchain을 사용한다. build root가 하위 module이면 승인된 build root를 cwd로 지정하고 해당 `./mvnw`를 전달한다. multi-module의 `-pl`/`-am` 등 승인 옵션은 보존한다. 서로 다른 저장소의 설정을 자동 검색·혼합하지 않는다.

## 진단과 준비

```bash
/usr/local/bin/hermes-maven --diagnose ./mvnw
```

이 호출은 지정 toolchain, Maven executable 예상 경로, repository, 기존 상위 디렉터리 쓰기 가능 여부만 확인한다. 다운로드·캐시 생성·컴파일을 하지 않는다. `READY`는 executable 존재, `PREPARATION_REQUIRED`는 프로젝트 배포본 준비 필요일 뿐 compile/test 성공 증거가 아니다. helper 부재라면 지정 `/usr/local/bin/hermes-maven`만 확인한 뒤 `MAVEN_LAUNCHER_MISSING`으로 관리 단계에 전달한다. `/`·`/workspace` 전체, HOME cache, Windows disk에서 `mvn`/Spring JAR를 찾지 않는다.

실제 검증은 승인된 다운로드/네트워크 정책 안에서 프로젝트 `distributionUrl`의 배포본을 DevKit cache에 준비한다. 이것은 이미 선택된 toolchain 준비이며 전역 Maven 설치/버전 업그레이드가 아니다. 네트워크 사용 승인이 없거나 오프라인 계약이면 관리 단계에서 배포본·의존성을 먼저 준비한다. wrapper script는 실행·개행 수정하지 않고 properties만 읽으므로 CRLF `mvnw` 자체는 blocker가 아니다.

기본 cache는 `/opt/data/maven/{repository,distributions,downloads,locks}`이며 HOME의 `.m2` 유무와 독립이다. 저장소 경로는 `MAVEN_REPOSITORY` 출력이 기준이다. 빈 저장소만으로 차단하지 않는다. 실제 artifact 해석/원격 접근 실패를 구분한다. `.m2/settings.xml`이나 승인 `-s` 설정은 기존 Maven 동작대로 유지하지만 secret을 로그/카드에 복사하지 않는다. `maven.repo.local`을 CLI/환경/.mvn 설정에서 덮어쓰는 것은 금지한다. 프로젝트 `target` 출력 위치는 이번 변경에서 옮기지 않는다.

## 승인된 compile/test 실행

```bash
python3 /opt/custom-skills/coder/dev-implement-plan/scripts/maven_verification.py \
  --workspace "<approved build root>" --wrapper ./mvnw --mode COMPILE \
  -- -B -DskipTests compile
```

```bash
python3 /opt/custom-skills/coder/dev-implement-plan/scripts/maven_verification.py \
  --workspace "<approved build root>" --wrapper ./mvnw --mode TARGETED_TEST \
  -- -B -Dtest=<approved-test-selector> test
```

명령은 예시이며 Task의 승인 goal/profile/selector/module/options가 우선한다. compile 성공을 실제 JSP/SiteMesh/Tomcat HTTP 회귀 검증 성공으로 바꾸지 않는다. Test skip/no-tests-success 옵션으로 필수 테스트를 통과한 것처럼 처리하지 않는다.

기본 제한은 COMPILE 300초, TARGETED_TEST/PACKAGE/VERIFY 600초다. `HERMES_MAVEN_COMPILE_TIMEOUT_SECONDS`, `HERMES_MAVEN_VERIFY_TIMEOUT_SECONDS` 또는 승인된 `--timeout-seconds`로 지정한다. helper는 한 번 실행하고 시간 초과 시 프로세스 그룹과 자식 프로세스를 종료·회수한다. 실패 후 같은 명령/`--info` 변형/백그라운드 대기/raw Maven 우회를 반복하지 않는다. 원인 수정 또는 승인된 환경 복구 후 재검증한다.

`MAVEN_STATUS`, `MAVEN_BLOCKER`, exit code, 소요 시간, `MAVEN_LOG`, `MAVEN_EVIDENCE`를 handoff한다. raw command args 대신 SHA-256을 receipt에 보관해 credential 노출을 줄인다. 실제 승인 command는 secret을 제거한 형태로 Task 근거에 별도 기록한다. Maven의 기존 incremental/dependency cache는 재사용하지만 이 helper는 Gradle fingerprint 자동 PASS 재사용 기능을 제공하지 않는다. Reviewer는 변경 후 최신 evidence인지 검토하고 필요한 재검증만 실행한다.

## 차단 분류와 재개

- `MAVEN_LAUNCHER_MISSING` / `MAVEN_TOOLCHAIN_MISSING` / `MAVEN_JDK_INVALID`: 이미지·canonical toolchain 확인.
- `MAVEN_CACHE_NOT_WRITABLE`: 표시된 전용 cache 권한 확인. HOME 변경/광범위 chmod로 우회 금지.
- `MAVEN_DISTRIBUTION_*`: 다운로드·체크섬·압축/내부 경로·배포본 lock 원인을 구분.
- `MAVEN_REPOSITORY_OVERRIDE`: 프로젝트/환경과 공용 cache 정책 충돌을 관리 단계에 전달.
- `MAVEN_DEPENDENCY_RESOLUTION_FAILED` / `MAVEN_OFFLINE_DEPENDENCY_MISSING`: 실제 실패 artifact/원격 접근을 secret 없이 기록.
- `MAVEN_COMMAND_TIMEOUT` / `MAVEN_WORKSPACE_LOCK_TIMEOUT`: 실제 제한 초과 기록, 동일 세션의 무작정 반복 금지.
- `MAVEN_BUILD_OR_TEST_FAILED`: 실제 빌드/테스트 오류. 설치 문제로 재분류하지 않는다.

보안 도구가 호출을 거부해 실행되지 않은 경우 `NOT_EXECUTED / APPROVAL_REQUIRED`로 기록한다. 파일/의존성이 없다는 증거로 간주하거나 guard를 완화하지 않는다. worker process `rc=0`과 Kanban 완료는 다르다. 이 변경은 카드 상태, 자동 재시도 정책, run ownership, Reviewer handoff를 변경하지 않는다.
