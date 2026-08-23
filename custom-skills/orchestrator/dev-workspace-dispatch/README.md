# dev-workspace-dispatch v0.2.0

dev-breakdown의 READY 계획을 사용자 승인 이후에 Git workspace와 Kanban Task로 Dispatch하는 orchestrator Skill입니다.

신규 Dispatch의 표준 Skill이며, legacy linked-worktree 전용 `dev-worktree-dispatch`를 대체합니다.

## 핵심 변경

- 기본 동작으로 git worktree add를 실행하지 않습니다.
- 사용자가 workspace와 branch 전략을 선택합니다.
- Kanban Body에 Workspace Contract, Base SHA, Branch mode를 보존합니다.

## Helper

```bash
python3 "${HERMES_SKILL_DIR}/scripts/prepare_dispatch.py" \
  --task-key "CALC-001" \
  --workspace "/workspace/dashboard" \
  --branch-mode create \
  --branch "feature/CALC-001"
```

현재 branch를 그대로 사용할 때는 `--branch-mode current`를 사용합니다. Dirty workspace는 사용자가 승인한 경우에만 `--confirmed-dirty`를 추가합니다.

## 검증

Repository root에서 다음을 실행합니다.

```bash
python3 -m compileall -q custom-skills
python3 custom-skills/orchestrator/dev-workspace-dispatch/tests/test_prepare_dispatch.py
python3 custom-skills/orchestrator/dev-project-bootstrap/tests/test_metadata_preservation.py
python3 custom-skills/orchestrator/dev-project-resolve/tests/test_project_resolve.py
```
