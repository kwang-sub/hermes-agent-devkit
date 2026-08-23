# dev-implement-plan v0.2.0

Coder가 사용자 승인된 Implementation Plan을 승인된 Git workspace에서 구현하고 Reviewer에게 넘기는 Skill입니다.

## 변경점

- Branch 계약을 Kanban Workspace Contract의 Expected Branch 기준으로 검증
- 기존 구현/검증/Review Handoff 로직 유지
- 문서 한글화

## 설치

```text
/opt/custom-skills/coder/dev-implement-plan
```

또는 기존 Profile Skill 영역:

```text
/opt/data/profiles/coder/skills/dev-implement-plan
```

## Workspace 검증

```bash
python3 "${HERMES_SKILL_DIR}/scripts/verify_workspace.py" \
  --task-key CALC-001 \
  --expected-branch "<Kanban Workspace Contract의 Expected Branch>"
```

이 Skill은 commit/push를 수행하지 않습니다.
