# dev-code-review v0.1.1

Reviewer가 Coder의 미커밋 동일 Workspace 구현을 독립 검토하는 Skill입니다.

설치:

```text
/opt/custom-skills/reviewer/dev-code-review
```

Branch는 Kanban Body의 `Expected Branch`를 검증합니다. 현재 branch 사용 또는 새 branch 생성 모두 dev-workspace-dispatch의 Workspace Contract를 따릅니다.

Reviewer는 Source를 직접 고치지 않고 `CHANGES_REQUESTED` 또는 `APPROVED`로 처리합니다.
