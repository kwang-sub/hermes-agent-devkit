# Kanban 작업 알림 설정

Hermes 공식 Kanban terminal-event notification을 이용해 작업 완료/차단 등의 상태를 Gateway 플랫폼으로 전달한다.

DevKit은 플랫폼별 코드를 workflow에 하드코딩하지 않고 다음 공통 설정을 사용한다.

```dotenv
HERMES_KANBAN_NOTIFY_ENABLED=false
HERMES_KANBAN_NOTIFY_PLATFORM=discord
HERMES_KANBAN_NOTIFY_TARGET=
HERMES_KANBAN_NOTIFY_DELIVERY_MODE=notify
HERMES_KANBAN_NOTIFY_CHAT_TYPE=channel
HERMES_KANBAN_NOTIFY_PROFILE=default
```

`HERMES_KANBAN_NOTIFY_PROFILE`은 실제 알림 adapter를 소유한 Gateway Profile이다. 단일 Gateway로 동작하는 DevKit 기본 구조에서는 `default`를 사용한다. Orchestrator가 구독을 등록하더라도 subscription 소유자는 이 값으로 고정된다.

기본값은 비활성화이며, 알림 등록 실패는 Coder/Reviewer 작업을 차단하지 않는다.

## Discord 사용

Discord를 사용할 때 로컬 `.env`에 다음 값을 추가한다.

```dotenv
HERMES_KANBAN_NOTIFY_ENABLED=true
HERMES_KANBAN_NOTIFY_PLATFORM=discord
HERMES_KANBAN_NOTIFY_TARGET=<Discord Channel ID>
HERMES_KANBAN_NOTIFY_DELIVERY_MODE=notify
HERMES_KANBAN_NOTIFY_CHAT_TYPE=channel
HERMES_KANBAN_NOTIFY_PROFILE=default
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
  --notifier-profile <profile>
  [--chat-type <type>]
```

## Kanban 세션 고정

DevKit의 dispatcher worker는 `Task ID + Profile`을 세션 고정 키로 사용한다. 같은 카드라도 Coder와 Reviewer는 서로 다른 세션을 사용한다.

```text
Task t_3a1bde20
├─ coder    → session C-001
└─ reviewer → session R-001
```

동일 프로필의 재실행에서 실행 조건이 유지되면 기존 Hermes session을 `--resume`으로 재사용한다. 차단 후 입력 추가, 리뷰 수정 요청 후 재작업처럼 같은 작업 문맥을 이어가는 실행은 기존 조사·판단 컨텍스트를 유지한다.

다음 실행 계약을 fingerprint로 비교한다.

- workspace
- branch
- Base SHA
- model / provider override
- reasoning effort
- pinned skills / worker toolsets
- goal mode
- 해당 profile의 `config.yaml`

위 계약이 달라지면 같은 카드·프로필이라도 `NEW` 세션으로 시작한다. 특히 profile 기본 모델이나 reasoning 설정이 변경된 뒤 과거 session의 모델 설정이 복원되는 것을 방지하기 위해 profile 설정도 비교 대상에 포함한다.

세션 고정 정보는 Hermes 공식 Kanban DB schema를 수정하지 않고 보드별 `devkit-session-affinity.db`에 별도로 저장한다. 세션 조회나 sidecar DB 접근에 실패하면 dispatch를 차단하지 않고 안전하게 `NEW` 세션으로 폴백한다.

## Discord 알림 포맷

DevKit은 Discord로 전달되는 주요 Kanban terminal event를 업무용 한국어 포맷으로 변환한다. 다른 Gateway 플랫폼에는 Hermes 기본 포맷을 유지한다.

`프로필`은 해당 terminal run을 실제 수행한 Hermes profile, `세션`은 실제 Hermes session ID, `세션 방식`은 `NEW` 또는 `RESUME`을 표시한다. 기존 기록이거나 세션 정보를 확인할 수 없는 경우 `-`로 표시할 수 있다.

차단 예시:

```text
⛔ 작업 차단

프로젝트  oc-wowsoft-server-setup
작업      Windows OC APP_SFTP 설치 자동화 구현
Task      t_3a1bde20
담당      coder
프로필    coder
모델      GPT-5.6 Terra
세션      20260907_163138_b1481e
세션 방식 RESUME
상태      BLOCKED

사유
Windows 검증 환경이 없어 수동 확인이 필요합니다.
```

완료 예시:

```text
✅ 작업 완료

프로젝트  oc-wowsoft-server-setup
작업      Windows OC APP_SFTP 설치 자동화 구현
Task      t_3a1bde20
담당      coder
프로필    coder
모델      GPT-5.6 Terra
세션      20260907_163138_b1481e
세션 방식 RESUME
상태      DONE
```

`review_requested`와 `changes_requested`는 이벤트 provenance를 사용해 상태 전환 후 카드의 현재 담당자가 아니라 해당 terminal event를 실제 수행한 implementer/reviewer profile과 세션을 표시한다.

동일한 형식으로 `gave_up`, `crashed`, `timed_out`, `review_requested`, `changes_requested`, `block_loop_detected`를 구분해 표시한다. 사유/오류/리뷰 내용은 외부 전달용 안전 필터를 거친 뒤 길이를 제한한다.

## 플랫폼 변경

Discord에서 다른 Hermes Gateway 플랫폼으로 변경할 때 workflow/skill 코드를 수정하지 않는다.

예:

```dotenv
HERMES_KANBAN_NOTIFY_PLATFORM=slack
HERMES_KANBAN_NOTIFY_TARGET=<Slack Channel ID>
HERMES_KANBAN_NOTIFY_PROFILE=<Slack adapter를 소유한 Gateway Profile>
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

구독 성공 시 실제 소유 profile도 `NOTIFY_PROFILE=<profile>`로 출력한다.

알림 실패 또는 세션 정보 조회 실패를 이유로 Task를 `BLOCKED` 처리하거나 별도 notification Task를 만들지 않는다.
