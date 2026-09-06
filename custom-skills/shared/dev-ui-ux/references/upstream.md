# Upstream / Audit Record

이 adapter의 UI/UX baseline은 아래 공개 프로젝트의 Skill 구조와 우선순위를 참고해 DevKit 정책에 맞게 재구성했다.

```text
Project: nextlevelbuilder/ui-ux-pro-max-skill
Upstream skill: .claude/skills/ui-ux-pro-max/SKILL.md
Observed commit: 314307f156aeab0c6b567bbaa1ce4e7aabd5a636
License: MIT (upstream repository)
Audit date: 2026-09-06
```

## Adapter 원칙

- upstream의 Claude-specific `${CLAUDE_PLUGIN_ROOT}` 경로와 runtime search command를 DevKit에 그대로 복제하지 않는다.
- upstream 검색 데이터 결과를 실행하지 않았는데 검색 결과인 것처럼 보고하지 않는다.
- project Design System / existing component가 upstream recommendation보다 우선한다.
- upstream 업데이트는 자동 반영하지 않는다. 버전/내용 검토 후 별도 변경으로 갱신한다.
- 이 repository에는 upstream 전체 dataset/engine을 vendor하지 않고 안정적인 baseline rule과 provenance만 유지한다.

향후 full search engine 도입이 필요하면 별도 dependency/vendor 검토를 거쳐 source commit, license, update policy, test를 함께 추가한다.
