---
name: dev-favorite-session
description: Hermes 대화 세션을 제목으로 고정(Pin)하고 즐겨찾기 목록에서 찾거나 재개하고 안전하게 고정 해제한다. Hermes 네이티브 sessions pin/pinned/unpin/rename을 사용한다.
version: 0.1.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, core, session, favorite, pinned, resume, interactive]
    related_skills: [dev-session]
    requires_tools: [terminal, clarify]
---

# dev-favorite-session

Hermes **현재 대화 안에서** 세션 즐겨찾기를 관리한다. 사용자는 `/dev-favorite-session`으로 시작한다. 별도 즐겨찾기 DB를 만들지 않고 Hermes의 `sessions pin`, `pinned`, `unpin`, `rename`을 재사용한다. 실제 세션/대화 기록은 삭제하지 않는다.

## 인터랙티브 실행

스킬을 호출하면 다른 파일이나 프로젝트를 수정하기 전에 **반드시 네이티브 `clarify` 도구**로 다음 단일 선택 질문을 보여준다. 목록을 일반 텍스트로 출력하고 숫자를 맞혀서는 안 된다.

```json
{"questions":[{"question":"세션 즐겨찾기에서 어떤 작업을 하시겠습니까?","choices":["신규 등록","즐겨찾기 목록","즐겨찾기 재개","즐겨찾기 삭제"],"multi_select":false}]}
```

- 기본 `clarify`의 `Other` 자유입력 항목은 Hermes가 자동 추가한다. 네 가지 선택지만 직접 정의한다.
- `outcome=submitted` / `status=answered`인 **해당 질문의 실제 응답**만 처리한다. 취소, 시간 초과, 잘못된 응답, `clarify` 미지원이면 아무것도 변경하지 않는다.
- `clarify` 입력을 shell 명령으로 그대로 조합하지 않는다. 명령을 호출할 때 사용자 입력은 별도 인자로 전달하고 POSIX shell 단일 인자 인용(`shlex.quote`와 동등)을 적용한다. 제목·세션 ID를 셸 확장/파이프/명령 치환에 넣지 않는다.
- 작업용 도우미는 `python3 "${HERMES_SKILL_DIR}/scripts/favorite_session.py"`이다. 출력은 `{ok, action, ...}` 형태의 **JSON 한 객체**다. `ok=false`이거나 종료 코드가 실패이면 완료했다고 말하지 않는다.
- `${HERMES_SESSION_ID}`는 **현재 호출 세션의 ID**로 스킬 로드 시 치환된다. 이 토큰이 치환되지 않았거나 실제 사용 중인 세션과 일치한다고 확인할 수 없다면 신규 등록을 중단한다. 다른 세션 ID를 추측하거나 임의 최근 세션을 Pin하지 않는다.
- 이 스킬은 사용자가 선택한 세션 *메타데이터 Pin/타이틀*만 다룬다. 소스·설정 변경 승인 UI를 반복 출력하지 않는다. 단, 사용자가 개발 코드 변경을 함께 요청하면 `dev-session`의 별도 구현 승인 계약을 적용한다.

## 1. 신규 등록

1. 제목을 `clarify` 자유입력(choices 생략)으로 한 번 받는다. 이미 `/title`이 등록된 세션도 입력한 제목으로 **변경**한다.
2. 입력이 취소/공백이면 중단한다. 현재 세션 ID는 `${HERMES_SESSION_ID}`에서만 얻는다.
3. 아래 helper를 호출한다. 제목에 공백·한글이 포함될 수 있으므로 전체를 정확히 하나의 인자로 인용한다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/favorite_session.py" \
  register --session-id "${HERMES_SESSION_ID}" --title 'XOCR-인증개선'
```

4. JSON `ok=true`일 때만 등록 성공을 보고하고 `pin_added`, `title_updated`를 구별한다. 이미 같은 이름으로 Pin돼 있으면 멱등적으로 유지한다. 제목 충돌·Pin 실패는 상태를 설명한다. **등록 성공을 증명하지 못하면 성공으로 표시하지 않는다.**

## 2. 즐겨찾기 목록

1. 아래 명령으로 현재 페이지를 조회한다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/favorite_session.py" list --offset 0 --limit 2
```

2. `sessions`를 제목과 고유 ID 식별자로 표시한다. 한 화면에 최대 4개의 `clarify` 선택지를 준다: 현재 페이지의 **최대 2개 세션**, 필요한 경우 `이전 페이지`와 `다음 페이지` 선택지다. 페이지 이동은 `offset`을 2 단위로 변경한다. 빈 목록이면 아무 선택 없이 안내한다.
3. 세션을 선택하면 반드시 **고유 ID**로 `prepare-resume --session-id`를 호출한다.
4. 준비 결과의 `resume_slash`를 그대로 출력한다. 현재 모델 턴 도중에 다른 `hermes` 대화 프로세스를 실행하거나 세션 DB의 라우팅 정보를 직접 변경하지 않는다. 사용자가 현재 응답을 마친 다음 **입력창에 `/resume <ID>`를 입력**해야 실제 세션이 전환됨을 명확히 안내한다.

## 3. 즐겨찾기 재개

1. `clarify` 자유입력으로 타이틀을 받는다.
2. 아래 명령으로 Pin된 세션의 제목을 조회한다. 정확히 일치하는 제목을 먼저 찾고, 없으면 대소문자 무시 일치, 그다음 유일한 접두 일치를 허용한다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/favorite_session.py" \
  prepare-resume --title 'XOCR-인증개선'
```

3. 유일한 결과가 있다면 응답 종료 후 사용할 `/resume <ID>`를 보여준다. 여러 세션이 일치하면 후보 제목을 보여주고 정확한 제목 또는 목록 선택을 다시 받는다. 실제로 **재개되었다고 주장하지 않는다**. Hermes 네이티브 `/resume`을 사용하면 압축된 세션의 최신 계보로 이어지는 동작을 재사용한다.

## 4. 즐겨찾기 삭제

1. 즐겨찾기 목록과 동일한 페이지 선택 UI로 대상 세션을 고른다.
2. 선택한 **정확한 제목과 고유 세션 ID**를 다시 보여주고, 별도의 `clarify`를 호출한다.

```json
{"questions":[{"question":"선택한 세션의 즐겨찾기 Pin만 해제하시겠습니까? 기존 대화 내용은 보존됩니다.","choices":["즐겨찾기 해제","취소"],"multi_select":false}]}
```

3. `즐겨찾기 해제`가 명시적으로 응답된 경우에만 실행한다. `--expected-title`은 목록에서 선택한 원래 제목이다.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/favorite_session.py" \
  remove --session-id '20261117_101500_a1b2c3' \
  --expected-title 'XOCR-인증개선' --confirmed
```

4. helper가 목록을 다시 확인해 **ID와 제목이 동일할 때만** 네이티브 `sessions unpin`을 호출한다. `ok=true` 이후에만 해제 완료를 보고한다. 별도의 확인 UI 없이 `--confirmed`를 전달하지 않는다. 이미 제목이 바뀌었으면 목록 조회/확인을 다시 시작한다.

## 제한 및 안전 정책

- 본 스킬은 Pin 제거만 제공한다. **`sessions delete`, `prune`, `archive`, `rm -rf`, `UPDATE state.db` 호출 금지**. Docker `/opt/data`와 기존 프로필을 보존한다.
- 중요: Hermes의 고유한 `/resume`은 CLI 세션 경계에서 수행한다. 현재 스킬 LLM 턴 **한가운데서** 에이전트가 자신의 부모 대화를 전환할 수 있다고 가정하지 않는다. 목록/재개 결과는 `resume_slash`로 제공한다. 원클릭 전환은 별도의 최소 TUI/CLI 어댑터 범위다.
- `pinned --json` 결과를 유일한 목록 기준으로 사용한다. 원본 DB 스키마를 자체 분석하거나 복제하지 않는다.
- 제목 변경과 Pin은 별도 Hermes 명령이므로 완전한 단일 트랜잭션이 아니다. 신규 Pin 후 제목 변경 실패 시 helper가 **해당 Pin만 복구**한다. 부분 실패나 검증 불가 시 결과를 숨기지 않는다.
- 중복 제목 충돌·압축 도중 세션 ID 변경·프로필 불일치·명령 미지원이면 임의 세션을 고르지 않고 중단한다.
- 등록/해제/재개 대상은 사용자 대화 세션이다. CLI `oneshot`, 보안 영역이 다른 프로필, 다른 사용자의 채널로 넘어가는 강제 세션 전환을 만들지 않는다.

## 검증

```bash
python3 "${HERMES_SKILL_DIR}/tests/test_favorite_session.py"
```

실제 컨테이너에서는 설치된 Hermes CLI 버전을 먼저 확인한다. 테스트는 사용자의 실 세션 DB를 조작하지 않는 모의 CLI/실행 매개변수 기반이며, 실제 TUI 선택/전환은 별도로 수동 확인한다.
