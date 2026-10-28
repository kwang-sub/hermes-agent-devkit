# Lite 검증 이동 내역

## 제거한 검사는 어떤 검사인가

Direct/Standard 분류, Orchestrator 승인 필드, Coder/Reviewer 스킬 pin, Worker claim/handoff/session affinity, 모델 등급 전환, 자동 task recovery처럼 폐기한 실행 방식만 검증하던 검사와 fixture는 삭제했다. 실패를 숨기기 위해 application/build/security 검사를 생략한 것이 아니다.

## 유지·이관한 검사

- `scripts/run_regression_tests.py`가 모든 `scripts/test_*.py`, `scripts/verification/tests/test_*.py`, `custom-skills/*/*/tests/test_*.py`를 별도 프로세스로 실행한다. 스킬 이동으로 기존 경로만 수정한 테스트도 포함한다.
- 실제 Maven launcher/output isolation, Gradle timeout/child cleanup/cache, Node/pnpm 격리·restore·보안 정책, Git publication·cleanup, 기능 문서 검색, DBML·migration guard, 공식 문서/Figma provider, UI adapter/dialog/evidence 회귀를 유지한다.
- 기술 정책의 기존 문자열 검사는 `domain-contracts.json`에 모아 도메인 규칙/공식 참고 문서가 빠지지 않게 한다. 역할별 연결 검사는 활성 catalog·related_skills·런타임 참조 검증으로 교체했다.
- 프로젝트 bootstrap 전체 등록 엔진은 제거하고 툴체인·설정 보안·Gitignore·빠른 preflight·기술 감지의 독립 helper와 테스트만 Lite로 옮겼다.

## 신규 안전 검증

Default migration은 fixture의 인증·메모리·세션 보존, private backup, overlay 1/2, symlink/충돌·잘못된 YAML·unknown DB schema·실행 중 카드 차단, 중간 실패 원복·중단 journal·멱등성을 확인한다.

Windows PowerShell 5.1은 named volume/host bind/외부 readonly mount를 비롯한 inspect 파싱·override 보존을 검사한다. 실제 updater 코드를 mock Docker/Git으로 실행해 정상 순서, local dirty, active worker, build failure, mount mismatch와 불필요한 repair 방지를 검사한다. 사용자 `.env`와 실제 Docker는 읽지 않는다.

최신 Hermes CI는 실제 이미지로 새로운 볼륨 및 기존 역할 데이터를 가진 host bind의 부팅·재시작, default Gateway, 자동 dispatcher 비활성화, 데이터 보존을 검사한다. active task/보관 경로 충돌 fixture는 서비스가 시작되기 전에 종료되어야 한다. 이 테스트가 만든 UUID-labelled 자원만 정리한다.

이 검사들의 성공은 실제 사용자 제품 코드의 검증이나 Windows Docker Desktop/OAuth/모델 응답 확인을 의미하지 않는다. 실행 결과는 CI와 해당 실행의 regression report를 기준으로 보고한다.

업데이트 이미지 생명주기 회귀는 기존 컨테이너 이미지가 Docker 저장소에서 사라져도 빌드 후 새 이미지 ID로 사전 검사를 수행하는지, 이전 이미지가 없을 때 필수 검사를 건너뛰지 않는지, 루트에는 `update-devkit.ps1` 하나만 남는지를 확인한다.
