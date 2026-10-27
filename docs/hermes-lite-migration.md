# Lite 단일 표준 전환

기존 Lite/Standard 병행 실험을 종료하고, default 직접 개발을 표준으로 한다. DevKit 역할 스킬·승인 상태 머신·Worker startup/session affinity/model transition/자동 복구 및 복구 전용 표시 패치를 삭제한다. Hermes upstream의 일반 프로필 관리 기능은 수정하지 않는다.

## 사전 이관

`git-pr-publish`, `git-workspace-cleanup`, `dev-feature-docs`, `dev-project-pattern`, `dev-lite-review`와 Worktree 생성/제거를 Lite에 보존했다. 선택적 Jira와 프로젝트 툴체인·설정 보안 준비도 직접 실행 가능하다. Maven/Gradle 엔진·검증 캐시와 process_execution은 역할 독립 경로를 사용하며 같은 코드를 역할별로 복제하지 않는다.

Shared 데이터·API·Infrastructure의 설계와 실행 권한은 유지하되 별도 Task/프로필·pin·Dispatch는 요구하지 않는다. 논리 모델 승인, migration 파일 작성, 실제 운영 DB 적용은 다른 범위이며 승인된 순서로 같은 세션에서 진행할 수 있다.

## 안전한 부팅 순서

`01-hermes-setup`의 upstream 데이터 준비 이후 `018-devkit-lite-init`가 실행된다. 이 스크립트는 `02-reconcile-profiles`보다 먼저 default 설정·역할 보관을 끝낸다. `S6_BEHAVIOUR_IF_STAGE2_FAILS=2`로 검사가 실패한 컨테이너는 서비스 시작을 계속하지 않는다. 별도 native dispatcher 비활성화가 자동 Worker 생성도 차단한다.

`lite_default_profile.py`는 관리된 skill roots/auto-load/toolsets/dispatch만 갱신하고 다른 설정은 보존한다. 이전 overlay schema 1/2는 현재 값이 기록과 일치하는지 먼저 확인하여 오래된 백업으로 사용자 편집을 덮어쓰지 않는다. 설정은 원자적으로 기록하고 read-back한다. exclusive lock, 비밀값 없는 journal, private 원본 백업, 실패 시 이번 변경의 원복을 사용한다.

기존 역할 홈은 `/opt/data/devkit-lite/legacy-profiles/{orchestrator,coder,reviewer}`에 그대로 보관된다. OAuth·메모리·세션을 default에 임의 병합하지 않는다. 알 수 없는 schema, active/archive 충돌, symlink를 통한 경계 이탈, 실행 중 카드, 불완전 journal은 실패로 처리한다. 사용자 카드 상태를 자동 변경하지 않는다.

## 실행과 복구

`update-devkit.ps1` 하나가 설치/업데이트를 담당한다. 기존 컨테이너의 실제 mount를 보존하며 read-only 계획을 통과한 뒤 새 이미지를 사용한다. 이미지 빌드는 실행 컨테이너 정지 전에 완료된다. 전환 실패 후 재생성·재시도를 자동 반복하지 않는다.

표준 전환 이후 `updatekit_lite.ps1 -Mode standard`로 복원하지 않는다. 보관된 이전 코드 버전과 `devkit-lite/backups/`는 명시적 운영 복구의 자료다. 프로필 archive를 복원하려면 먼저 서비스를 정지하고 동일 경로 충돌·이후 사용자 변경 여부를 검토해야 한다. archive/data volume을 제거해서 해결하지 않는다.

## 운영 확인

CI는 임시 이름·label을 가진 자체 컨테이너/볼륨에서만 동작한다. 실제 사용자 Windows PC의 Docker 연결, 외부 mount 권한, OAuth와 모델 응답은 별도 확인이 필요하다. 설치 안내는 루트 README를 따른다.
