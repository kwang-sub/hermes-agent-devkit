# Runtime Topology

## 축 분리

실행 위치(Runtime), 플랫폼(Platform), DB Vendor를 독립 축으로 관리한다.

```text
Application Runtime = LOCAL_HOST | NETWORK_HOST | CONTAINER
Database Runtime    = LOCAL_HOST | NETWORK_HOST | CONTAINER
Database Platform   = NATIVE | SUPABASE
Database Vendor     = postgresql | mysql | mariadb | mssql | oracle | unknown
```

## 연결 조합

| Application | Database | 기본 연결 개념 |
| --- | --- | --- |
| CONTAINER | CONTAINER | compose/service network hostname |
| LOCAL_HOST | CONTAINER | published port + localhost |
| CONTAINER | LOCAL_HOST | host 접근 경로; OS/runtime evidence 필요 |
| LOCAL_HOST | NETWORK_HOST | remote endpoint |
| CONTAINER | NETWORK_HOST | container -> remote endpoint |
| NETWORK_HOST | NETWORK_HOST | metadata/connection 지원; 자동 배포는 현재 범위 밖 |

`host.docker.internal`, `host-gateway` 등 구현 세부는 실제 대상 OS/런타임 evidence가 있을 때만 적용한다.

## 우선순위

```text
1. 사용자/Task 명시 요구
2. 기존 infrastructure desired metadata
3. 명확한 Repository observed evidence
4. 기본값 CONTAINER
```

기존 프로젝트에서 observed evidence가 명확하면 4번 기본값으로 덮어쓰지 않는다.

## 상태

```text
READY
PARTIAL
NOT_CONFIGURED
UNKNOWN
```

`Runtime=CONTAINER`와 `Dockerfile/Compose가 이미 준비됨`은 다른 사실이다.

## Drift

Observed State는 매 실행 시 Repository evidence로 다시 계산한다. metadata는 Desired State로만 해석한다.

```text
Observed != Desired
→ drift
→ transition plan
→ apply
→ verify
```
