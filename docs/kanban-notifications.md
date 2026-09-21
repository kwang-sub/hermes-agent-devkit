# Kanban 작업 알림 설정

DevKit은 Hermes Kanban DB에 이미 기록되는 `task_events`를 읽어 개발 업무용 알림을 만든다. Hermes의 notifier Python source는 수정하지 않는다.

## 구조

```text
hermes-dev container
├─ gateway-default
├─ devkit-notifier        ← /run/service dynamic s6-svscan longrun
├─ coder/reviewer workers
└─ /opt/data
   ├─ kanban.db / kanban/boards/*/kanban.db
   └─ devkit-notifier/state.db
```

`devkit-notifier`는 read-only로 Hermes의 task/event/run 정보를 조회하고, 자체 cursor만 `/opt/data/devkit-notifier/state.db`에 저장한다. 메시지는 Hermes 공식 scripting surface인 `hermes send`로 전송한다.

## 설정

```dotenv
HERMES_KANBAN_NOTIFY_ENABLED=true
HERMES_KANBAN_NOTIFY_PLATFORM=discord
HERMES_KANBAN_NOTIFY_TARGET=<Discord Channel ID>
DISCORD_BOT_TOKEN=<Discord Bot Token>
```

기본값은 비활성화다. 설정 변경 후:

```powershell
.\update-devkit.ps1
```

DevKit boot/profile-init policy는 Hermes native `kanban.notify_in_gateway`와 `kanban.auto_subscribe_on_create`를 항상 `false`로 유지한다. `HERMES_KANBAN_NOTIFY_ENABLED`는 오직 `devkit-notifier`의 실제 전송 여부만 제어하므로 Native/Bridge 중복 알림이 생기지 않는다.

## 이벤트

| Hermes event | DevKit 알림 |
|---|---|
| `created` | 🆕 작업 등록 |
| `review_requested` | 🔎 리뷰 요청 |
| `changes_requested` | 🛠️ 수정 요청 |
| `completed` | ✅ 작업 완료 |
| `blocked` | ⛔ 작업 차단 |
| `gave_up` | ❌ 작업 실패 |
| `crashed` | 💥 작업 비정상 종료 |
| `timed_out` | ⏱️ 작업 시간 초과 |
| `block_loop_detected` | ⚠️ 반복 차단 감지 |

Standard/Direct Flow가 Task를 `initial_status=blocked`로 만드는 내부 barrier는 실제 장애가 아니므로 payload의 `reason=initial_status`인 `blocked` event는 알림에서 제외한다.

## 포맷

예:

```text
🆕 작업 등록

프로젝트  hdc-218
작업      docs/test.txt 생성 및 성공 문구 기록
Task      t_8fc8b512
담당      coder
프로필    orchestrator
모델      openai-codex / gpt-5.6-terra
상태      REGISTERED

등록
Coder 작업 대기열에 등록되었습니다.
```

리뷰/완료/차단도 같은 필드 구조를 사용하고 event payload의 summary/reason/result를 최대 길이로 제한해 붙인다.

Worker Session Affinity는 알림과 독립적으로 유지한다. 동일 Task/Profile의 실행 fingerprint가 같으면 기존 worker session을 `--resume`하고 달라지면 `NEW`로 시작한다. 현재 알림에는 NEW/RESUME을 다시 주입하지 않는다.

## Cursor / Retry

컨테이너 boot의 `019-devkit-kanban-notifier-policy`가 Gateway profile reconciliation보다 먼저 persistent cursor를 seed한다. 따라서 최초 도입 이전의 과거 event는 재생하지 않으면서, 그 boot barrier 뒤에 생성되는 첫 `created` event부터 놓치지 않는다.

`HERMES_KANBAN_NOTIFY_ENABLED=false`인 동안에도 Bridge 프로세스는 전송만 생략하고 cursor는 계속 따라간다. 나중에 다시 활성화해도 비활성 기간의 과거 이벤트를 몰아서 재생하지 않는다.

```text
event 읽기
→ formatter
→ hermes send
→ 성공: cursor advance
→ 실패: cursor 유지 + bounded backoff retry
```

따라서 알림 실패는 Coder/Reviewer 실행을 막지 않는다. 프로세스가 재시작돼도 persistent cursor에서 이어간다.

## 검증

```bash
python3 scripts/devkit_kanban_notifier.py --self-test
hermes send --help
```

컨테이너에서는 boot policy가 `/run/service/devkit-notifier`를 atomic publish하고 PID 1 `s6-svscan`이 직접 감독한다. DevKit은 이 Bridge에 대해 정적 `/etc/s6-overlay/s6-rc.d` user bundle 활성 여부에 의존하지 않는다.
