---
name: dev-figma-design
description: Figma frame/component URL에서 공식 REST API로 bounded design context와 preview를 read-only 추출해 dev-design-reference용 provider evidence로 전달한다.
version: 0.2.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, frontend, figma, design, provider, rest, read-only]
    related_skills: [dev-design-reference, dev-frontend-feature, dev-ui-ux, dev-frontend-guidelines, dev-nextjs-feature]
    requires_tools: [terminal]
---

# dev-figma-design

Figma의 구현 대상 frame/component를 **read-only**로 읽는 Design Provider다. Frontend source나 Figma canvas를 수정하지 않는다.

상위 Normalized Design Evidence 계약은 `dev-design-reference`가 소유한다.

## 인증

```text
FIGMA_ACCESS_TOKEN
- Personal Access Token 또는 Plan REST Access Token
- X-Figma-Token header

FIGMA_OAUTH_TOKEN
- OAuth access token
- Authorization: Bearer
```

파일 내용을 읽으려면 `file_content:read` scope가 필요하다. token을 source/Kanban/comment/log에 출력하지 않는다.

## Design Status

```text
DRAFT
→ planning only

REFERENCE
→ 시각/구조 참고

APPROVED
→ REFERENCE_DRIVEN 구현 기준으로 사용 가능
```

상태가 명확하지 않으면 임의로 APPROVED로 승격하지 않는다.

## Canonical targeted read

사용자가 선택한 frame/component의 `node-id`가 포함된 URL을 우선한다.

```bash
python3 /opt/custom-skills/shared/dev-figma-design/scripts/figma_context.py inspect \
  --url "<FIGMA_NODE_URL>" \
  --depth 4 \
  --render
```

필요하면 preview를 안전한 경로에 저장한다.

```bash
python3 /opt/custom-skills/shared/dev-figma-design/scripts/figma_context.py inspect \
  --url "<FIGMA_NODE_URL>" \
  --depth 4 \
  --preview-out "/opt/data/figma-cache/<task>.png"
```

file-level URL은 기본 차단한다. 명시적 planning 탐색이 필요할 때만 `--allow-file`을 사용하며 depth는 bounded다.

## Provider Evidence

직접 API에서 확인한 값은 `OBSERVED` 후보다.

```text
Frame/Component identity
bounding box
Auto Layout 방향/간격/padding
constraints
fill/stroke/effect/radius/opacity
text content/typography
component/style references
interaction/reaction
child hierarchy
render preview URL/path
```

Figma에 정의되지 않은 responsive/product behavior는 `UNKNOWN`으로 남길 수 있다.

raw API 전체 응답은 기본 출력하지 않으며 debugging 근거가 필요할 때만 `--raw`를 사용한다.

## Normalized Evidence 전달

`dev-design-reference`에는 다음을 전달한다.

```text
Design Source: FIGMA
Design Status: DRAFT | REFERENCE | APPROVED
Reference: <selected Figma URL>
Observed:
- exact Figma evidence
Inferred:
- provider evidence에서 합리적으로 추정한 내용
Unknown:
- Figma에 정의되지 않은 상태/behavior
```

## Design Conflict

Figma와 기존 project component/token이 다르면:

```text
Figma Evidence:
Current Project Pattern:
Task-local Decision:
Global Change Required: true|false
Improvement Deferred:
```

현재 Task에 필요하지 않은 global token/component migration은 수행하지 않는다.

## Provider 정책

현재 provider는 Figma 공식 REST API다. Figma 공식 MCP 지원 여부와 무관하게 Hermes에서 임의의 MCP contract를 가정하지 않는다.

Provider 구현이 바뀌어도 상위 `dev-design-reference`의 Normalized Design Evidence 계약은 유지한다.

세부 endpoint/source는 `references/figma-provider.md`를 따른다.
