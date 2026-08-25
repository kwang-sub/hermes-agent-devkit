# Project Pattern Rules

이 문서는 개발 작업에서 **대상 프로젝트의 기존 구조와 코드 패턴을 최대한 동일하게 유지**하기 위한 canonical 규칙이다.

## 1. 핵심 원칙

새 코드는 먼저 현재 프로젝트를 읽고, 이미 존재하는 동일/유사 구현을 reference로 사용한다.

```text
명시된 사용자/Task 정책
        ↓
대상 프로젝트의 기존 구조·명명·구현 패턴
        ↓
DevKit의 stack/capability reference
        ↓
일반적인 framework best practice
```

- 사용자가 명시한 정책은 기존 코드보다 우선한다. 단, 기존 코드와 충돌하면 주변 코드를 대규모로 바꾸지 말고 충돌 사실과 최소 적용 방법을 기록한다.
- package/module 구조, class/file naming, dependency 사용 방식, DTO/Entity/Service/Repository 배치, exception/validation/test convention은 대상 프로젝트를 우선한다.
- 기존 패턴이 단순히 오래됐다는 이유로 architecture, library, naming, response contract를 임의 현대화하지 않는다.
- 기존 방식에 실제 correctness, security, performance, maintainability 문제가 있더라도 요구 범위를 넘어 조용히 고치지 않는다. 필요한 경우 근거와 대안을 제시하고 사용자 결정 후 반영한다.

## 2. 작업 전 탐색

최소한 다음을 확인한다.

```text
build/dependency file
source root와 package/module 구조
동일 또는 유사 기능 1~3개
Controller/API boundary
Service/Application layer
Repository/Data access
Entity/Model/Domain object
Request/Response DTO
공통 Response/Error 규격
Validation/Exception 처리
Test 위치와 framework
프로젝트별 instruction/AGENTS 파일
```

파일 이름만 보고 추정하지 않고 실제 호출 흐름과 사용 위치를 확인한다.

## 3. Reference 선택

새 artifact마다 가능한 한 가장 가까운 기존 reference를 선정한다.

예:

```text
새 User 조회 API
→ 기존 Book 조회 API의 Controller/Service/DTO/Repository 패턴 확인

새 Entity field
→ 같은 module의 Entity mapping/naming/nullability 패턴 확인

새 validation
→ 기존 Request DTO와 GlobalExceptionHandler의 validation error 표현 확인
```

서로 다른 패턴이 공존하면 다음 순서로 선택한다.

1. 같은 module/domain의 최신 사용 패턴
2. 실제 호출이 많은 active pattern
3. 현재 Task와 구조적으로 가장 유사한 pattern
4. 그래도 결정할 수 없으면 임의 통일하지 말고 conflict를 보고한다.

## 4. 개선 제안 Gate

다음 변화는 요구사항에 직접 포함되지 않았다면 자동 적용하지 않는다.

```text
package/layer 재구성
architecture 변경
새 abstraction 도입
공통 response/error contract 교체
library/dependency 추가 또는 교체
대규모 naming 변경
기존 native/legacy 구현의 광범위한 migration
unrelated refactor/formatting
```

개선이 필요하면 다음 형식으로 남긴다.

```text
Current Pattern:
Observed Problem:
Proposed Improvement:
Benefits / Trade-offs:
Required Scope:
Decision Needed:
```

## 5. 구현 Evidence

Coder는 handoff에 최소한 다음을 기록한다.

```text
Pattern References: <재사용한 기존 파일/클래스>
Preserved Conventions: <package/naming/response/test 등>
Intentional Deviations: <없으면 None>
Improvement Deferred: <있으면 이유와 제안>
```

Reviewer는 새 코드가 임의의 새 스타일을 만들지 않았는지 확인하고, 차이가 있다면 요구사항 또는 명시적 정책으로 설명되는지 검증한다.
