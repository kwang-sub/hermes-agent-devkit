---
name: dev-node-dependencies
description: Node.js 프로젝트의 dependency 추가·삭제·복원에서 package root/manager/version/lockfile 호환성을 먼저 검증하고 Tirith threat-intelligence incomplete를 보안 우회 없이 처리하는 공통 capability skill.
version: 0.1.1
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, node, npm, pnpm, yarn, bun, dependency, package-manager, lockfile, tirith, security, headless]
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
→ dependency mutation 정확히 1회
→ manifest + lockfile 검증
→ project verification
```

- `node_modules`에 package가 존재한다는 이유만으로 설치 완료로 간주하지 않는다.
- `node_modules`에는 있지만 `package.json`/canonical lockfile에 없으면 `EXTRANEOUS_PRESENT`다.
- package manager를 임의로 바꾸지 않는다. `npm`, `pnpm`, `yarn`, `bun`은 lockfile과 `packageManager` evidence로 결정한다.
- monorepo에서는 leaf package root와 상위 package-manager root를 구분한다. leaf에 manager evidence가 없으면 Task workspace 범위 안에서 가장 가까운 상위 `packageManager`/canonical lockfile 경계를 사용한다.
- mixed/conflicting lockfile이면 자동 정리하거나 하나를 삭제하지 않고 BLOCK한다.
- package manager major/version mismatch를 무시하고 설치하지 않는다.
- install 실패를 해결하려고 다른 manager, global install, 임의 `--force`, `--legacy-peer-deps`, lockfile 삭제를 시도하지 않는다.
- Tirith/approval을 끄거나 `TIRITH_ENABLED=0`, YOLO, approval off, fail-open 강제로 우회하지 않는다.

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
STATUS=pass
```

`STATUS=blocked`이면 install command를 실행하지 않는다.

## 2. Package Manager 판정

우선순위:

```text
leaf package root의 packageManager / canonical lockfile
→ 가장 가까운 상위 package-manager root의 packageManager / canonical lockfile
→ BLOCK (Task workspace 안에서 evidence 없음)
```

canonical mapping:

```text
package-lock.json / npm-shrinkwrap.json → npm
pnpm-lock.yaml                          → pnpm
yarn.lock                               → yarn
bun.lock / bun.lockb                    → bun
```

`packageManager`와 같은 경계의 lockfile manager가 다르면 BLOCK한다. 같은 경계에 서로 다른 manager의 lockfile이 2종 이상이면 BLOCK한다.

`packageManager`가 version을 pin하면 현재 실행 가능한 manager version과 일치해야 한다. mismatch면 environment compatibility blocker로 분류하고 dependency mutation을 하지 않는다.

lockfile이 아직 없지만 `packageManager`가 authoritative evidence이면 manager별 기본 lockfile 경로를 `CANONICAL_LOCKFILE`로 예측하고 `LOCKFILE_PRESENT=false`를 출력한다. mutation 성공 후 해당 canonical lockfile이 생성/갱신됐는지 확인한다.

## 3. Node Version Evidence

다음을 evidence로 수집한다.

```text
package.json engines.node
package.json volta.node
상위 package-manager root의 engines.node / volta.node
.nvmrc
.node-version
현재 node --version
```

명시적 major/exact requirement와 현재 Node major가 명백히 충돌하면 `NODE_VERSION_MISMATCH`로 BLOCK한다. 복잡한 semver expression을 helper가 완전히 판정하지 못하면 추측해서 통과시키지 않고 `NODE_REQUIREMENT_CHECK=manual` evidence를 남긴다. 실제 manager가 engine mismatch를 오류로 반환하면 이를 source 문제로 바꾸지 않는다.

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
→ install 진행 가능

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

이 경우 helper는:

```text
one-shot check
→ analysis_incomplete만 존재
→ tirith daemon status
→ 필요 시 daemon start --detach
→ 동일 exact command를 정확히 1회 재검사
```

두 번째 검사가 `allow`이면 진행한다. 두 번째도 incomplete이거나 다른 warn/block finding이 있으면 `approval_required`로 종료한다. `analysis_incomplete`와 실제 finding이 함께 있으면 daemon retry로 실제 finding을 가리지 않고 즉시 `approval_required`다.

보안 의미를 약화하지 않는다.

```text
금지: incomplete를 allow로 재분류
금지: tirith_fail_open 강제
금지: approval/yolo off
금지: package command 문자열 변형으로 scanner 회피
금지: 실제 package install을 helper 내부에서 실행
```

## 6. Dependency Mutation

preflight가 PASS이고 install이 필요할 때만 `INSTALL_COMMAND`를 exact package root에서 **정확히 1회** 실행한다. `PACKAGE_MANAGER_ROOT`가 상위에 있으면 그 경계를 canonical lockfile owner로 유지하며 mutation 뒤 다른 manager/leaf lockfile이 새로 생기지 않았는지 확인한다.

기본 command:

```text
npm  prod → npm install <pkg...>
npm  dev  → npm install --save-dev <pkg...>
pnpm prod → pnpm add <pkg...>
pnpm dev  → pnpm add -D <pkg...>
yarn prod → yarn add <pkg...>
yarn dev  → yarn add -D <pkg...>
bun  prod → bun add <pkg...>
bun  dev  → bun add -d <pkg...>
```

package manager가 peer conflict/engine incompatibility/security finding으로 실패하면 자동 flag 추가로 밀어붙이지 않는다. 원인을 분류한다.

```text
DEPENDENCY_INSTALL_FAILURE_CLASS
- COMPATIBILITY
- SECURITY_INCOMPLETE
- SECURITY_FINDING
- NETWORK_REGISTRY
- MANIFEST_LOCK_CONFLICT
- UNKNOWN
```

동일 실패 command 반복은 금지한다. `SECURITY_INCOMPLETE`만 daemon preflight에서 허용한 단일 재검사 경로를 사용한다.

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
Package Manager: npm | pnpm | yarn | bun
Package Manager Source: packageManager | lockfile
Package Manager Version: ...
Required Package Manager Version: ... | NONE
Node Version: ...
Node Requirement: ... | NONE
Node Requirement Check: pass | manual | blocked
Canonical Lockfile: ...
Lockfile Present Before: true | false
Dependency State Before:
- <package>: <manifest state> / <node_modules state>
Tirith Preflight: allow | approval_required | unavailable
Tirith Retry: none | daemon-recheck-pass | daemon-recheck-fail
Install Command: ... | NOT_REQUIRED
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
- 기존 package manager/lockfile convention을 유지한다.
- `node_modules`는 source of truth가 아니다.
- security incomplete와 실제 security finding을 구분한다.
- headless worker가 interactive approval을 기다리며 같은 command를 반복하지 않는다.
- 보안 scanner 문제를 source compatibility 문제로 오분류하지 않는다.
