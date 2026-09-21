# dev-workspace-dispatch v0.11.0

dev-breakdown의 READY 계획을 사용자 승인 이후 Git/Non-Git workspace와 Kanban Task로 Dispatch하는 orchestrator Skill입니다.

## 핵심 계약

- `prepare_dispatch.py`로 승인된 workspace/branch 계약을 준비합니다.
- Task는 `initial_status=blocked`로 생성해 `kanban_show` read-back 검증 전 worker claim을 막습니다.
- read-back이 승인 계약과 일치하면 `kanban_unblock`으로 ready 전환합니다.
- 알림은 dispatch 경로의 Gate가 아닙니다.
- 같은 `hermes-dev` 컨테이너의 s6-supervised `devkit-notifier`가 Hermes `task_events`를 비동기로 읽고 업무용 포맷으로 전송합니다.
- Hermes notifier source patch, custom registration event, delivery ACK Gate, explicit `notify-subscribe` helper를 사용하지 않습니다.

## Workspace Helper

```bash
python3 "${HERMES_SKILL_DIR}/scripts/prepare_dispatch.py" \
  --task-key "CALC-001" \
  --workspace "/workspace/dashboard" \
  --branch-mode create \
  --branch "feature/CALC-001"
```

현재 branch를 그대로 사용할 때는 `--branch-mode current`를 사용합니다. Dirty workspace는 사용자가 승인한 경우에만 `--confirmed-dirty`를 추가합니다.

## Kanban Dispatch

```text
kanban_create(board=BOARD, initial_status=blocked)
→ kanban_show(board=BOARD, task_id=TASK)
→ contract read-back
→ kanban_unblock(board=BOARD, task_id=TASK)
→ worker dispatch
```

Notification Bridge는 위 흐름과 독립적으로 `created`, `review_requested`, `changes_requested`, `completed`, `blocked`, `gave_up`, `crashed`, `timed_out`, `block_loop_detected` event를 관찰합니다.

## 검증

```bash
python3 -m compileall -q custom-skills shared/scripts
python3 custom-skills/orchestrator/dev-workspace-dispatch/tests/test_prepare_dispatch.py
python3 scripts/devkit_kanban_notifier.py --self-test
python3 custom-skills/orchestrator/dev-project-bootstrap/tests/test_metadata_preservation.py
python3 custom-skills/orchestrator/dev-project-resolve/tests/test_project_resolve.py
```
