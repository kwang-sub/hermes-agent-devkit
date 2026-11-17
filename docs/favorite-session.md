# Hermes DevKit — 세션 즐겨찾기

## 목적

오랫동안 여러 프로젝트를 오가더라도 중요한 Hermes 세션을 다시 찾을 수 있도록 Hermes 네이티브 세션 Pin 기능을 `dev-favorite-session` 스킬의 선택 UI에 연결한다. 기존 SQLite 세션 내용은 변경하거나 복제하지 않는다. **Pin 해제는 대화 삭제가 아니다.**

## 사용자 흐름

Hermes 대화창에서 `/dev-favorite-session`을 입력하면 기본 `clarify` 선택 UI에 다음 메뉴가 나온다.

1. 신규 등록 — 제목 자유입력, 현재 세션 제목 설정/변경, native Pin 등록
2. 즐겨찾기 목록 — 고정된 세션을 선택한 후 `/resume <ID>` 실행 방법 안내
3. 즐겨찾기 재개 — 제목 자유입력, 정확/대소문자 무시/고유 접두 검색 후 `/resume <ID>` 안내
4. 즐겨찾기 삭제 — 목록 선택, **별도 확인 UI**, native Unpin만 수행

등록된 세션에 같은 제목을 입력하면 변경 없이 Pin 상태를 유지한다. 등록하는 제목이 다른 세션에 이미 있으면 기존 세션에 Pin이 남지 않도록 신규 Pin을 복구한다.

`clarify`는 기본적으로 **Other(자유입력)** 항목을 덧붙인다. 목록에는 한 페이지당 세션 2개와 `이전 페이지`/`다음 페이지`를 필요할 때 표시한다.

### 재개 UX의 한계

`/dev-favorite-session`은 LLM 스킬로 실행된다. 이미 진행 중인 모델 턴 안에서 `/resume`이 부모 CLI의 실행 세션을 전환한다고 가정하지 않는다. **목록/재개 기능을 선택하면 스킬 결과로 `/resume <ID>`를 알려준다. 스킬 응답이 끝난 다음 같은 Hermes 입력창에 이 명령을 다시 입력해야 한다.** CLI 내부 원클릭 전환은 별도 TUI/CLI 어댑터 후속 작업이다.

## 저장/호환성

- Hermes 기존 `sessions pin`, `sessions pinned --json`, `sessions rename`, `sessions unpin`을 호출한다.
- 세션의 제목과 Pin은 동일한 Hermes native `state.db`에 저장된다. 커스텀 즐겨찾기 파일/DB를 만들지 않는다.
- Hermes native Pin은 압축 계보 단위로 고정하므로 후속 세션을 별도 추적할 필요가 없다.
- DevKit의 `/opt/data` 마운트와 프로필 분리는 그대로 둔다. 기존 데이터 볼륨이 보존될 때 컨테이너 재생성 후에도 Pin은 유지된다.
- 스킬은 `custom-skills/core/dev-favorite-session/SKILL.md`에 두며, DevKit의 `external_dirs`에 core가 포함되므로 기존 로딩 경로를 재사용한다.
- 설치된 Hermes 버전에서 Pin 서브커맨드가 누락됐다면 mutation을 시도하지 않고 지원 버전 확인을 안내한다. 최신 소스의 동작과 실행 중 컨테이너의 버전은 구별한다.

## 설치 후 확인

Hermes에서 (스킬 호출 전에는 bash/PowerShell 외부 터미널에서) 다음을 확인한다.

```bash
hermes sessions --help
hermes sessions pinned --json
```

DevKit의 Docker 컨테이너 안에서는 사용자 권한과 프로필을 일치시켜 확인할 수 있다.

```powershell
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p default sessions --help
docker exec --user hermes hermes-dev /opt/hermes/.venv/bin/hermes -p default sessions pinned --json
```

실제 세션 Pin 등록은 **컨테이너를 업데이트한 뒤** `/dev-favorite-session`을 실행해 메뉴에서 `신규 등록`을 선택한다. 새로 작성한 스킬이 기존 프로세스 캐시에 보이지 않으면 `/reload-skills` 또는 새 Hermes 세션에서 다시 시도한다.

## CLI Helper 직접 호출

Hermes CLI Python 환경/실행 경로가 일반 기본값이 아닌 경우 `HERMES_CLI_BIN`으로 명시할 수 있다. 실행 명령은 셸 문자열이 아닌 `subprocess.run(argv, shell=False)` 형태다.

```bash
SKILL=/opt/custom-skills/core/dev-favorite-session
python3 "$SKILL/scripts/favorite_session.py" list --offset 0 --limit 2
python3 "$SKILL/scripts/favorite_session.py" prepare-resume --title 'XOCR-인증개선'
python3 "$SKILL/scripts/favorite_session.py" register --session-id '20261117_101500_a1b2c3' --title 'XOCR-인증개선'
# 실제 삭제 확인을 받았을 때만 실행:
python3 "$SKILL/scripts/favorite_session.py" remove --session-id '20261117_101500_a1b2c3' --expected-title 'XOCR-인증개선' --confirmed
```

실제 세션 ID는 환경/상황에 따라 달라진다. 위 문자열은 예시다. JSON의 `ok=true`와 처리 대상을 확인한 뒤 성공을 안내한다.

### 오작동 방지

- 스킬 호출 시 세션 ID 토큰 `${HERMES_SESSION_ID}`가 치환되지 않으면 신규 등록을 금지한다.
- 제목과 ID를 셸 명령 문자열에 결합하지 않는다. 셸에서 실행해야 할 때는 사용자 제목을 정확하게 shell-quote한다.
- 명령 오류·접근 권한 오류·버전 불일치·중복 제목·압축으로 ID 변경이 의심되면 성공 보고나 임의 후속 세션 선택을 하지 않는다.
- 제목 변경과 Pin은 native CLI의 **별도 작업**이므로 완전 원자적이지 않다. 신규 Pin 이후 변경 실패 시 고정을 복구하며, 복구에 실패하면 `partial_failure`를 보고한다.
- **`sessions delete`, `prune`, `archive` 호출 금지**. 삭제 메뉴는 `unpin`만 한다.
- CLI 명령이 실행되는 사용자/프로필을 실제 Hermes 사용 프로필과 일치시킨다. 컨테이너에서 root로 임의 실행하지 않는다.

## 검증

```bash
python3 custom-skills/core/dev-favorite-session/tests/test_favorite_session.py
# DevKit 전체 검증(실제 소스 checkout에서)
bash scripts/verify.sh
```

단위 테스트는 Hermes 저장소를 직접 수정하지 않는다. 하지만 네이티브 CLI 버전/런타임 연동, TUI에서 실제 `clarify` 표시, 등록된 세션 선택, 삭제 재확인, 업데이트 후 보존은 별도 실행 환경 수동 검증 대상이다.
