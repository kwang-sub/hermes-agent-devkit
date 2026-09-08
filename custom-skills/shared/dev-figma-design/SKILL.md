---
name: dev-figma-design
description: 승인된 Figma frame/component URL에서 공식 REST API로 bounded design context와 preview를 read-only 추출해 Frontend 구현 evidence로 전달한다.
version: 0.1.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, frontend, figma, design, rest, read-only]
    related_skills: [dev-frontend-feature, dev-ui-ux, dev-frontend-guidelines, dev-nextjs-feature]
    requires_tools: [terminal]
---

# dev-figma-design

Figma의 구현 대상 frame/component를 **read-only**로 읽어 Design Evidence를 만드는 Skill이다. Frontend source를 직접 구현하지 않으며 Figma canvas도 수정하지 않는다.

## 인증

컨테이너 환경에서 다음 중 하나를 사용한다.

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
→ planning/reference only
→ 구현 source of truth 아님

APPROVED
→ FIGMA_DRIVEN 구현 source of truth
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

## Evidence

최소 다음을 해석한다.

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

raw API 전체 응답은 기본 출력하지 않으며 debugging 근거가 필요할 때만 `--raw`를 사용한다.

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

현재 provider는 Figma 공식 REST API다. Figma 공식 MCP는 지원 catalog client 제약이 있으므로 Hermes에서 직접 가정하지 않는다. provider 교체가 필요해도 `dev-figma-design`의 Design Evidence 계약은 유지한다.

세부 endpoint/source는 `references/figma-provider.md`를 따른다.
