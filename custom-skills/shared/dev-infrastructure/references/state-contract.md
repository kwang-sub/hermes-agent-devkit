# State Contract

Desired State는 `.hermes/project.yaml`의 `infrastructure:` section 또는 명시적 Task 요구에서 읽는다. Observed State는 repository evidence에서 계산한다.

```yaml
infrastructure:
  version: "1"
  application_runtime: "CONTAINER"
  database_runtime: "CONTAINER"
  database_platform: "NATIVE"
  database_vendor: "UNKNOWN"
```

`UNKNOWN` observed 값을 default로 채우지 않는다. 명시적 evidence와 desired metadata가 다르면 drift다.
