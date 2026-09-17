# Infrastructure Transition Policy

## State

```text
Observed State = repository bounded evidence
Desired State  = Task + .hermes/project.yaml infrastructure section
Drift          = Observed와 Desired의 차이
Transition     = 차이를 해소하기 위한 변경 계획
```

Desired default는 `CONTAINER`지만 Observed unknown을 CONTAINER로 채우지 않는다.

## Classification

```text
NO_CHANGE
RUNTIME_CHANGE
HOST_CHANGE
PLATFORM_CHANGE
VENDOR_CHANGE
COMBINED_CHANGE
UNKNOWN
```

## Safety

- detach와 destroy를 구분한다.
- DB container를 detach해도 volume/data는 유지한다.
- persistent data cleanup은 명시적 승인 없이는 실행하지 않는다.
- vendor 변경은 Data Migration Gate 없이는 완료하지 않는다.
- metadata와 repository evidence가 다르면 drift로 보고한다.
- transition 완료 뒤 connection/health/build/test 중 affected verification을 수행한다.
