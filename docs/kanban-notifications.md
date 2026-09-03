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

```dotenv
HERMES_KANBAN_NOTIFY_ENABLED=true
HERMES_KANBAN_NOTIFY_PLATFORM=discord
HERMES_KANBAN_NOTIFY_TARGET=<Discord Channel ID>
HERMES_KANBAN_NOTIFY_DELIVERY_MODE=notify
HERMES_KANBAN_NOTIFY_CHAT_TYPE=channel
DISCORD_BOT_TOKEN=<Discord Bot Token>
```

## NAVER WORKS 사용

DevKit은 Hermes third-party platform plugin으로 `naverworks` outbound adapter를 제공한다.

인증 흐름:

```text
Service Account + Private Key
→ RS256 JWT
→ OAuth2 Access Token
→ Bot Channel Message API
```

`.env` 예시:

```dotenv
HERMES_KANBAN_NOTIFY_ENABLED=true
HERMES_KANBAN_NOTIFY_PLATFORM=naverworks
HERMES_KANBAN_NOTIFY_TARGET=<NAVER WORKS Channel ID>
HERMES_KANBAN_NOTIFY_DELIVERY_MODE=notify
HERMES_KANBAN_NOTIFY_CHAT_TYPE=channel

NAVER_WORKS_CLIENT_ID=<Client ID>
NAVER_WORKS_CLIENT_SECRET=<Client Secret>
NAVER_WORKS_SERVICE_ACCOUNT=<Service Account>
NAVER_WORKS_BOT_ID=<Bot ID>
NAVER_WORKS_SCOPE=bot.message
NAVER_WORKS_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"
```

`NAVER_WORKS_PRIVATE_KEY`는 로컬 `.env`에만 저장한다. PEM 줄바꿈은 `\n`으로 기록하면 adapter가 실제 줄바꿈으로 복원한다. Token/Private Key는 Kanban body/comment/log에 기록하지 않는다.

`HERMES_KANBAN_NOTIFY_TARGET`은 Bot이 참여한 NAVER WORKS 메시지방의 `channelId`다. Compose는 이 값을 `NAVER_WORKS_HOME_CHANNEL`에도 전달하므로 별도 channel 환경변수를 중복 입력하지 않는다.

플러그인은 이미지 빌드 시 `/opt/hermes/plugins/platforms/naverworks`에 포함된다. 설정 변경 또는 DevKit 업데이트 후 이미지를 다시 빌드/재생성한다.

```powershell
.\update-devkit.ps1
```

또는 수동으로:

```powershell
docker compose up -d --build --force-recreate
```

환경 설정 확인 시 Private Key나 Client Secret 자체는 출력하지 않는다.

```powershell
docker exec --user hermes hermes-dev sh -lc 'echo PLATFORM=$HERMES_KANBAN_NOTIFY_PLATFORM; echo TARGET=$HERMES_KANBAN_NOTIFY_TARGET; [ -n "$NAVER_WORKS_PRIVATE_KEY" ] && echo PRIVATE_KEY=SET || echo PRIVATE_KEY=MISSING'
```

기존 Task로 수동 subscription을 확인할 수 있다.

```powershell
docker exec --user hermes hermes-dev python3 /opt/data/shared/scripts/kanban_notify_subscribe.py --task-id <TASK_ID>
```

정상 결과:

```text
NOTIFY_STATUS=subscribed
NOTIFY_PLATFORM=naverworks
NOTIFY_TARGET=<channelId>
NOTIFY_DELIVERY_MODE=notify
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

workflow/skill 코드는 수정하지 않고 `.env`의 platform/credential만 바꾼다.

```dotenv
HERMES_KANBAN_NOTIFY_PLATFORM=naverworks
HERMES_KANBAN_NOTIFY_TARGET=<NAVER WORKS Channel ID>
```

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
