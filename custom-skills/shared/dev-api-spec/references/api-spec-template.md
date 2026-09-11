# <Domain> API

> 프로젝트 기존 API 문서 구조가 있으면 이 템플릿보다 기존 구조를 우선한다.

## 공통 메타데이터

| 항목 | 값 |
|---|---|
| Status | `DRAFT | APPROVED | DEPRECATED` |
| Documentation Source | `DESIGN | APPLICATION_SOURCE | MIGRATED_SPEC` |
| Domain | `<domain>` |
| Last Updated | `<YYYY-MM-DD>` |

---

## <Use Case / Endpoint Name>

### 기본 정보

| 항목 | 값 |
|---|---|
| Status | `DRAFT | APPROVED | DEPRECATED` |
| Documentation Source | `DESIGN | APPLICATION_SOURCE | MIGRATED_SPEC` |
| Use Case | `<what this API does>` |
| Method | `<GET | POST | PUT | PATCH | DELETE>` |
| Path | `</api/...>` |
| Authentication | `<project policy | NONE>` |
| Authorization | `<rule | project common rule>` |

### Request

#### Path Parameters

| Field | Type | Required | Nullable | Description |
|---|---|---:|---:|---|
| `<name>` | `<type>` | `Y/N` | `Y/N` | `<description>` |

#### Query Parameters

| Field | Type | Required | Nullable | Description |
|---|---|---:|---:|---|
| `<name>` | `<type>` | `Y/N` | `Y/N` | `<description>` |

#### Headers

| Header | Required | Description |
|---|---:|---|
| `<name>` | `Y/N` | `<description>` |

#### Body

| Field | Type | Required | Nullable | Description |
|---|---|---:|---:|---|
| `<name>` | `<type>` | `Y/N` | `Y/N` | `<description>` |

### Success Response

**HTTP `<status>`**

| Field | Type | Nullable | Description |
|---|---|---:|---|
| `<name>` | `<type>` | `Y/N` | `<description>` |

### Error

| HTTP | Code | Condition |
|---:|---|---|
| `<status>` | `<ERROR_CODE>` | `<when it occurs>` |

### Contract Notes

- Common Response Wrapper: `<docs/api/README.md 또는 project-specific contract>`
- Money / Decimal: `<representation>`
- Date / Time / Timezone: `<representation>`
- Enum / Code: `<values or reference>`
- Paging / Sorting: `<rule or N/A>`
- Idempotency: `<rule or N/A>`
- Compatibility / Migration: `<note or N/A>`

### Source Evidence

`SOURCE_SYNC`에서만 필요한 범위로 기록한다.

```text
Controller / Route: <file#symbol>
Request DTO: <file#symbol | none>
Response DTO: <file#symbol | none>
Validation: <file#symbol | none>
Error / Handler: <file#symbol | none>
Auth / Security: <file#symbol | project common rule>
OpenAPI: <present | missing | mismatch>
```

Source에서 확정할 수 없는 내용은 추측하지 않고 `Unknown / Review Required`로 남긴다.
