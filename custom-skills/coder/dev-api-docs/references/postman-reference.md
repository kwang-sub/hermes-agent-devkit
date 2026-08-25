# Postman Collection Reference

`dev-api-docs`가 Postman Collection을 생성하거나 갱신할 때 사용하는 로컬 기준이다.

실제 API source contract와 기존 프로젝트의 collection/environment 구조를 항상 우선한다.

## 기본 구조

기존 Collection이 없을 때의 기본 grouping 후보:

```text
Collection
├─ Auth
├─ <Domain A>
│  ├─ Create
│  ├─ Get
│  ├─ Search
│  ├─ Update
│  └─ Delete
└─ Variables
```

실제 프로젝트에 이미 folder/group convention이 있으면 그대로 유지한다.

## Variable 정책

가능하면 reusable environment/collection variable을 사용한다.

```text
baseUrl
accessToken
refreshToken  # 실제 API에서 필요할 때만
resourceId    # 반복 테스트에 유용할 때만
```

규칙:

- 실제 credential/token 값을 repository에 저장하지 않는다.
- 예시 token이 필요하면 명백한 placeholder를 사용한다.
- localhost/port도 기존 프로젝트 environment가 있으면 재사용한다.

## Request Contract

각 request는 실제 source와 일치해야 한다.

```text
HTTP Method
URL / Path
Path Parameters
Query Parameters
Headers
Authentication
Request Body
```

Request body example은 실제 DTO field/type/validation과 어긋나지 않게 작성한다.

## Response Example

가능하면 다음을 포함한다.

```text
대표 성공 응답
대표 validation error
대표 business/not-found error
인증 관련 오류 (실제 endpoint에 해당할 때)
```

API에 공통 Response wrapper가 있으면 success/error example 모두 해당 wrapper를 반영한다.

## OpenAPI BOTH Mode Consistency

OpenAPI와 Postman을 함께 만들 때 어느 문서도 다른 문서를 source of truth로 간주하지 않는다.

```text
Application Source Contract
    ├─ OpenAPI
    └─ Postman
```

두 artifact에서 다음이 동일한지 확인한다.

```text
method/path
parameter name/type
required/optional
request body
success status/response
known error contract
auth scheme
```

## Validation Checklist

```text
[ ] Collection JSON이 유효함
[ ] 모든 URL이 실제 route와 일치
[ ] required header/auth가 반영됨
[ ] secret/raw token 없음
[ ] request body example이 DTO와 일치
[ ] success/error response가 실제 contract와 일치
[ ] OpenAPI 동시 생성 시 두 문서 contract 일치
```
