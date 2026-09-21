# Kanban 작업 알림 설정

Hermes 공식 Kanban terminal-event notification을 이용해 작업 완료/차단/리뷰 등의 상태를 Gateway 플랫폼으로 전달한다.

DevKit은 Hermes notifier source를 수정하지 않고 다음 공통 설정만 사용한다.

```dotenv
HERMES_KANBAN_NOTIFY_ENABLED=false
HERMES_KANBAN_NOTIFY_PLATFORM=discord
HERMES_KANBAN_NOTIFY_TARGET=
HERMES_KANBAN_NOTIFY_DELIVERY_MODE=notify
HERMES_KANBAN_NOTIFY_CHAT_TYPE=channel
```

notifier profile은 DevKit 내부의 `default` multiplex Gateway로 고정한다. `orchestrator`는 Workflow 역할이며 별도 notification Gateway 소유자가 아니다.

## 동작 방식

Direct/Standard canonical dispatch는 Task를 잠시 `blocked`로 생성하고 read-back을 확인한 뒤 native subscription을 시도한다.

```text
kanban_create(initial_status=blocked)
→ kanban_show
→ Hermes native notify-subscribe
→ native notify-list read-back (best-effort)
→ kanban_unblock
→ worker dispatch
```

`blocked`는 notification delivery ACK를 기다리는 Gate가 아니다. 빠른 worker가 subscription 생성보다 먼저 terminal event를 만드는 race를 줄이기 위한 짧은 순서 보장 장치다.

별도 custom registration event를 만들지 않으며, 등록 성공 기준은 `kanban_create + kanban_show` read-back이다.

## Hermes native notifier

terminal event의 메시지 포맷, adapter delivery, retry, cursor/dedup은 Hermes Gateway native notifier가 담당한다. DevKit은 다음을 더 이상 patch하지 않는다.

```text
Discord 업무용 한국어 formatter
custom registration event
registration delivery ACK Gate
notification용 session/profile/NEW·RESUME 표시
```

실제 알림 문구는 Hermes upstream 버전에 따라 달라질 수 있다. DevKit은 `completed`, `blocked`, `review_requested`, `changes_requested`, `crashed`, `timed_out` 등 native terminal notification을 그대로 사용한다.

## Kanban 세션 고정

Worker Session Affinity는 알림과 독립적으로 유지한다.

```text
Task t_3a1bde20
├─ coder    → session C-001
└─ reviewer → session R-001
```

동일 Task/Profile의 재실행에서 workspace, branch, Base SHA, model/provider, reasoning, skills/toolsets, profile config fingerprint가 같으면 기존 worker session을 `--resume`한다. 계약이 달라지면 `NEW` 세션으로 시작한다.

NEW/RESUME 정보는 더 이상 Discord notifier source에 주입하지 않는다. 실행 추적이 필요하면 Kanban run/event metadata, worker log, profile session 기록을 사용한다.

## Discord 사용

```dotenv
HERMES_KANBAN_NOTIFY_ENABLED=true
HERMES_KANBAN_NOTIFY_PLATFORM=discord
HERMES_KANBAN_NOTIFY_TARGET=<Discord Channel ID>
HERMES_KANBAN_NOTIFY_DELIVERY_MODE=notify
HERMES_KANBAN_NOTIFY_CHAT_TYPE=channel
DISCORD_BOT_TOKEN=<Discord Bot Token>
```

`DISCORD_BOT_TOKEN`은 저장소에 커밋하거나 Kanban body/comment에 기록하지 않는다. 설정 변경 후에는 `.\update-devkit.ps1`로 컨테이너를 재생성한다.

## 실패 정책

helper 출력은 다음 셋이다.

```text
NOTIFY_STATUS=subscribed
NOTIFY_STATUS=disabled
NOTIFY_STATUS=warning
```

- `subscribed`: native subscription 생성과 read-back 확인 성공.
- `disabled`: 알림 비활성화.
- `warning`: 설정 누락, Gateway/CLI 오류, subscription read-back 실패 등 observability 저하.

세 상태 모두 개발 Task lifecycle은 계속 진행한다. 알림 실패를 이유로 Task를 `BLOCKED` 처리하거나 별도 notification Task를 만들지 않는다.
