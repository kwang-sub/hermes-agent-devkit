# Risk-based Verification Level Policy

이 문서는 Maven, Gradle, Node/TypeScript를 포함한 구현 검증의 공통 `VERIFICATION_LEVEL_POLICY_V1` 계약이다. 목적은 **변경 위험을 충분히 검증하는 최소 단계부터 시작하고, 실제 영향이 있을 때만 test 또는 package/build로 승격**하는 것이다.

## 1. 우선순위

검증 명령과 수준은 다음 순서를 따른다.

```text
명시된 사용자/Task Verification Contract
        ↓
대상 프로젝트의 기존 script / CI / AGENTS / build convention
        ↓
VERIFICATION_LEVEL_POLICY_V1의 ecosystem mapping
        ↓
DevKit fallback
```

프로젝트가 이미 `check`, `typecheck`, `test`, module test, Maven/Gradle task 같은 canonical 검증을 제공하면 이를 우선한다. DevKit이 검증 편의를 위해 새 runner/plugin/build script를 만들거나 기존 project convention을 교체하지 않는다.

## 2. Verification Level

### STATIC_COMPILE

변경된 source가 현재 project/toolchain에서 정적으로 성립하는지 확인하는 기본 수준이다.

```text
Java/Maven  → compile + testCompile 계열
Java/Gradle → classes/testClasses 또는 project canonical compile task
Node/TS     → project canonical typecheck/check, 필요한 project-mandatory lint
```

일반 application source 변경에서 package/build artifact 생성은 기본 요구가 아니다.

### TARGETED_TEST

변경된 동작, bug regression, 직접 영향 범위를 기존 테스트로 증명해야 할 때 `STATIC_COMPILE`에서 승격한다.

승격 조건 예:

- behavior/API/session/security/persistence 의미가 변경됨
- bug fix에 직접 재현 가능한 test가 있음
- 변경 영역과 직접 연결된 unit/component/integration test가 존재함
- Task Acceptance Criteria가 실행 가능한 테스트를 명시함

가능하면 affected test를 한 invocation으로 묶는다. 관련 테스트가 없고 새 테스트 추가가 현재 Work Unit 밖이면 `STATIC_COMPILE` 결과와 미검증 behavior를 handoff에 명시한다.

### PACKAGE_BUILD

배포 artifact/framework build 결과 자체가 검증 대상일 때만 승격한다. **일반 application source 변경의 기본값이 아니다.**

승격 조건:

- `pom.xml`, Gradle build logic, `package.json` build script, lockfile/dependency scope가 변경됨
- Maven WAR/JAR, Gradle JAR/WAR/bootJar, frontend bundle 등 artifact 구조가 변경됨
- resource filtering/copy, manifest, packaging plugin, bundler/framework config가 변경됨
- Docker/image/release/deployment artifact가 현재 Acceptance Criteria임
- Next.js 등의 route/SSR/SSG/build-time behavior처럼 framework build가 현재 변경을 실제로 검증해야 함
- 사용자/승인된 Verification Contract가 package/build/verify를 명시함

단순히 "최종적으로 더 확실해 보인다"는 이유로 `PACKAGE_BUILD`를 실행하지 않는다.

## 3. Ecosystem mapping

### Maven

기본 static/compile 검증은 canonical cached helper로 수행한다.

```bash
python3 /opt/custom-skills/coder/dev-implement-plan/scripts/maven_verification_cached.py \
  --workspace "<approved build root>" \
  --wrapper ./mvnw \
  --mode COMPILE \
  --scope-path "<covered-path>" \
  -- -B -DskipTests test-compile
```

`TARGETED_TEST`는 승인된 selector를 사용한다. `PACKAGE`/`VERIFY` mode는 `PACKAGE_BUILD` 승격 근거가 있을 때만 사용한다.

### Gradle

`STATIC_COMPILE`은 project canonical compile task를 `gradle_verification_cached.py --mode COMPILE`로 실행한다. `TARGETED_TEST`는 동일 helper의 `TARGETED_TEST`를 사용한다. `build`, `assemble`, `bootJar`, `war` 등 artifact task는 `PACKAGE_BUILD` 승격 근거가 있을 때만 실행한다.

### Node / TypeScript

첫 Node command 전에 Frontend Environment Gate를 통과하고 `node_runtime.py` Linux isolated workspace만 사용한다.

명령 선택 우선순위:

```text
package.json의 project canonical check/typecheck/test/build script
→ CI에서 실제 사용하는 동일 목적 script
→ framework/project convention
→ DevKit fallback
```

`STATIC_COMPILE`은 보통 `typecheck` 또는 project `check`이며, `pnpm run build`는 기본 단계가 아니다. `TARGETED_TEST`는 기존 test runner의 affected selector를 사용한다. `PACKAGE_BUILD`에서만 framework/build script를 실행한다.

### 공통 Cheap Gate / pnpm PASS 재사용

검증 직전에는 Project/Workspace/승인 범위를 확인하고, Coder는
`change_summary.py --task-id "<Task ID>" --check-only --include <actual paths>`
로 Scope/EOL/whitespace 검사를 먼저 수행한다. `--check-only`는 기존
검토 인계 정보를 삭제하거나 생성하지 않는다. 검증 후 최종 Scoped Summary로
Coder Handoff를 갱신한다.

Reviewer는 `review_context.py --task-id "<Task ID>" --include <Changed Files>`
를 **빌드/테스트 전에** 실행한다. Task별 Handoff가 없거나 fingerprint가
불일치하면 검증 명령을 실행하지 않고 증적 보완을 요청한다.

Node/TypeScript 검증은 기존 `node_runtime.py` 격리를 유지하되
`node_verification_cached.py`를 통과한다. 명시적 `--scope-path`와
project-canonical pnpm command가 필요하며, source/config/toolchain 및
helper fingerprint가 동일한 PASS만 재사용한다. `pnpm install` 같은
dependency mutation은 이 경로에서 실행할 수 없다. Node 환경/빌드 정책
Gate는 cache hit에서도 생략하지 않는다.

`VERIFICATION_EVIDENCE=REUSED`는 과거 동일 실행의 통과 근거이지
Reviewer가 반드시 확인할 행동 검증 범위까지 자동으로 확장하지 않는다.

## 4. 계획과 실행

Orchestrator는 Standard Flow Verification Plan에 다음을 기록한다.

```text
Verification Level: STATIC_COMPILE | TARGETED_TEST | PACKAGE_BUILD
Verification Escalation Reason: <NONE | 구체 근거>
Project Verification Source: TASK_APPROVED | PROJECT_SCRIPT | CI | BUILD_TOOL_DEFAULT
```

기본 후보는 `STATIC_COMPILE`이다. source evidence/AC가 승격 조건을 만족할 때만 `TARGETED_TEST` 또는 `PACKAGE_BUILD`를 선택한다. 사용자가 이미 더 높은 수준을 승인했다면 Coder가 임의 하향하지 않는다.

Coder는 구현 후 실제 changed scope가 계획보다 높은 수준을 요구하면 같은 Work Unit/승인 범위 안에서 검증 수준만 승격할 수 있다. 새로운 provider/environment/Work Unit 또는 명시적 승인 범위를 추가해야 하면 기존 Gate 규칙에 따라 재승인한다.

## 5. Evidence / reuse

Handoff에는 다음을 남긴다.

```text
Verification Level: <...>
Verification Escalation Reason: <...>
Project Verification Source: <...>
Verification Evidence: EXECUTED | REUSED
Verification Final: true | false
```

동일 request/scope의 PASS evidence는 기존 Maven/Gradle/Node runtime cache 계약에 따라 재사용한다. 높은 level의 PASS가 낮은 level을 실질적으로 포함하더라도 별도 behavior test가 생략된 것으로 오인하지 않는다.

## 6. Blocker 원칙

`PACKAGE_BUILD`가 필요하지 않은 Task에서 package/build를 임의 실행한 뒤 timeout이 발생했다는 이유만으로 Task를 blocked 처리하지 않는다. 실행하지 말았어야 할 상위 수준 검증은 evidence에서 제외하고 승인된 최소 수준의 결과로 판단한다.

반대로 현재 Task가 `PACKAGE_BUILD`를 명시적으로 요구하면 timeout/build failure는 실제 blocker다. 이 정책은 timeout을 숨기거나 실패를 PASS로 바꾸는 규칙이 아니다.
