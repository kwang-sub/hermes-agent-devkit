# dev-workspace-dispatch v0.6.0

dev-breakdown의 READY 계획을 사용자 승인 이후에 Git workspace와 Kanban Task로 Dispatch하는 orchestrator Skill입니다.

신규 Dispatch의 표준 Skill이며, legacy linked-worktree 전용 `dev-worktree-dispatch`를 대체합니다.

## 핵심 변경

- 기본 동작으로 git worktree add를 실행하지 않습니다.
- 사용자가 workspace와 branch 전략을 선택합니다.
- Kanban Body에 Workspace Contract, Base SHA, Branch mode를 보존합니다.
- 선택적으로 Kanban terminal event 알림을 Task 생성 직후 구독합니다.
- 알림 플랫폼은 환경변수로 선택하므로 Discord에서 Slack/Telegram 등 Hermes 지원 플랫폼으로 교체할 때 dispatch 로직을 수정하지 않습니다.
- 알림 등록 실패는 개발 Task를 차단하지 않고 warning만 남깁니다.

## Workspace Helper

```bash
python3 "${HERMES_SKILL_DIR}/scripts/prepare_dispatch.py" \
  --task-key "CALC-001" \
  --workspace "/workspace/dashboard" \
  --branch-mode create \
  --branch "feature/CALC-001"
```

현재 branch를 그대로 사용할 때는 `--branch-mode current`를 사용합니다. Dirty workspace는 사용자가 승인한 경우에만 `--confirmed-dirty`를 추가합니다.

## Kanban 알림

기본값은 비활성화입니다. Discord를 사용할 때 로컬 `.env`에는 다음처럼 설정합니다.

```dotenv
HERMES_KANBAN_NOTIFY_ENABLED=true
HERMES_KANBAN_NOTIFY_PLATFORM=discord
HERMES_KANBAN_NOTIFY_TARGET=<Discord Channel ID>
HERMES_KANBAN_NOTIFY_DELIVERY_MODE=notify
HERMES_KANBAN_NOTIFY_CHAT_TYPE=channel
DISCORD_BOT_TOKEN=<Discord Bot Token>
```

Task 생성 직후 다음 helper를 실행합니다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/subscribe_notification.py" --task-id "<KANBAN_TASK_ID>"
```

`NOTIFY_STATUS=subscribed`이면 구독 성공입니다. `disabled` 또는 `warning`도 helper exit code는 0이며 Kanban 작업은 계속 진행합니다.

## 검증

Repository root에서 다음을 실행합니다.

```bash
python3 -m compileall -q custom-skills
python3 custom-skills/orchestrator/dev-workspace-dispatch/tests/test_prepare_dispatch.py
python3 custom-skills/orchestrator/dev-workspace-dispatch/tests/test_subscribe_notification.py
python3 custom-skills/orchestrator/dev-project-bootstrap/tests/test_metadata_preservation.py
python3 custom-skills/orchestrator/dev-project-resolve/tests/test_project_resolve.py
```
