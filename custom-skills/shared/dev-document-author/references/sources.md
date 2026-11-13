# 참고 자료와 적용 범위

이 스킬의 한국어 규칙과 예문은 사용자의 요구사항에 맞춰 새로 작성했다. 외부 스킬의 생성 코드나 본문을 복제하지 않는다.

## 확인한 공식 자료

- NousResearch/hermes-agent, `skills/productivity/microsoft-office/SKILL.md`, v2.0.0, MIT: https://github.com/NousResearch/hermes-agent/blob/main/skills/productivity/microsoft-office/SKILL.md
- NousResearch/hermes-agent, `skills/productivity/pdf/SKILL.md`, v1.1.0: https://github.com/NousResearch/hermes-agent/blob/main/skills/productivity/pdf/SKILL.md
- NousResearch/hermes-agent, `skills/creative/humanizer/SKILL.md`, v2.5.1, MIT. 원저자 Siqi Chen (@blader), Hermes 이식본: https://github.com/NousResearch/hermes-agent/blob/main/skills/creative/humanizer/SKILL.md
- 원본 Humanizer: https://github.com/blader/humanizer

확인일: 2026-10-30. 위 버전은 조사한 문서의 버전이지 사용자 컨테이너의 설치 버전이나 고정 의존성이 아니다. 실제 작업 때 설치된 스킬과 참조를 읽는다.

Humanizer의 의미 보존·독자에 맞는 문체·과장과 반복 줄이기는 참고했다. 영어 표현 목록, 감정·의견 추가, 탐지 회피, 초안/자기평가 반복 출력은 한국어 업무 문서의 기본 규칙으로 채택하지 않았다. 한국어 단어의 사용 빈도를 측정했다는 주장은 하지 않는다.

## HTML 시안 연동 참고 자료

확인일: 2026-11-13. 최초 도입 pack이 고정한 `mock-review` 1.2.0의 아래 커밋을 기준으로 native JSON과 CLI 인수만 확인했다. community 플러그인이며 Nous Research의 직접 유지보수 또는 보안 감사 완료를 뜻하지 않는다.

- JSON 블록·HTML 정제·피드백 규격: https://github.com/apelabs-dev/hermes-mock-review/blob/4ec3b90d63ef82efa2c91c6e62845e1f16f66d88/docs/decisions-format.md
- CLI: https://github.com/apelabs-dev/hermes-mock-review/blob/4ec3b90d63ef82efa2c91c6e62845e1f16f66d88/docs/cli.md
- 로컬·no-wake 설정: https://github.com/apelabs-dev/hermes-mock-review/blob/4ec3b90d63ef82efa2c91c6e62845e1f16f66d88/plugin.yaml
- 저장소 `shared/design-plugins/hermes-pack.yaml`, `docs/design-plugins.md`: 버전·로컬 노출·수동 운영의 기준. 실행할 때 설치 버전의 도움말과 도구 스키마를 다시 확인한다.

HTML 시안 선행, 실제 내용으로 A/B 비교, 선택 대기, 편집 가능한 PPT 제작 규칙은 이 작업을 위해 새로 작성한 DevKit 정책이다. 플러그인이 PPT를 자동 재디자인하거나 HTML을 PPT로 무손실 변환한다는 주장이 아니다.

## 저장소의 기존 기준

- `custom-skills/core/dev-session/SKILL.md`: 변경 승인과 필요 시 스킬 로딩.
- `custom-skills/core/dev-feature-docs/SKILL.md`: 기능 문서의 범위와 구현 상태.
- `custom-skills/shared/dev-api-docs/SKILL.md`: API 계약과 문서 동기화.
- `scripts/run_regression_tests.py`: 스킬의 `tests/test_*.py` 자동 탐색.

정적 테스트는 정책의 필수 항목·참조·예문의 보호 값과 등록 상태만 확인한다. 모델이 실제로 자연스럽게 작성하는지, 사용자 환경에서 문서가 올바르게 렌더링되는지는 별도 실행·내용 검토로 확인해야 한다.
