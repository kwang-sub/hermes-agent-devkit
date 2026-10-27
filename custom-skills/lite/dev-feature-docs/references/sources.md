# 정책 출처와 차용 범위

확인일: 2026-10-04. 공개 원문은 GitHub 연결로 읽었다. 아래 정책은 Hermes Agent DevKit의 약한 문서 연결에 맞춰 자체 문장으로 작성했으며 외부 코드·템플릿을 포함하거나 외부 스킬을 실행 의존성으로 설치하지 않는다.

## OpenSpec — 논의와 기록의 경계

- 저장소: Fission-AI/OpenSpec
- 확인한 main commit: `2500d6da971336167548b53731a35b2127df35ac`
- 파일: `src/core/templates/workflows/explore.ts`
- 읽은 파일의 blob SHA: `e5ad09819ca695ef775000d140d6a18ecff0852d`
- 원문: https://github.com/Fission-AI/OpenSpec/blob/2500d6da971336167548b53731a35b2127df35ac/src/core/templates/workflows/explore.ts
- 라이선스: MIT. 해당 commit의 LICENSE 확인. Copyright (c) 2024 OpenSpec Contributors.
- 반영: 논의만으로 쓰기/구현을 시작하지 않음, 결정/제안/미정 분리, 명시적 문서화 요청을 요청 범위의 쓰기 동의로 인정, 고정된 질문 수/필수 산출물 없음.
- 제외: OpenSpec CLI, scaffold, 산출물 의존성, 별도 handoff/승인 흐름.

## PM Skills — 범위와 안전한 부분 수정

- 저장소: product-on-purpose/pm-skills
- 확인한 main commit: `1cef1a9eae10017389863d51e289e0ae41e17fcb`
- 파일: `skills/deliver-prd/SKILL.md`
- 읽은 파일의 blob SHA: `e5f564802e4696e96807c7f431981d9897507c1d`
- 원문: https://github.com/product-on-purpose/pm-skills/blob/1cef1a9eae10017389863d51e289e0ae41e17fcb/skills/deliver-prd/SKILL.md
- 라이선스: SKILL.md frontmatter의 `Apache-2.0` 표기 확인.
- 반영: 목적과 사용자 기능 중심 설명, 포함/제외/향후 범위 분리, 쓰기 직전 재확인과 다른 변경 보존.
- 변형: 원문의 프로젝트 메모리 파일 수정 규칙을 기능 Markdown 문서의 부분 수정 원칙으로 적용.
- 제외: 전체 PRD 양식 강제, 의무 KPI/일정/담당자, 별도 프로젝트 메모리 시스템, 실행 계약 Gate.

## Ralph PRD — 확인 가능한 완료 기준

- 저장소: snarktank/ralph
- 확인한 main commit: `6c53cb0b831ebe8739c6a003e22af14902d8b0b5`
- 파일: `skills/prd/SKILL.md`
- 읽은 파일의 blob SHA: `3c2f7acf886603e263a1bc9faed9d7fe844c3298`
- 원문: https://github.com/snarktank/ralph/blob/6c53cb0b831ebe8739c6a003e22af14902d8b0b5/skills/prd/SKILL.md
- 라이선스: MIT. 해당 commit의 LICENSE 확인. Copyright (c) 2026 snarktank.
- 반영: 사용자 행동·조건·기대 결과로 확인 가능한 완료 기준, 제외 범위, 문서 작성과 구현 분리.
- 제외: 3~5개 질문 강제, 스토리 ID와 세션 크기 분해, 특정 브라우저 스킬 의존성.

## 자체 정책

경로 기반 선택적 연결, 관찰 기반 상태 반영, worktree 쓰기 경계, 문서 실패의 비차단 처리, README에 상태를 복제하지 않는 원칙과 읽기 전용 후보 수집기는 이번 합의에 따라 자체 작성했다. 외부 정책의 모든 기능이나 검증 보장을 제공한다고 설명하지 않는다.

원문은 main에서 읽고 같은 조사 중 main commit을 별도로 확인했다. 파일 blob SHA도 기록하여 재검토할 수 있게 했다. 위 commit과의 바이트 일치 검사를 수행했다고 주장하지 않는다.
