# dev-workspace-dispatch v0.9.3

dev-breakdown의 READY 계획을 사용자 승인 이후에 Git workspace와 Kanban Task로 Dispatch하는 orchestrator Skill입니다.

신규 Dispatch의 표준 Skill이며, legacy linked-worktree 전용 `dev-worktree-dispatch`를 대체합니다.

## 핵심 변경

- 기본 동작으로 git worktree add를 실행하지 않습니다.
- 사용자가 workspace와 branch 전략을 선택합니다.
- Kanban Body에 Workspace Contract, Base SHA, Branch mode를 보존합니다.
- Kanban Task는 알림 Gate가 끝나기 전 worker가 가져가지 못하도록 `blocked` 상태로 생성합니다.
- 명시적 `BOARD`로 Task read-back을 확인한 뒤에만 알림 구독을 수행합니다.
- 알림 구독 후 `notify-list --json`에서 기대 subscription row를 다시 확인합니다.
- 알림 활성 환경에서 등록/구독/검증이 실패하면 Task를 unblock하지 않습니다.
- 알림이 명시적으로 비활성화된 경우에만 구독 없이 ready 전환을 허용합니다.
- 알림 플랫폼은 환경변수로 선택하므로 Discord에서 Slack/Telegram 등 Hermes 지원 플랫폼으로 교체할 때 dispatch 로직을 수정하지 않습니다.

## Workspace Helper

```bash
python3 "${HERMES_SKILL_DIR}/scripts/prepare_dispatch.py" \
  --task-key "CALC-001" \
  --workspace "/workspace/dashboard" \
  --branch-mode create \
  --branch "feature/CALC-001"
```

현재 branch를 그대로 사용할 때는 `--branch-mode current`를 사용합니다. Dirty workspace는 사용자가 승인한 경우에만 `--confirmed-dirty`를 추가합니다.

## Kanban 알림 Gate

기본값은 비활성화입니다. Discord를 사용할 때 로컬 `.env`에는 다음처럼 설정합니다.

```dotenv
HERMES_KANBAN_NOTIFY_ENABLED=true
HERMES_KANBAN_NOTIFY_PLATFORM=discord
HERMES_KANBAN_NOTIFY_TARGET=<Discord Channel ID>
HERMES_KANBAN_NOTIFY_DELIVERY_MODE=notify
HERMES_KANBAN_NOTIFY_CHAT_TYPE=channel
HERMES_KANBAN_NOTIFY_PROFILE=default
DISCORD_BOT_TOKEN=<Discord Bot Token>
```

표준 순서는 다음과 같습니다.

```text
kanban_create(board=BOARD, initial_status=blocked)
→ kanban_show(board=BOARD, task_id=TASK)
→ subscribe_notification.py --board BOARD --task-id TASK
→ subscription read-back 검증
→ kanban_unblock(board=BOARD, task_id=TASK)
```

알림 helper는 반드시 `--board`와 `--task-id`를 함께 받습니다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/subscribe_notification.py" \
  --board "<KANBAN_BOARD>" \
  --task-id "<KANBAN_TASK_ID>"
```

성공 시 다음 핵심 상태를 출력합니다.

```text
TASK_READBACK_VERIFIED=true
NOTIFY_STATUS=subscribed
NOTIFY_VERIFIED=true
```

알림이 꺼져 있으면 `NOTIFY_STATUS=disabled`이고 정상 종료합니다. 알림이 켜져 있는데 Task read-back, 구독, 구독 read-back 중 하나라도 실패하면 `NOTIFY_STATUS=failed`와 non-zero exit code를 반환하므로 Task는 `blocked` 상태로 유지해야 합니다.

## 검증

Repository root에서 다음을 실행합니다.

```bash
python3 -m compileall -q custom-skills shared/scripts
python3 custom-skills/orchestrator/dev-workspace-dispatch/tests/test_prepare_dispatch.py
python3 custom-skills/orchestrator/dev-workspace-dispatch/tests/test_subscribe_notification.py
python3 custom-skills/orchestrator/dev-project-bootstrap/tests/test_metadata_preservation.py
python3 custom-skills/orchestrator/dev-project-resolve/tests/test_project_resolve.py
```
