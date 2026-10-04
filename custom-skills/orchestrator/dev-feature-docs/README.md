# dev-feature-docs 사용 안내

Orchestrator용 기능 문서 관리 스킬이다. 기능 문서는 `docs/features`에 두고 Standard Flow와는 선택적 문서 연결만 사용한다.

## 요청 예시

```text
새 기능 아이디어를 논의하자. 아직 문서는 바꾸지 마.
논의한 내용을 docs/features/tag-build-notification.md로 정리해줘.
기존 기능 문서에 실패 알림 조건만 추가해줘.
성과 분석 기능의 구현 여부를 기존 코드와 검증 결과로 확인해줘.
docs/features/portfolio-performance.md의 MDD 범위를 Standard Flow로 구현해줘.
```

문서 작성은 구현 시작이 아니다. 문서에 없는 정보는 미정으로 두고 사용자 결정과 제안을 섞지 않는다. `구현 완료`는 문서의 현재 합의 범위를 기준으로 하며 merge/배포를 뜻하지 않는다.

## 파일 구성

- `SKILL.md`: 요청 구분, 상태, 역할 경계, 진입 규칙.
- `references/document-policy.md`: 부분 수정·범위·근거 정책.
- `references/standard-flow.md`: 문서 후보/연결 구분과 기존 Flow 연동.
- `references/sources.md`: 공개 정책 출처, 확인한 commit/blob, 차용/제외 범위.
- `templates/feature.md`, `templates/index.md`: 선택적 문서 템플릿.
- `scripts/find_feature_docs.py`: 읽기 전용 후보 검색. 상태/연결을 결정하지 않음.
- `tests/test_find_feature_docs.py`: 임시 디렉터리 기반 단위 테스트.

## 후보 검색

```bash
python3 custom-skills/orchestrator/dev-feature-docs/scripts/find_feature_docs.py \
  --project-root /workspace/example --query 'MDD 최대낙폭'

python3 custom-skills/orchestrator/dev-feature-docs/scripts/find_feature_docs.py \
  --project-root /workspace/example --document docs/features/portfolio-performance.md

python3 custom-skills/orchestrator/dev-feature-docs/scripts/find_feature_docs.py \
  --project-root /workspace/example --approved-document docs/features/portfolio-performance.md
```

명시한 경로가 있으면 기존 연결/자동 검색보다 우선한다. 지정 경로가 없어져도 다른 문서로 바꾸지 않는다. `--document`와 `--approved-document`는 여러 번 지정할 수 있다. 이름만 입력한 요청은 Orchestrator가 제목/내용을 확인해 실제 상대 경로를 정한다.

자동 검색은 `docs/features` 안으로 제한된다. 기본 최대 512개 디렉터리 항목, 80개 Markdown 파일, 파일당 64 KiB, 결과 12개다. 한계/권한/인코딩/경로 오류는 `warnings`와 `partial`/`unavailable`로 표시한다. 결과가 없거나 부분 결과인 것은 관련 기능 문서가 절대 없다는 증거가 아니다. preview가 잘렸으면 전체 의미를 확인한 것으로 간주하지 않는다.

검색은 어휘 기반이며 의미적 일치 판정기가 아니다. `binding_decided`는 항상 false다. 문자열 점수만으로 기능 문서를 자동 연결하거나 상태를 갱신하지 않는다. helper는 명령 실행, 네트워크 접근, 문서 쓰기, Kanban 호출을 하지 않는다.

## 상태 반영 시점

Orchestrator가 기존 진행 응답/조회에서 실제 착수·완료를 확인했을 때 승인된 문서에 부분 반영한다. worker가 독립 실행 중이면 문서 상태의 즉시 갱신은 보장하지 않는다. 다음 상태 조회·작업 재개·명시적 문서 확인에서 보완한다. 별도 polling/watcher/lifecycle hook은 없다.

## 검증

저장소 루트에서 실행한다.

```bash
python3 scripts/check_feature_docs_contract.py
python3 custom-skills/orchestrator/dev-feature-docs/tests/test_find_feature_docs.py
```

첫 명령은 스킬 문서와 통합 규칙의 정적 계약 검사다. 두 번째는 검색 helper 단위 테스트다. 실제 Hermes의 도구 선택, 문서 갱신, Kanban 흐름을 실행하는 end-to-end 테스트는 아니다.
