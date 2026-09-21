# dev-workspace-dispatch v0.10.0

dev-breakdown의 READY 계획을 사용자 승인 이후에 Git workspace와 Kanban Task로 Dispatch하는 orchestrator Skill입니다.

신규 Dispatch의 표준 Skill이며, legacy linked-worktree 전용 `dev-worktree-dispatch`를 대체합니다.

## 핵심 변경

- 기본 동작으로 git worktree add를 실행하지 않습니다.
- 사용자가 workspace와 branch 전략을 선택합니다.
- Kanban Body에 Workspace Contract, Base SHA, Branch mode를 보존합니다.
- Task는 native notification subscription 시도와 worker 실행의 순서를 보장하기 위해 잠시 `blocked`로 생성합니다.
- 명시적 `BOARD`에서 `kanban_show` read-back을 확인한 뒤 Hermes native `notify-subscribe`를 한 번 시도합니다.
- notification 결과는 `subscribed | disabled | warning`이며 **warning도 worker dispatch를 차단하지 않습니다.**
- 별도 custom registration event, delivery ACK Gate, Discord formatter/session-context source patch를 사용하지 않습니다.
- 알림 플랫폼은 환경변수로 선택합니다.

## Workspace Helper

```bash
python3 "${HERMES_SKILL_DIR}/scripts/prepare_dispatch.py" \
  --task-key "CALC-001" \
  --workspace "/workspace/dashboard" \
  --branch-mode create \
  --branch "feature/CALC-001"
```

현재 branch를 그대로 사용할 때는 `--branch-mode current`를 사용합니다. Dirty workspace는 사용자가 승인한 경우에만 `--confirmed-dirty`를 추가합니다.

## Kanban native 알림 연결

기본값은 비활성화입니다.

```dotenv
HERMES_KANBAN_NOTIFY_ENABLED=true
HERMES_KANBAN_NOTIFY_PLATFORM=discord
HERMES_KANBAN_NOTIFY_TARGET=<Discord Channel ID>
HERMES_KANBAN_NOTIFY_DELIVERY_MODE=notify
HERMES_KANBAN_NOTIFY_CHAT_TYPE=channel
DISCORD_BOT_TOKEN=<Discord Bot Token>
```

notifier profile은 DevKit 내부 계약상 `default` multiplex Gateway로 고정합니다.

```text
kanban_create(board=BOARD, initial_status=blocked)
→ kanban_show(board=BOARD, task_id=TASK)
→ subscribe_notification.py --board BOARD --task-id TASK
→ NOTIFY_STATUS=subscribed | disabled | warning
→ kanban_unblock(board=BOARD, task_id=TASK)
```

`blocked`는 notification delivery 성공을 기다리는 Gate가 아니라 subscription 시도가 worker보다 먼저 일어나게 하는 짧은 race barrier입니다.

성공한 native subscription은 다음을 출력합니다.

```text
NOTIFY_STATUS=subscribed
NOTIFY_VERIFIED=true
NOTIFY_PROFILE=default
```

알림이 꺼져 있으면 `disabled`, 설정/Gateway/read-back 문제가 있으면 `warning`입니다. 두 경우 모두 개발 Task는 계속 진행합니다. 이후 terminal notification delivery/retry/cursor 관리는 Hermes Gateway native notifier가 담당합니다.

## 검증

```bash
python3 -m compileall -q custom-skills shared/scripts
python3 custom-skills/orchestrator/dev-workspace-dispatch/tests/test_prepare_dispatch.py
python3 custom-skills/orchestrator/dev-workspace-dispatch/tests/test_subscribe_notification.py
python3 custom-skills/orchestrator/dev-project-bootstrap/tests/test_metadata_preservation.py
python3 custom-skills/orchestrator/dev-project-resolve/tests/test_project_resolve.py
```
