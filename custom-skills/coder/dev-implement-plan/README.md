# dev-implement-plan v0.21.0

Coder가 사용자 승인된 Implementation Plan을 승인된 Git workspace에서 구현하고 Reviewer에게 넘기는 Skill입니다.

## 핵심 계약

- Branch/Base SHA/Workspace는 `verify_workspace.py`로 검증합니다.
- Kanban Worker ownership은 Workspace 검증과 분리합니다.
  - `openai-codex`: Hermes MCP `kanban_worker_context` 도구로 검증
  - 그 외 Hermes Worker: `verify_worker_context.py`로 검증
- Codex native shell에는 `HERMES_KANBAN_TASK` 같은 ownership env를 다시 노출하지 않습니다.
- 기존 구현/검증/Review Handoff 로직은 유지합니다.

## 설치

```text
/opt/custom-skills/coder/dev-implement-plan
```

## Worker Context 검증

Codex Worker는 Hermes MCP의 `kanban_worker_context`를 사용합니다. 일반 Hermes Worker는 다음 helper를 사용합니다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/verify_worker_context.py" \
  --expected-workspace "<Kanban Workspace Contract의 Workspace>" \
  --expected-profile coder
```

## Workspace 검증

```bash
python3 "${HERMES_SKILL_DIR}/scripts/verify_workspace.py" \
  --task-key CALC-001 \
  --workspace "<Kanban Workspace Contract의 Workspace>" \
  --expected-workspace "<Kanban Workspace Contract의 Workspace>" \
  --expected-branch "<Kanban Workspace Contract의 Expected Branch>" \
  --base-sha "<Kanban Workspace Contract의 Base SHA>"
```

이 Skill은 commit/push를 수행하지 않습니다.
