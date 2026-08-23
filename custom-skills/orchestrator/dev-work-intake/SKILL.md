---
name: dev-work-intake
description: Jira Cloud Issue를 Read-only로 조회해 Source-independent Common Work Item JSON/Markdown으로 정규화한다. Jira 인증/설정은 Container Environment를 우선 사용한다.
version: 0.1.3
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, intake, jira, work-item, orchestrator]
    related_skills: [dev-project-resolve, dev-breakdown, dev-workflow-orchestrate]
    requires_tools: [terminal]
---

# dev-work-intake

외부 Work Source의 요구사항을 **Source-independent Common Work Item**으로 정규화하는 Intake 계층이다.

현재 구현된 Adapter는 **Jira Cloud**다.

```text
Jira Cloud
    ↓
dev-work-intake
    ↓
Normalized Work Item
    ↓
dev-project-resolve
    ↓
사용자 Project Approval
    ↓
dev-breakdown
```

이 Skill은 **orchestrator 전용**이다.

Jira와 Source Repository에 대해 Read-only로 동작한다.

`dev-workflow-orchestrate`의 최초 입력은 Jira 또는 Text가 될 수 있지만, v0.1.3의 이 Skill이 실제로 제공하는 Source Adapter는 Jira뿐이다. Text Request는 상위 Workflow가 원문을 Common Work Item으로 취급하며, Jira Adapter 로직을 억지로 재사용하지 않는다.

---

# 1. 존재 이유

Downstream Development Skill이 Jira 전용 Data Structure에 종속되면 안 된다.

`dev-breakdown`은 작업 출처가 다음 중 무엇이든 동일한 Normalized Contract를 받아야 한다.

- Jira
- Notion
- Slack
- GitHub
- Plain Text
- Future Source

따라서 Source-specific Parsing은 Intake 계층에 둔다.

Normalized Work Item은 다음 경계다.

```text
source-specific intake
```

과:

```text
source-independent development planning
```

---

# 2. Normalized Work Item 계약

Jira Adapter는 Canonical JSON을 생성한다.

```text
/opt/data/work-items/jira/<ISSUE-KEY>.json
```

사람이 읽는 Markdown도 함께 생성한다.

```text
/opt/data/work-items/jira/<ISSUE-KEY>.md
```

JSON 구조:

```json
{
  "version": 1,
  "source": {
    "type": "jira",
    "deployment": "cloud",
    "ref": "POBA-123",
    "url": "https://example.atlassian.net/browse/POBA-123"
  },
  "work": {
    "id": "POBA-123",
    "title": "...",
    "description": "...",
    "acceptance_criteria": ["..."],
    "comments": [],
    "labels": [],
    "components": [],
    "dependencies": [],
    "constraints": [],
    "custom_fields": {}
  },
  "project_hints": {
    "jira_project_key": "POBA",
    "components": [],
    "labels": []
  },
  "jira": {
    "status": "...",
    "issue_type": "...",
    "priority": "...",
    "assignee": "...",
    "reporter": "...",
    "parent": null,
    "subtasks": [],
    "issue_links": []
  }
}
```

Authentication Secret을 Work Item Artifact에 넣지 않는다.

---

# 3. Jira Cloud 전용

현재 버전은 의도적으로 **Jira Cloud만** 지원한다.

Jira 설정은 기본적으로 Docker Compose Project의 `.env`에서 Container Environment Variable로 전달한다.

```text
D:\docker\hermes-agent\.env
        ↓ Docker Compose environment:
        ↓
hermes-dev process environment
        ↓
dev-work-intake
```

Backward Compatibility를 위해 다음 Profile-local File은 **Optional Fallback**으로만 사용한다.

```text
/opt/data/profiles/orchestrator/.env
```

필요하면 Fallback Path를 변경할 수 있다.

```text
JIRA_ENV_FILE=/another/path/.env
```

Process Environment가 항상 우선한다. 필요한 Jira Variable이 Process Environment에 있으면 Fallback File은 없어도 된다.

권장 `.env`:

```dotenv
# Jira Cloud
JIRA_BASE_URL=https://your-company.atlassian.net
JIRA_EMAIL=user@example.com
JIRA_API_TOKEN=replace-with-api-token
JIRA_API_VERSION=3

# Jira field mapping
JIRA_ACCEPTANCE_CRITERIA_FIELDS=Acceptance Criteria,완료 조건,인수 조건
JIRA_INCLUDE_FIELD_NAMES=

# TLS
JIRA_VERIFY_SSL=true
# JIRA_CA_FILE=/opt/data/certs/company-ca.pem

# Normalized Work Item output
HERMES_WORK_ITEM_DIR=/opt/data/work-items
```

Cloud-only Mode에서는 다음 값이 필요하지 않다.

```text
JIRA_DEPLOYMENT
JIRA_AUTH
JIRA_PAT
JIRA_USERNAME
JIRA_PASSWORD
```

Jira Cloud Authentication:

```text
email + API token
```

HTTP Basic Authentication을 사용한다.

---

# 4. Configuration / Secret 위치

Primary Configuration Source:

```text
Docker Compose project .env
→ container environment variables
```

Optional Compatibility Fallback:

```text
/opt/data/profiles/orchestrator/.env
```

Fallback File은 없어도 된다.

Jira Credential을 다음에 기록하지 않는다.

- `AGENTS.common.md`
- Project `AGENTS.md` / `CLAUDE.md`
- `.hermes/project.yaml`
- Skill File
- Kanban Task Body
- Normalized Work Item JSON/Markdown
- Git Repository

`.env`는 Configuration/Secret 저장용이다.

생성된 Work Item은 다음에 유지한다.

```text
/opt/data/work-items/jira/
```

Normalized Jira Data를 `.env`에 넣지 않는다.

---

# 5. 선택적 Jira Environment Variable

## `JIRA_API_VERSION`

Jira Cloud REST API Version Override.

기본:

```text
3
```

## `JIRA_ACCEPTANCE_CRITERIA_FIELDS`

Acceptance Criteria로 취급할 Jira Field Display Name의 Comma-separated List.

기본:

```text
Acceptance Criteria,Acceptance criteria,Acceptance Criterion,AC
```

예:

```text
JIRA_ACCEPTANCE_CRITERIA_FIELDS=Acceptance Criteria,완료 조건,인수 조건
```

## `JIRA_INCLUDE_FIELD_NAMES`

`work.custom_fields`에 보존할 추가 Custom Field Display Name.

## `JIRA_VERIFY_SSL`

기본:

```text
true
```

Certificate Verification이 불가능한 통제된 내부 Test에서만 `false`를 고려한다.

Internal PKI라면 다음 방식을 우선한다.

```text
JIRA_CA_FILE=/opt/data/certs/company-ca.pem
```

## `HERMES_WORK_ITEM_DIR`

기본:

```text
/opt/data/work-items
```

---

# 6. 연결 Test

Issue 조회 전에 Jira Authentication을 검증한다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/jira_intake.py" --check
```

성공 예:

```text
STATUS=connected
DEPLOYMENT=cloud
API_VERSION=3
USER=...
BASE_URL=...
ENV_FILE=/opt/data/profiles/orchestrator/.env
```

Authentication 실패 시 진행하지 않는다.

대표 실패:

- `401`: Credential 누락/오류
- `403`: 인증 계정의 Permission 부족
- `404`: Base URL / Context Path / API Version 오류
- TLS Error: Certificate / CA 문제

실패 보고에 Secret Value를 출력하지 않는다.

---

# 7. Issue 조회 및 정규화

실행:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/jira_intake.py" \
  --issue "POBA-123"
```

Adapter 동작:

1. Configuration 검증
2. Jira Issue Read-only 조회
3. Jira Field-name Metadata 요청
4. Pagination으로 모든 Visible Comment 조회
5. Jira Cloud ADF Rich Text를 Plain Text로 정규화
6. 다음 정보 추출
   - Title
   - Description
   - Acceptance Criteria
   - Comments
   - Labels
   - Components
   - Issue Type/Status/Priority
   - Assignee/Reporter
   - Parent/Subtasks
   - Issue Links/Dependencies
   - Configured Custom Fields
7. Project Hint 생성
8. JSON + Markdown Work Item Artifact 생성
9. Artifact Path 출력

예상 출력:

```text
SOURCE=jira
ISSUE_KEY=POBA-123
PROJECT_KEY=POBA
TITLE=...
JSON_FILE=/opt/data/work-items/jira/POBA-123.json
MARKDOWN_FILE=/opt/data/work-items/jira/POBA-123.md
STATUS=normalized
```

---

# 8. Acceptance Criteria 추출

Jira Instance는 Acceptance Criteria를 Custom Field에 저장할 수 있다.

Adapter는 Issue Response의 Field-name Expansion을 사용해 Field ID와 Display Name을 연결한다.

다음 설정과 Match한다.

```text
JIRA_ACCEPTANCE_CRITERIA_FIELDS
```

비어 있지 않은 Matched Field마다:

- Rich Text를 Plain Text로 변환
- 가능한 경우 List-like Value를 개별 Criteria로 변환
- 추가 Criteria를 만들어내지 않고 원 Value 보존

Jira에 명시적 Acceptance Criteria가 없으면:

```text
work.acceptance_criteria = []
```

Intake 단계에서 Acceptance Criteria를 만들어내지 않는다.

`dev-breakdown`이 이후 Test 가능한 Planning Criteria로 명확히 할 수 있지만 Source Fact와 Planning Inference를 구분해야 한다.

---

# 9. Comment

Comment는 Read-only로 모두 가져오고 다음을 보존한다.

- 보이는 경우 Author Display Name
- Created/Updated Timestamp
- Normalized Body Text

Comment에는 Decision, Clarification, Unresolved Discussion이 포함될 수 있다.

Intake Adapter는 어떤 Comment가 최종 권위인지 임의 판단하지 않는다.

`dev-breakdown`이 Requirement와 함께 해석하고 모호하면 보고한다.

---

# 10. Project Hint

Adapter는 Hermes Project를 직접 결정하지 않고 Hint만 출력한다.

Jira 기준:

```text
project_hints.jira_project_key
project_hints.components
project_hints.labels
```

예:

```json
{
  "project_hints": {
    "jira_project_key": "POBA",
    "components": ["Dashboard"],
    "labels": ["backend"]
  }
}
```

이후 `dev-project-resolve`가 등록된 `.hermes/project.yaml` Metadata와 비교한다.

다음을 가정하지 않는다.

```text
Jira project key == Hermes project id
```

Project Metadata가 명시적으로 Mapping하지 않는 한 동일하지 않다.

Resolver가 Candidate를 찾은 이후에도 사용자 Project Approval이 필요하다.

---

# 11. Downstream Handoff

정규화 후 Work Item을 Requirement Source로 사용한다.

권장:

```text
Read:
  /opt/data/work-items/jira/POBA-123.md

Then:
  dev-project-resolve
  사용자 Project Approval
  dev-breakdown
```

Breakdown은 다음 Source Fact를 보존해야 한다.

- Original Title
- Original Description
- Explicit Acceptance Criteria
- Comments
- Dependencies
- Constraints

이 Fact에서 Implementation Plan을 도출할 수 있지만 불확실성을 Source Record 수정으로 숨기지 않는다.

---

# 12. Read-only 안전 규칙

Jira Adapter는 절대 다음을 하지 않는다.

- Jira Issue 생성
- Jira Issue 수정
- Status Transition
- Comment 추가/수정/삭제
- Assignee 변경
- Label/Component 변경
- Attachment Upload
- Generated Plan Write-back
- Credential 노출

현재 버전은 의도적으로 **Read-only Intake**다.

향후 Write-back 자동화가 필요하면 별도 명시적 Workflow로 추가한다.

---

# 13. 실패 규칙

다음 경우 Data를 만들어내지 말고 중단/보고한다.

- Issue가 없거나 조회 권한이 없음
- Jira Authentication 실패
- Response Parse 실패
- 필수 Field가 예상하지 못한 Schema
- Downstream에 필요한 Data가 불완전함
- Comment 전체 조회 실패

Partial Data를 보존해야 한다면 Partial임을 명확히 표시한다.

Project Resolution Hint가 약하다는 이유로 Jira Intake 자체가 Repository를 선택해서는 안 된다.

---

# 14. 최초 검증 순서

```text
1. --check
   ↓
2. --issue <known Jira key>
   ↓
3. generated JSON 확인
   ↓
4. generated Markdown 확인
   ↓
5. Jira UI의 title/description/comments/AC와 비교
   ↓
6. Jira에 어떤 수정도 발생하지 않았는지 확인
```

Issue Normalization이 검증된 뒤 Project Resolver에 연결한다.

---

# 15. 향후 Adapter

향후 Source는 동일 Work Item Contract를 구현하고 Downstream Skill을 변경하지 않는 방향으로 확장한다.

계획 구조:

```text
dev-work-intake/
├─ SKILL.md
└─ scripts/
   ├─ jira_intake.py
   ├─ notion_intake.py
   ├─ slack_intake.py
   └─ text_intake.py
```

현재 Text Entry는 `dev-workflow-orchestrate`가 직접 Source-independent Request로 취급하며, 향후 `text_intake.py`가 추가되어도 Downstream Contract는 유지한다.

`dev-breakdown`에 Source-specific Assumption을 넣지 않는다.
