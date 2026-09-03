# Gradle timeout 관찰 정책

현재 DevKit은 Gradle timeout 원인이 확정되지 않은 상태에서 Host IntelliJ/애플리케이션 실행 여부를 정책으로 강제하지 않는다.

## 원칙

- Host에서 대상 프로젝트를 실행 중이거나 IntelliJ/Gradle이 같은 workspace를 사용하는 상황을 **자동 차단하지 않는다**.
- Container에서는 Host 프로세스 상태를 신뢰성 있게 확정할 수 없으므로 `HOST_ACTIVITY=UNKNOWN`으로 기록한다.
- Gradle timeout이 실제 발생했을 때만 관찰 로그를 저장한다.
- 반복된 timeout 로그에서 동일 패턴이 확인된 뒤에만 Host/Container 동시 사용 정책을 결정한다.
- 정상 PASS 또는 일반 BUILD_FAILURE에는 timeout 관찰 로그를 만들지 않는다.

## 저장 위치

기본값:

```text
/opt/data/gradle/diagnostics/<workspace-name>/
```

파일명:

```text
<UTC timestamp>--<Kanban Task ID>--<Hermes Session ID>.log
```

`/opt/data` named volume에 저장되므로 일반적인 컨테이너 재생성 후에도 유지된다.

## 기록 항목

대표 항목:

```text
OBSERVED_AT_UTC=
WORKSPACE=
MODE=
HERMES_KANBAN_TASK=
HERMES_SESSION_ID=
HOST_ACTIVITY=UNKNOWN
HOST_ACTIVITY_POLICY=OBSERVE_ONLY
WORKSPACE_FILESYSTEM=
PRIMARY_RESULT=
PRIMARY_DURATION_SECONDS=
PRIMARY_COMMAND=
PRIMARY_LAST_TASK=
PRIMARY_TIMEOUT_PROCESS_*=...
GRADLE_BLOCKER=
GRADLE_TIMEOUT_DETAIL=
GRADLE_ROOT_CAUSE_CANDIDATES=
DIAGNOSTIC_ONLINE_RESULT=
DIAGNOSTIC_OFFLINE_RESULT=
DIAGNOSTIC_DRY_RUN_RESULT=
```

## 정책 결정 시점

단일 timeout만으로 다음과 같은 정책을 추가하지 않는다.

- IntelliJ 종료 강제
- Host 애플리케이션 실행 금지
- Host Gradle daemon 종료 강제
- workspace 동시 사용 차단

대신 여러 관찰 로그에서 다음과 같은 상관관계가 반복 확인될 때 정책화를 검토한다.

- Host에서 대상 프로젝트 실행 중일 때만 timeout 반복
- 같은 workspace의 Host Gradle build와 Container Gradle timeout이 반복적으로 동시 발생
- process snapshot이 지속적인 wait/lock/I/O 대기를 가리킴
- bind mount filesystem에서만 재현되고 별도 Linux workspace에서는 재현되지 않음

정책이 필요해질 경우에도 원인과 영향 범위를 먼저 정리한 뒤 DevKit 운영 규칙으로 별도 반영한다.
