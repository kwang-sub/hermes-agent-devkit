# 참고 자료와 적용 범위

이 스킬의 한국어 규칙과 예문은 사용자의 요구사항에 맞춰 새로 작성했다. 외부 스킬의 생성 코드나 본문을 복제하지 않는다.

## 확인한 공식 자료

- NousResearch/hermes-agent, `skills/productivity/microsoft-office/SKILL.md`, v2.0.0, MIT: https://github.com/NousResearch/hermes-agent/blob/main/skills/productivity/microsoft-office/SKILL.md
- NousResearch/hermes-agent, `skills/productivity/pdf/SKILL.md`, v1.1.0: https://github.com/NousResearch/hermes-agent/blob/main/skills/productivity/pdf/SKILL.md
- NousResearch/hermes-agent, `skills/creative/humanizer/SKILL.md`, v2.5.1, MIT. 원저자 Siqi Chen (@blader), Hermes 이식본: https://github.com/NousResearch/hermes-agent/blob/main/skills/creative/humanizer/SKILL.md
- 원본 Humanizer: https://github.com/blader/humanizer

확인일: 2026-10-30. 위 버전은 조사한 문서의 버전이지 사용자 컨테이너의 설치 버전이나 고정 의존성이 아니다. 실제 작업 때 설치된 스킬과 참조를 읽는다.

Humanizer의 의미 보존·독자에 맞는 문체·과장과 반복 줄이기는 참고했다. 영어 표현 목록, 감정·의견 추가, 탐지 회피, 초안/자기평가 반복 출력은 한국어 업무 문서의 기본 규칙으로 채택하지 않았다. 한국어 단어의 사용 빈도를 측정했다는 주장은 하지 않는다.

## 저장소의 기존 기준

- `custom-skills/core/dev-session/SKILL.md`: 변경 승인과 필요 시 스킬 로딩.
- `custom-skills/core/dev-feature-docs/SKILL.md`: 기능 문서의 범위와 구현 상태.
- `custom-skills/shared/dev-api-docs/SKILL.md`: API 계약과 문서 동기화.
- `scripts/run_regression_tests.py`: 스킬의 `tests/test_*.py` 자동 탐색.

정적 테스트는 정책의 필수 항목·참조·예문의 보호 값과 등록 상태만 확인한다. 모델이 실제로 자연스럽게 작성하는지, 사용자 환경에서 문서가 올바르게 렌더링되는지는 별도 실행·내용 검토로 확인해야 한다.
