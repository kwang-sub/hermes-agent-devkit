# Common Coding Rules

이 문서는 **언어와 프레임워크에 관계없이 모든 프로그래밍 작업에 적용하는 Coder/Reviewer 공통 코드 품질 기준**이다.

이 규칙은 프로젝트의 기존 architecture와 convention을 대체하지 않는다. 먼저 현재 프로젝트가 이미 사용하는 구조, naming, error model, data-access pattern, test style과 domain modeling 방식을 확인한 뒤 그 안에서 적용한다.

Stack-specific 또는 capability-specific Skill은 이 규칙을 **확장할 수는 있지만 약화하거나 대체하지 않는다.**

---

# 1. 기존 프로젝트 패턴과 구현을 먼저 확인한다

새 함수, helper, class, abstraction을 만들기 전에 동일하거나 유사한 책임이 프로젝트에 이미 존재하는지 검색한다.

우선 확인 대상:

```text
Utility / Helper
Service / Component
Policy / Strategy / Calculator / Validator
Converter / Mapper / Adapter
Entity / Aggregate / Value Object / Model
Repository / DAO / Data Access abstraction
공통 module / shared library
프로젝트가 이미 사용 중인 framework/library utility
```

기존 구현이 현재 요구사항에 적합하면 새 구현을 만들지 않고 재사용한다.

Coder 개인의 선호 때문에 기존 layer, package/module 구조, naming, error model, transaction boundary, persistence model 또는 domain modeling 방식을 바꾸지 않는다.

기존 코드가 명백히 문제가 있더라도 현재 요구사항과 관계없는 architecture 개선이나 전면 refactor를 같은 작업에 섞지 않는다.

---

# 2. 범용 기술 로직과 Domain Logic을 구분한다

## 2.1 범용 Utility

비즈니스 의미가 없는 범용 기술 기능은 기존 Utility/Helper 또는 사용 중인 library를 먼저 확인한다.

예:

```text
문자열 blank/normalization
날짜 parsing/formatting
숫자 기본값/범위 처리
파일/경로 처리
범용 collection 변환
공통 encoding/hash 처리
```

적용 순서:

```text
기존 동일 기능 존재
  → 재사용

적합한 기존 Utility/Helper 존재
  → 기존 위치에 추가 검토

기존 구현 없음 + 여러 위치에서 재사용 가능한 범용 기능
  → 새 Utility/Helper 생성 검토
```

특정 클래스에서 한 번만 사용하는 작은 표현을 단지 짧다는 이유로 공통 Utility로 이동하지 않는다.

## 2.2 Domain Logic

비즈니스 의미가 있는 로직을 `SomethingUtil`, `CommonHelper` 같은 범용 기술 클래스에 넣지 않는다.

먼저 책임을 판단한다.

```text
Domain Logic
   ↓
특정 Entity / Value Object / Domain Object 자신의 상태·행위·불변식인가?
   ├─ YES → 해당 Domain Object 우선
   └─ NO
        ↓
     하나의 Domain Object에 자연스럽게 귀속되지 않는 규칙인가?
        ├─ DDD 프로젝트
        │    → Domain Service / Policy / Calculator / Validator 등 검토
        └─ 비DDD 프로젝트
             → 기존 Service / Component / Model 패턴 우선
```

### DDD 프로젝트

DDD를 따르는 프로젝트에서도 모든 도메인 로직을 Domain Service로 옮기지 않는다.

특정 Entity/Aggregate/Value Object 자신의 상태와 불변식을 다루는 행위는 해당 Domain Object에 두는 것을 우선한다.

여러 Domain Object 또는 여러 비즈니스 규칙을 조합하며 특정 객체 하나에 귀속하기 어려울 때만 Domain Service, Policy, Calculator, Validator 같은 Domain Component를 검토한다.

### 비DDD 프로젝트

DDD를 사용하지 않는 프로젝트에서는 기존 Model/Entity가 어떤 역할을 맡고 있는지 먼저 확인한다.

- 기존 Model/Entity가 Rich Domain Model이면 자기 상태에 대한 행위를 추가할 수 있다.
- 기존 Model/Entity가 persistence/data-transfer 중심의 단순 모델이면 Coder가 임의로 Rich Domain Model로 전환하지 않는다.
- 이 경우 프로젝트가 이미 사용하는 Service/Component/Helper 구조를 우선한다.

DB, 외부 API, 파일 시스템, 메시지 브로커 등 infrastructure 의존성이 필요한 로직을 Domain Object에 억지로 넣지 않는다.

---

# 3. 함수/메서드는 하나의 명확한 책임을 갖는다

함수나 메서드 하나가 조회, validation, 변환, 저장, 외부 I/O, 후처리 등을 동시에 수행하면 책임 분리를 검토한다.

절대적인 line count보다 다음 질문으로 판단한다.

```text
이 함수/메서드를 하나의 동사 또는 책임으로 설명할 수 있는가?
이름과 실제 수행 범위가 일치하는가?
분리하면 테스트와 오류 경계가 더 명확해지는가?
추출된 함수가 의미 있는 이름과 책임을 갖는가?
```

단순히 함수를 작게 보이게 하기 위해 `process1`, `handle2`, `doWorkInternal`처럼 의미 없는 wrapper를 양산하지 않는다.

---

# 4. 실행 Block Depth는 기본 최대 2-depth로 유지한다

함수/메서드 내부 실행 block의 중첩은 기본적으로 최대 2-depth를 넘기지 않는다.

대상 예:

```text
if / else
for / while / loop
switch / when / match
try / catch / except
lambda / callback body
기타 중첩 실행 block
```

2-depth를 초과하면 다음을 우선 검토한다.

```text
guard clause / early return / continue
복잡한 조건식의 의미 있는 함수 추출
반복 처리의 책임 단위 함수 추출
조회 / 변환 / 저장 / 후처리 분리
도메인 또는 application component로 책임 이동
```

정상 흐름 전체를 깊은 조건문에 넣기보다 실패/제외 조건을 먼저 처리하는 Guard Clause를 우선한다.

2-depth 규칙은 기계적인 숫자 맞추기가 아니다. 단순하고 읽기 쉬운 코드까지 불필요하게 쪼개지 않으며, 중첩 때문에 흐름과 책임이 불명확해질 때 분리를 요구한다.

---

# 5. 주석과 Documentation은 목적과 이유를 설명한다

새로 작성하거나 의미 있게 수정하는 주요 함수/메서드와 비직관적 흐름에는 목적과 동작을 이해할 수 있는 설명을 작성한다.

프로젝트와 언어가 지원하는 documentation convention을 우선한다.

예:

```text
Java      → JavaDoc
Kotlin    → KDoc
Python    → docstring
TypeScript/JavaScript → JSDoc 또는 프로젝트 기존 convention
기타 언어 → 프로젝트의 표준 documentation 방식
```

좋은 주석/documentation은 다음을 설명한다.

```text
왜 이 처리가 필요한지
주요 처리 흐름이 무엇인지
특별한 비즈니스/호환성/동시성 제약이 무엇인지
직관적이지 않은 알고리즘이나 식별자 생성 규칙의 이유
외부 시스템 또는 legacy format과의 호환성 이유
```

다음처럼 코드를 그대로 번역하는 주석은 작성하지 않는다.

```text
// null인지 확인한다
// 데이터를 저장한다
// 리스트를 반복한다
```

주석은 코드 변경 후 실제 동작과 일치해야 한다. 오래되었거나 잘못된 주석을 발견했으며 현재 변경과 직접 관련 있다면 함께 수정한다.

---

# 6. 반복문 안의 DB/API/File I/O를 점검한다

`for`, `loop`, `stream`, `map`, `forEach`, collection pipeline 내부에서 다음 호출이 반복되면 비용과 N+1 형태의 문제를 확인한다.

```text
DB / Repository / DAO query
HTTP / RPC / external API
파일 open/read/write
메시지 broker 호출
원격 cache/network I/O
고비용 process 실행
```

가능하면 프로젝트의 기존 패턴 안에서 다음을 검토한다.

```text
batch/bulk request
IN/bulk query
join/fetch/projection
한 번 조회 후 Map/grouping 구성
외부 요청 묶음 처리
I/O 경계 밖으로 반복 불변 작업 이동
```

단, 실제 데이터 규모와 호출 특성을 확인하지 않고 무조건 복잡한 최적화를 추가하지 않는다.

---

# 7. 기존 타입과 공통 Abstraction을 우선한다

Magic String/Number 또는 동일 의미의 새 타입을 만들기 전에 기존 Constant, Enum, sealed type, value type, Converter, Mapper, Validator 등의 존재 여부를 확인한다.

같은 의미가 이미 타입으로 표현되어 있다면 primitive/string 상수를 중복 생성하는 것보다 기존 타입을 재사용한다.

새 abstraction을 만드는 경우에는 현재 요구사항뿐 아니라 프로젝트의 기존 책임 경계와 naming convention에 자연스럽게 들어맞는지 확인한다.

---

# 8. Error Handling에서 실패를 숨기지 않는다

오류를 catch/except한 뒤 아무 처리 없이 삼키지 않는다.

- 복구 가능한 실패는 retry/skip/fallback 조건과 필요한 context를 남긴다.
- 복구 불가능한 실패는 원인 error/exception을 보존한다.
- 원인과 실제 운영 영향을 판단할 수 있는 context를 남긴다.
- credential, token, password, cookie, raw sensitive value를 log/error message에 기록하지 않는다.
- 기존 프로젝트의 exception/error model을 우선한다.

불필요하게 모든 예외를 최상위 generic error로 바꾸어 root cause를 잃지 않는다.

---

# 9. 최소 변경과 기존 Architecture 일관성을 유지한다

요구사항을 만족하는 가장 작은 diff를 우선한다.

같은 작업에 다음을 섞지 않는다.

```text
unrelated refactor
대규모 formatting
불필요한 rename
dependency upgrade
architecture 변경
legacy cleanup
요구되지 않은 API/schema 변경
```

Stack-specific 또는 capability-specific Skill이 로드되어 있더라도 해당 Skill의 목적 범위 밖 변경을 자동으로 확장하지 않는다.

---

# 10. 변경과 직접 연결된 검증을 수행한다

가능한 가장 좁은 targeted verification부터 실행하고 필요할 때만 범위를 넓힌다.

관련될 경우 다음을 확인한다.

```text
normal path
null / empty / missing
boundary
failure path
retry / duplicate execution
idempotency
transaction / concurrency
backward compatibility
serialization / persistence compatibility
```

프로젝트에 test framework가 존재하면 기존 test style을 따른다.

실제로 실행하지 않은 검증을 PASS라고 보고하지 않는다.

Repository/Tooling상 가능하면 Reviewer handoff 전 `git diff --check`를 실행한다.

---

# 11. Stack/Capability Skill 확장 규칙

이 공통 규칙은 구현의 **기반 품질 계약**이다.

추후 추가되는 Stack/Capability Skill은 다음 구조로 이 규칙 위에 쌓인다.

```text
Common Coding Rules
        ↓
dev-implement-plan
        ↓
Optional Stack / Capability Skill
        ↓
Project-specific convention
        ↓
Implementation
        ↓
Reviewer
```

전문 Skill은 다음을 지킨다.

- 공통 Coding Rules를 복사해 자체 문서에 중복하지 않는다.
- 현재 프로젝트 pattern 검색을 먼저 수행한다.
- 언어/프레임워크별 특수 규칙만 추가한다.
- 프로젝트의 이미 사용 중인 library/version/convention을 우선한다.
- 필요하지 않은 dependency를 자동 추가하지 않는다.
- 여러 구현 방식이 합리적이고 사용자 선택이 필요한 경우 명시적인 선택을 받는다.
- 생성/적용 결과에 대한 stack-specific verification을 정의한다.
- Reviewer가 검증할 수 있는 명확한 Acceptance Criteria와 evidence를 남긴다.

예정된 Spring 계열 Capability Skill 예:

```text
dev-spring-openapi
  → 기존 SpringDoc/Swagger 설정 탐색
  → Swagger UI 또는 Postman 산출물 선택
  → Controller/DTO schema 반영 및 검증

dev-spring-validation
  → 기존 Bean Validation / custom validator 탐색
  → 기존 Validator 재사용 우선
  → 필요 시 Enum/annotation/validator 생성
  → Request DTO에 validation 적용 및 실패 케이스 검증

dev-jpa-converter
  → 기존 AttributeConverter 탐색
  → Java/Kotlin 및 Entity mapping convention 확인
  → Converter 생성/등록/적용
  → persistence round-trip 검증
```

Spring Capability Skill은 가능한 경우 Java와 Kotlin을 별도 Skill로 나누지 않고 **하나의 Spring Skill 안에서 현재 프로젝트 언어와 convention을 감지**한다. 언어별 차이가 충분히 클 때만 내부 reference를 분리한다.

---

# 12. Reviewer Quality Gate

Reviewer는 correctness 검토와 함께 관련 있는 경우 다음을 확인한다.

- 새 helper/class가 기존 프로젝트 구현을 불필요하게 중복하지 않는가.
- 범용 Utility와 Domain Logic의 위치가 책임에 맞는가.
- DDD 프로젝트에서 Entity/Value Object 책임을 불필요하게 Domain Service로 밀어내지 않았는가.
- 비DDD 프로젝트에서 기존 model 역할과 다른 domain modeling을 갑자기 도입하지 않았는가.
- 함수/메서드 실행 block이 2-depth를 반복적으로 초과하며 책임 분리가 필요한가.
- 하나의 함수/메서드가 여러 책임을 과도하게 수행하지 않는가.
- 주요 함수/비직관적 흐름의 documentation이 목적과 이유를 설명하는가.
- 코드 번역형 또는 실제 동작과 다른 주석이 추가되지 않았는가.
- 반복문 내부 DB/API/File/Network I/O로 불필요한 반복 호출이 발생하지 않는가.
- 기존 Constant/Enum/Validator/Converter/Mapper 등 재사용 가능한 abstraction을 중복 구현하지 않았는가.
- 오류를 숨기거나 민감정보를 log에 남기지 않는가.
- 변경 범위와 테스트가 요구사항에 맞는가.
- Task에 Stack/Capability Skill이 사용되었다면 해당 Skill의 stack-specific Acceptance Criteria와 verification도 충족하는가.

이 항목은 취향 기반 style gate가 아니다. 기존 프로젝트 pattern과 실제 correctness, maintainability, performance에 의미가 있을 때만 Blocking Finding으로 판단한다.
