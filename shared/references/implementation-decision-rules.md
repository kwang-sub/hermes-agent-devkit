# Implementation Decision Rules

이 문서는 `coding-rules.md`를 대체하지 않고, **코딩 전에 무엇을 만들지·만들지 않을지 결정하는 공통 판단 규칙**을 보완한다.

Karpathy-style 최소 변경 원칙과 Ponytail-style 최소 구현 사다리에서 DevKit에 맞는 부분만 흡수한 canonical reference다. 외부 스킬이나 플러그인의 버전에 DevKit 개발 철학을 종속시키지 않는다.

## 1. 코딩 전에 중요한 가정을 먼저 닫는다

구현 전에 다음 중 결과를 바꿀 수 있는 가정이 남아 있는지 확인한다.

```text
요구사항의 의미가 둘 이상인가
public API / schema / persistence 의미가 달라질 수 있는가
기존 프로젝트에 서로 다른 활성 패턴이 공존하는가
새 dependency / architecture / 공통 contract 선택이 필요한가
보안 / 데이터 손실 / 호환성 / 접근성 결과가 달라질 수 있는가
```

- source/config/기존 구현을 읽어서 확인할 수 있는 가정은 먼저 evidence로 확인한다.
- 합리적인 선택지가 둘 이상이고 product/architecture 의도가 필요한 경우 임의 선택하지 않는다.
- DIRECT/FAST에서 위 결정이 필요해지면 해당 Flow의 escalation 계약을 따른다.
- 단순 syntax, 명백한 기존 pattern 재사용처럼 evidence로 닫히는 질문을 불필요한 사용자 질문으로 만들지 않는다.

## 2. 구현 필요성 사다리

새 코드, abstraction, dependency를 만들기 전에 다음 순서로 판단한다.

```text
0. 현재 요구사항을 만족하려면 정말 변경이 필요한가?
1. 프로젝트에 이미 동일/유사 구현이 있는가?
2. 프로젝트가 이미 사용하는 공통 abstraction/library로 해결되는가?
3. 언어 표준 라이브러리 또는 framework/platform 기본 기능으로 해결되는가?
4. 이미 설치된 dependency의 현재 사용 방식으로 해결되는가?
5. 더 작은 local implementation으로 해결되는가?
6. 그래도 필요할 때만 새 abstraction/dependency를 제안한다.
```

뒤 단계로 갈수록 근거가 더 필요하다.

새 dependency는 편의성만으로 추가하지 않는다. dependency 추가가 필요하면 기존 대안이 부족한 이유, 영향 범위, verification을 남긴다.

## 3. 최소화하면 안 되는 보호 영역

"최소 구현"은 다음을 생략하는 근거가 아니다.

```text
명시된 Acceptance Criteria
correctness / data integrity
입력 validation과 오류 처리
security / authorization / secret 보호
transaction / concurrency 안전성
backward compatibility
접근성(accessibility)
데이터 손실 방지
필수 테스트/검증
```

이 영역은 요구사항과 risk에 맞는 충분한 구현을 해야 한다.

## 4. 변경 범위 계약

- 요구사항과 직접 연결된 최소 diff를 우선한다.
- 현재 Task에 필요하지 않은 cleanup/refactor/modernization을 섞지 않는다.
- 새 helper나 abstraction을 만들었다면 **현재 Task에서 왜 기존 구현보다 필요한지** 설명 가능해야 한다.
- future-proofing만을 이유로 현재 사용되지 않는 extension point를 만들지 않는다.
- 단, 이미 프로젝트가 일관된 extension pattern을 요구하면 그 패턴은 유지한다.

## 5. 완료는 검증 가능한 결과로 정의한다

구현 전에 Acceptance Criteria와 가장 가까운 검증을 정한다.

```text
변경 behavior
→ 가장 가까운 targeted test / typecheck / lint / compile / integration verification
→ 필요할 때만 더 넓은 regression
```

- 실행하지 않은 검증을 PASS라고 보고하지 않는다.
- 동일 scope의 PASS를 단순 확신 확보용으로 반복하지 않는다.
- 변경 후 이전 PASS가 무효가 되었으면 fresh verification을 실행한다.
- 검증이 막히면 우회 반복보다 blocker evidence와 재개 조건을 남긴다.

## 6. Project Pattern과의 우선순위

```text
사용자/Task 명시 정책
→ 대상 프로젝트의 기존 활성 pattern
→ Common Coding / Decision Rules
→ Stack/Capability Skill
→ 일반 best practice
```

Stack/Capability Skill과 외부 Public Skill은 recommendation source다. 프로젝트의 기존 규칙을 자동으로 교체할 권한이 없다.
