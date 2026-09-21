---
name: dev-node-dependencies
description: pnpm 기반 Node.js 프로젝트의 dependency 추가·삭제·복원에서 package.json Node/pnpm runtime 계약과 pnpm-lock.yaml을 검증하고 Tirith threat-intelligence incomplete를 보안 우회 없이 처리하는 공통 capability skill.
version: 0.1.3
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, node, pnpm, dependency, package-manager, lockfile, runtime, tirith, security, headless]
    related_skills: [dev-frontend-feature, dev-typescript-guidelines, dev-nextjs-feature, dev-frontend-test]
    requires_tools: [terminal]
---

# dev-node-dependencies

Node.js dependency 변경의 공통 실행 계약이다. Frontend 전용이 아니며 `package.json` 기반 Node workspace에서 package 추가/삭제/복원 또는 lockfile 갱신이 실제 Task 범위일 때만 사용한다.

## 핵심 원칙

```text
manifest/lock evidence
→ exact package root
→ package-manager root
→ canonical package manager
→ Node/package-manager version compatibility
→ dependency manifest state
→ Tirith security preflight
→ Hermes actual terminal guard
→ dependency mutation 정확히 1회
→ manifest + lockfile 검증
→ project verification
```

- `node_modules`에 package가 존재한다는 이유만으로 설치 완료로 간주하지 않는다.
- `node_modules`에는 있지만 `package.json`/`pnpm-lock.yaml`에 없으면 `EXTRANEOUS_PRESENT`다.
- DevKit의 Node package manager는 **pnpm 하나만 지원**한다. npm/yarn/bun 호환 분기나 자동 판정은 하지 않는다.
- `package.json.devEngines.runtime`은 `name=node`, `version`, `onFail=download`를 선언해야 한다.
- `package.json.devEngines.packageManager`는 `name=pnpm`, `version`, `onFail=download`를 선언해야 한다.
- standalone pnpm이 Node runtime을 프로젝트 선언에 맞춰 설치/선택하며, host의 `node --version`은 source of truth가 아니다.
- canonical lockfile은 항상 `pnpm-lock.yaml`이다.
- install 실패를 해결하려고 다른 manager, global install, 임의 `--force`, `--legacy-peer-deps`, lockfile 삭제를 시도하지 않는다.
- Tirith/approval을 끄거나 `TIRITH_ENABLED=0`, YOLO, approval off, fail-open 강제로 우회하지 않는다.
- preflight 결과는 진단/사전 준비 evidence이며 실제 command 실행 허가는 Hermes terminal guard가 최종 결정한다.
- dependency mutation terminal call은 Hermes 기본 180초 timeout을 상속하지 않고 `timeout=600`을 명시한다. 이 예산은 package-manager mutation에만 적용하며 일반 terminal 명령의 기본 timeout은 변경하지 않는다.

## 1. Dependency Preflight

package mutation 전에 다음 helper를 정확히 1회 실행한다.

```bash
python3 /opt/custom-skills/shared/dev-node-dependencies/scripts/node_dependency_preflight.py \
  --workspace "<Task Workspace>" \
  [--package-root "<relative package root>"] \
  --dependency-type "prod|dev" \
  --package "<package-or-spec>" \
  [--package "<package-or-spec>" ...]
```

여러 `package.json`이 존재하고 `--package-root` 없이 하나로 확정할 수 없으면 BLOCK한다. 임의로 root package를 선택하지 않는다. 탐색은 bounded walk이며 `.git`, `.hermes`, `.worktrees`, `node_modules`, `.next`, build/dist/coverage 영역을 순회하지 않는다.

PASS 출력의 최소 evidence:

```text
PACKAGE_ROOT
PACKAGE_MANAGER_ROOT
PACKAGE_MANAGER
PACKAGE_MANAGER_SOURCE
PACKAGE_MANAGER_VERSION
PACKAGE_MANAGER_REQUIRED_VERSION
NODE_VERSION
NODE_REQUIREMENT
CANONICAL_LOCKFILE
LOCKFILE_PRESENT
DEPENDENCY_<N>_MANIFEST_STATE
DEPENDENCY_<N>_NODE_MODULES_STATE
INSTALL_REQUIRED
INSTALL_COMMAND
INSTALL_TIMEOUT_SECONDS
STATUS=pass
```

`STATUS=blocked`이면 install command를 실행하지 않는다.

## 2. pnpm / Node Runtime 계약

Node 프로젝트는 별도 Hermes 전용 버전 파일 대신 기존 `package.json`을 source of truth로 사용한다.

```json
{
  "devEngines": {
    "runtime": {
      "name": "node",
      "version": "^24.11.0",
      "onFail": "download"
    },
    "packageManager": {
      "name": "pnpm",
      "version": ">=12 <13",
      "onFail": "download"
    }
  }
}
```

규칙:

- `devEngines.runtime`이 없거나 Node가 아니면 BLOCK한다.
- `devEngines.packageManager`가 없거나 pnpm이 아니면 BLOCK한다.
- npm/yarn/bun lockfile 또는 manager를 fallback으로 선택하지 않는다.
- `pnpm install`이 runtime version range를 resolve하고 exact runtime/checksum을 `pnpm-lock.yaml`에 기록하도록 맡긴다.
- DevKit의 standalone pnpm은 bootstrap 역할만 하며 프로젝트의 Node runtime은 이미지에 고정하지 않는다.
- 검증 명령은 가능한 한 `pnpm run <script>` / `pnpm exec <tool>` 형태로 실행하여 project runtime pin을 따른다.
- Node/pnpm cache와 runtime state는 `/opt/data/node` 아래 persistent volume을 사용한다.
- Next.js 프로젝트는 `NEXT_DIST_DIR=.next-hermes`를 받아 `.next`와 Hermes build 산출물을 분리하도록 project config를 구성한다.

## 4. node_modules / Manifest 계약

상태:

```text
DECLARED_PROD
DECLARED_DEV
DECLARED_PEER
DECLARED_OPTIONAL
ABSENT
```

`node_modules` 상태:

```text
PRESENT_DECLARED
EXTRANEOUS_PRESENT
ABSENT
```

예를 들어 Supabase package가 `node_modules`에만 존재하면:

```text
MANIFEST_STATE=ABSENT
NODE_MODULES_STATE=EXTRANEOUS_PRESENT
INSTALL_REQUIRED=true
```

이다. source에서 import가 된다는 이유만으로 manifest/lock 반영을 생략하지 않는다.

## 5. Tirith / Headless Security Preflight

Node package mutation은 네트워크 package metadata를 조회하므로 실제 install 전에 exact `INSTALL_COMMAND`를 대상으로 다음 helper를 실행한다.

```bash
python3 /opt/custom-skills/shared/dev-node-dependencies/scripts/tirith_package_preflight.py \
  --command "<INSTALL_COMMAND>"
```

상태:

```text
TIRITH_PREFLIGHT=allow
→ actual terminal guard까지 진행 가능한 사전 evidence. guard bypass나 최종 승인 의미가 아님

TIRITH_PREFLIGHT=approval_required
→ 실제 positive warn/block finding 또는 daemon 재검사 후에도 불완전. headless worker에서 install 실행 금지, Kanban BLOCK

TIRITH_PREFLIGHT=unavailable
→ preflight binary를 찾지 못함. 실제 Hermes terminal guard를 그대로 사용하되 보안 우회 금지
```

### `analysis_incomplete` 처리

Tirith가 다음처럼 실제 악성 verdict가 아니라 runtime threat-intelligence 조회 불완전을 반환할 수 있다.

```text
rule_id=analysis_incomplete
Package threat intelligence could not be completed
```

preflight helper는 사전 진단/daemon warm-up 목적으로 다음을 수행한다.

```text
one-shot check
→ analysis_incomplete만 존재
→ tirith daemon status
→ 필요 시 daemon start --detach
→ 동일 exact command를 정확히 1회 재검사
```

두 번째 검사가 `allow`이면 actual terminal guard까지 진행한다. 두 번째도 incomplete이거나 다른 warn/block finding이 있으면 `approval_required`로 종료한다. `analysis_incomplete`와 실제 finding이 함께 있으면 daemon retry로 실제 finding을 가리지 않고 즉시 `approval_required`다.

### Hermes actual terminal guard parity

실제 `npm install` 실행 직전의 Hermes guard가 최종 authority다. DevKit runtime patch는 guard의 Tirith subprocess가 terminal child와 같은 routed-profile state를 보도록 다음 계약을 유지한다.

```text
active profile ContextVar
→ HERMES_HOME subprocess env bridge
→ Hermes subprocess HOME contract 적용
→ tirith check
```

따라서 Coder preflight가 보는 daemon/state와 actual guard가 보는 daemon/state가 profile별로 일치해야 한다.

actual guard에서 결과가 오직 `analysis_incomplete`인 경우에만:

```text
tirith check
→ pure analysis_incomplete
→ 같은 profile env로 daemon status
→ 필요 시 daemon start --detach
→ 같은 profile env + 같은 exact command로 정확히 1회 재검사
```

한다. 실제 malware/positive warn/block finding은 daemon 재검사 대상으로 바꾸지 않으며 기존 approval/BLOCK 의미를 그대로 유지한다. daemon 준비/재검사 자체가 실패하면 최초 verdict를 보존하고 fail-open으로 재분류하지 않는다.

보안 의미를 약화하지 않는다.

```text
금지: preflight allow를 actual guard bypass token으로 사용
금지: incomplete를 allow로 재분류
금지: tirith_fail_open 강제
금지: approval/yolo off
금지: package command 문자열 변형으로 scanner 회피
금지: 실제 package install을 helper 내부에서 실행
```

## 6. Dependency Mutation

preflight가 PASS이고 install이 필요할 때만 `INSTALL_COMMAND`를 exact package root에서 **정확히 1회** 실행한다. 이 terminal tool 호출에는 **`timeout=600`**을 명시한다. `PACKAGE_MANAGER_ROOT`가 상위에 있으면 그 경계를 canonical lockfile owner로 유지하며 mutation 뒤 다른 manager/leaf lockfile이 새로 생기지 않았는지 확인한다.

실행 계약:

```text
command: <INSTALL_COMMAND>        # exact package-manager command
workdir: <PACKAGE_ROOT>
timeout: 600
background: false
```

Hermes actual terminal guard가 exact package-manager command를 검사해야 하므로 `timeout 600 npm install ...`처럼 shell `timeout` wrapper로 command 문자열을 감싸지 않는다. terminal tool의 호출별 `timeout` 필드를 사용한다. 600초는 현재 foreground timeout 상한 안에서 사용하며, install이 더 빨리 끝나면 즉시 반환된다.

600초 안에 완료되지 않아 timeout/`exit 124`로 종료되면 설치 성공으로 간주하지 않는다. `package.json`/canonical lockfile이 반영되지 않고 `node_modules`만 일부 생성된 상태도 실패다. 동일 exact command를 자동 반복하지 않고 `DEPENDENCY_INSTALL_FAILURE_CLASS=TIMEOUT`으로 BLOCK한 뒤 부분 설치 정리와 재실행 승인을 요구한다.

기본 command:

```text
pnpm prod → pnpm add <pkg...>
pnpm dev  → pnpm add -D <pkg...>
```

package manager가 peer conflict/engine incompatibility/security finding으로 실패하면 자동 flag 추가로 밀어붙이지 않는다. 원인을 분류한다.

```text
DEPENDENCY_INSTALL_FAILURE_CLASS
- TIMEOUT
- COMPATIBILITY
- SECURITY_INCOMPLETE
- SECURITY_FINDING
- NETWORK_REGISTRY
- MANIFEST_LOCK_CONFLICT
- UNKNOWN
```

동일 실패 command 반복은 금지한다. `SECURITY_INCOMPLETE`는 actual guard의 profile-scoped daemon 단일 재검사 이후에도 incomplete일 때만 사용한다.

## 7. Mutation Verification

새 dependency 추가/변경이면 최소 다음을 확인한다.

```text
leaf package.json에 의도한 section 반영
CANONICAL_LOCKFILE 생성/갱신
다른 manager 또는 leaf 전용 lockfile이 의도치 않게 신규 생성되지 않음
package manager의 install/resolve 결과 성공
기존 project typecheck/lint/test/build 중 영향 범위 검증
```

`node_modules`만 바뀌고 manifest/lockfile이 그대로면 완료로 간주하지 않는다.

복원 작업에서 manifest/lockfile이 이미 authoritative하고 install tree만 없는 경우에는 manager의 frozen/CI restore 경로를 기존 project convention에 맞춰 사용한다. package 추가 Task와 restore Task를 혼동하지 않는다.

## 8. Handoff Evidence

```text
Node Dependency Preflight: PASS | BLOCKED
Package Root: ...
Package Manager Root: ...
Package Manager: pnpm
Package Manager Source: package.json devEngines.packageManager
Bootstrap pnpm Version: ...
Required pnpm Version: ...
Node Version: managed-by-pnpm
Node Requirement: ...
Node Requirement Check: pnpm-managed
Canonical Lockfile: ...
Lockfile Present Before: true | false
Dependency State Before:
- <package>: <manifest state> / <node_modules state>
Tirith Preflight: allow | approval_required | unavailable
Tirith Preflight Retry: none | daemon-recheck-pass | daemon-recheck-fail
Tirith Actual Guard: allow | approval_required | block | not_run
Tirith Guard Profile Parity: pass | blocked | not_observed
Install Command: ... | NOT_REQUIRED
Install Timeout Seconds: 600 | NOT_REQUIRED
Install Result: PASS | NOT_RUN | BLOCKED
Manifest Updated: true | false | not_required
Lockfile Updated: true | false | not_required
Verification:
- ...
Residual Risk:
- ...
```

## 불변식

- dependency 변경이 아닌 Task에서 편의상 package를 추가하지 않는다.
- Task에서 승인되지 않은 library/framework 교체는 Standard Flow Requirement Delta 대상이다.
- package manager/lockfile은 pnpm + pnpm-lock.yaml 단일 convention을 유지한다.
- `node_modules`는 source of truth가 아니다.
- security incomplete와 실제 security finding을 구분한다.
- preflight와 actual guard의 profile state를 서로 다른 HOME/HERMES_HOME으로 실행하지 않는다.
- headless worker가 interactive approval을 기다리며 같은 command를 반복하지 않는다.
- dependency mutation은 terminal tool `timeout=600`을 사용하고 일반 terminal 기본 timeout은 전역 변경하지 않는다.
- shell `timeout` wrapper로 package-manager command를 감싸 Tirith actual guard의 exact-command 의미를 바꾸지 않는다.
- 보안 scanner 문제를 source compatibility 문제로 오분류하지 않는다.
