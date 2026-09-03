# Kanban 작업 알림 설정

Hermes 공식 Kanban terminal-event notification을 이용해 작업 완료/차단 등의 상태를 Gateway 플랫폼으로 전달한다.

DevKit은 플랫폼별 코드를 workflow에 하드코딩하지 않고 다음 공통 설정을 사용한다.

```dotenv
HERMES_KANBAN_NOTIFY_ENABLED=false
HERMES_KANBAN_NOTIFY_PLATFORM=discord
HERMES_KANBAN_NOTIFY_TARGET=
HERMES_KANBAN_NOTIFY_DELIVERY_MODE=notify
HERMES_KANBAN_NOTIFY_CHAT_TYPE=channel
```

기본값은 비활성화이며, 알림 등록 실패는 Coder/Reviewer 작업을 차단하지 않는다.

## Discord 사용

Discord를 사용할 때 로컬 `.env`에 다음 값을 추가한다.

```dotenv
HERMES_KANBAN_NOTIFY_ENABLED=true
HERMES_KANBAN_NOTIFY_PLATFORM=discord
HERMES_KANBAN_NOTIFY_TARGET=<Discord Channel ID>
HERMES_KANBAN_NOTIFY_DELIVERY_MODE=notify
HERMES_KANBAN_NOTIFY_CHAT_TYPE=channel
DISCORD_BOT_TOKEN=<Discord Bot Token>
```

`DISCORD_BOT_TOKEN`은 저장소에 커밋하거나 Kanban body/comment에 기록하지 않는다.

설정 변경 후 Compose environment가 갱신되도록 컨테이너를 재생성한다.

```powershell
docker compose up -d --force-recreate
```

또는 DevKit 업데이트를 함께 적용하는 경우:

```powershell
.\update-devkit.ps1
```

## 동작 방식

Standard Flow:

```text
dev-workspace-dispatch
→ kanban_create
→ kanban_show / pinned skill 검증
→ notification subscription
→ Coder / Reviewer
```

Fast Flow:

```text
dev-fast-flow
→ create_fast_task.py
→ 생성된 Task ID 확보
→ notification subscription
→ Interactive Coder 종료
```

두 Flow 모두 공통 helper를 사용한다.

```bash
python3 /opt/data/shared/scripts/kanban_notify_subscribe.py --task-id "<TASK_ID>"
```

내부적으로 Hermes 공식 CLI를 호출한다.

```text
hermes kanban notify-subscribe <TASK_ID>
  --platform <platform>
  --chat-id <target>
  --delivery-mode <mode>
  [--chat-type <type>]
```

## 플랫폼 변경

Discord에서 다른 Hermes Gateway 플랫폼으로 변경할 때 workflow/skill 코드를 수정하지 않는다.

예:

```dotenv
HERMES_KANBAN_NOTIFY_PLATFORM=slack
HERMES_KANBAN_NOTIFY_TARGET=<Slack Channel ID>
```

플랫폼 인증 환경변수만 해당 플랫폼 규격에 맞게 구성한다. 사용하지 않는 플랫폼의 token은 로컬 `.env`에서 제거하거나 비활성화한다.

## 실패 정책

helper 출력:

```text
NOTIFY_STATUS=subscribed
NOTIFY_STATUS=disabled
NOTIFY_STATUS=warning
```

- `subscribed`: 정상 구독.
- `disabled`: 알림 비활성화. 정상 상태.
- `warning`: 설정 누락, Gateway/CLI 오류, 20초 timeout 등. 개발 Task는 계속 진행.

알림 실패를 이유로 Task를 `BLOCKED` 처리하거나 별도 notification Task를 만들지 않는다.
