# Risk-based Verification Level Policy

`VERIFICATION_LEVEL_POLICY_V1`은 단일 개발 세션의 위험 기반 검증 기준이다. 사용자 요구 → 프로젝트의 실제 script/CI/AGENTS → 아래 최소 검증 순서로 선택한다. 역할별 Handoff·Kanban ID·Worker 승인은 필요하지 않다.

## 검증 수준

| 수준 | 목적 | 승격 근거 |
|---|---|---|
| STATIC_COMPILE | 현재 toolchain에서 source/test 정합성 확인 | 코드 변경의 최소 기준 |
| TARGETED_TEST | 동작·API·보안·회귀·DB 의미 검증 | 버그 수정, 기존 관련 테스트, 명시된 완료 기준 |
| PACKAGE_BUILD | 배포 산출물·프레임워크 build-time 동작 검증 | build/dependency/resource/bundler/SSR/SSG/배포 변경 또는 사용자 요구 |

compile 성공을 behavior test 성공으로 보고하지 않는다. 적합한 테스트가 없으면 확인 못한 동작과 잔여 위험을 설명한다. 단순히 더 확실해 보인다는 이유로 전체 패키징을 반복하지 않는다. 명시적으로 요구된 package/build 실패는 실제 실패이며, 임의 실행한 불필요한 상위 단계의 실패로 필수 검증 결과를 덮지 않는다.

## 역할 독립 JVM 실행 경로

배포 위치: `/opt/devkit/scripts/verification/`. 저장소 내 대응 위치: `scripts/verification/`. 이미지가 관리하는 `hermes-java`/`hermes-maven` launcher를 사용한다. Maven 배포본·repository·build-output, Gradle cache/output/project-cache/workspace lock은 기존 `/opt/data` 격리 정책을 유지한다. Windows source를 덮어쓰거나 raw mvn/gradlew/host JDK로 우회하지 않는다.

```bash
python3 /opt/devkit/scripts/verification/maven_verification_cached.py \
  --workspace "<build-root>" --wrapper ./mvnw --mode COMPILE \
  --scope-path "<covered-source-or-test>" -- -B -DskipTests test-compile

python3 /opt/devkit/scripts/verification/gradle_verification_cached.py \
  --workspace "<build-root>" --mode TARGETED_TEST --test "<test-selector>" \
  --scope-path "<covered-source-or-test>"
```

세부 timeout/캐시/실패 분류는 실행 helper가 소유한다. `READY`는 toolchain 준비 상태이며 실제 테스트 PASS가 아니다. 동일 명령의 실패를 무제한 재시도하지 않는다. Maven PACKAGE/VERIFY 또는 Gradle artifact task는 PACKAGE_BUILD 근거가 있을 때만 수행한다.

## Node / TypeScript

`dev-node-dependencies`의 environment/build policy를 통과한 후 `node_runtime.py`의 Linux 격리 workspace를 사용한다. `package.json`의 typecheck/check/test/build와 기존 테스트 도구를 우선한다. `node_verification_cached.py`에 검증 범위와 canonical pnpm command를 넘긴다. dependency 변경은 검증 캐시 경로에서 수행하지 않는다. PACKAGE_BUILD는 항상 fresh 검증한다.

## 증거의 유효 범위

변경 범위, toolchain/build 설정 및 검증 명령의 fingerprint가 동일한 PASS만 재사용한다. 코드가 실행 도중 변경되었으면 결과를 무효화한다. FAIL/BLOCKED는 재사용하지 않는다. 외부 서비스·시간·환경 의존 테스트에는 `--no-reuse`를 사용한다. 더 높은 수준의 성공이 실제로 실행하지 않은 동작 테스트를 대신하지 않는다.

보고에는 `Verification Level`, 승격 이유, 실제 실행 명령(비밀값 제거), `EXECUTED | REUSED`, 결과와 미실행 사유를 기록한다. 자체 검토 결과를 독립 검증이라고 표현하지 않는다.
