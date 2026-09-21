---
name: dev-node-dependencies
description: Node.js 프로젝트의 pnpm dependency 추가·삭제·복원에서 package.json toolchain/runtime 계약과 pnpm-lock.yaml을 검증하고 Tirith security preflight를 적용하는 공통 capability skill.
version: 0.2.0
author: local
platforms: [linux]
metadata:
  hermes:
    tags: [dev, node, pnpm, dependency, package-manager, lockfile, runtime, tirith, security, headless]
    related_skills: [dev-frontend-feature, dev-typescript-guidelines, dev-nextjs-feature, dev-frontend-test]
    requires_tools: [terminal]
---

# dev-node-dependencies

Hermes Agent DevKit의 Node package manager는 **pnpm 하나만 사용한다**. Node runtime과 pnpm version의 source of truth는 별도 Hermes 설정 파일이 아니라 프로젝트의 기존 필수 manifest인 `package.json`이다.

## Canonical Toolchain Contract

Node 프로젝트는 다음 계약을 가진다.

```json
{
  "devEngines": {
    "runtime": {
      "name": "node",
      "version": "<project Node version/range>",
      "onFail": "download"
    },
    "packageManager": {
      "name": "pnpm",
      "version": "<project pnpm version/range>",
      "onFail": "download"
    }
  }
}
```

역할:

```text
package.json devEngines.runtime
→ 프로젝트가 실제 개발/검증에서 사용할 Node runtime

package.json devEngines.packageManager
→ 프로젝트가 사용할 pnpm version

pnpm-lock.yaml
→ dependency graph + pnpm/runtime resolution 재현성
```

pnpm standalone은 DevKit image에 존재하고 Node는 image에 고정하지 않는다. `pnpm install`이 `devEngines.runtime`을 해석해 필요한 Node를 내려받고, resolved runtime/version checksum을 lockfile에 기록한다.

추가 Node version file을 표준으로 만들지 않는다.

```text
.nvmrc        → DevKit canonical source 아님
.node-version → DevKit canonical source 아님
volta.node    → DevKit canonical source 아님
```

## pnpm-only Migration Gate

다음 lockfile이 존재하면 호환 실행하지 않고 migration blocker로 처리한다.

```text
package-lock.json
npm-shrinkwrap.json
yarn.lock
bun.lock
bun.lockb
```

Node 프로젝트의 canonical lockfile은 오직:

```text
pnpm-lock.yaml
```

이다.

기존 npm/yarn/bun 프로젝트를 Agent가 임의로 병행 지원하지 않는다. 프로젝트 migration Task에서 `package.json` toolchain 선언과 `pnpm-lock.yaml`을 만든 뒤 정상 Node workflow로 진입한다.

## Dependency Preflight

package mutation 전에 다음 helper를 정확히 1회 실행한다.

```bash
python3 /opt/custom-skills/shared/dev-node-dependencies/scripts/node_dependency_preflight.py \
  --workspace "<Task Workspace>" \
  [--package-root "<relative package root>"] \
  --dependency-type "prod|dev" \
  --package "<package-or-spec>" \
  [--package "<package-or-spec>" ...]
```

검증 범위:

```text
package root
→ nearest pnpm toolchain root
→ package.json devEngines.runtime
→ package.json devEngines.packageManager
→ pnpm standalone availability
→ legacy lockfile absence
→ pnpm-lock.yaml
→ manifest/node_modules state
→ exact pnpm mutation command
```

PASS evidence:

```text
PACKAGE_ROOT
PACKAGE_MANAGER_ROOT
PACKAGE_MANAGER=pnpm
PACKAGE_MANAGER_SOURCE=package.json devEngines.packageManager
PACKAGE_MANAGER_VERSION
PACKAGE_MANAGER_REQUIRED_VERSION
NODE_VERSION=managed-by-pnpm
NODE_REQUIREMENT
NODE_REQUIREMENT_SOURCE=package.json devEngines.runtime
CANONICAL_LOCKFILE
LOCKFILE_PRESENT
DEPENDENCY_<N>_MANIFEST_STATE
DEPENDENCY_<N>_NODE_MODULES_STATE
INSTALL_REQUIRED
RESTORE_REQUIRED
INSTALL_COMMAND
RESTORE_COMMAND
INSTALL_TIMEOUT_SECONDS
STATUS=pass
```

`STATUS=blocked`이면 dependency command를 실행하지 않는다.

## Manifest / node_modules Contract

`node_modules`는 source of truth가 아니다.

상태:

```text
DECLARED_PROD
DECLARED_DEV
DECLARED_PEER
DECLARED_OPTIONAL
ABSENT
```

node_modules 상태:

```text
PRESENT_DECLARED
EXTRANEOUS_PRESENT
ABSENT
```

예:

```text
package.json에 없음
node_modules에는 존재
→ EXTRANEOUS_PRESENT
→ install 완료로 간주하지 않음
```

## Tirith Security Preflight

Node package mutation은 실제 exact command를 대상으로 security preflight를 수행한다.

```bash
python3 /opt/custom-skills/shared/dev-node-dependencies/scripts/tirith_package_preflight.py \
  --command "<exact pnpm command>"
```

상태:

```text
TIRITH_PREFLIGHT=allow
→ actual terminal guard까지 진행

TIRITH_PREFLIGHT=approval_required
→ headless worker에서 실행 금지, Kanban BLOCK

TIRITH_PREFLIGHT=unavailable
→ actual Hermes terminal guard를 그대로 사용
```

`analysis_incomplete`만 존재할 때만 기존 bounded daemon recheck 계약을 적용한다. 실제 malware/warn/block finding은 retry로 가리지 않는다.

금지:

```text
TIRITH_ENABLED=0
approval/yolo bypass
fail-open 강제
preflight allow를 actual guard bypass token으로 사용
command 문자열 변형으로 scanner 회피
```

actual Hermes terminal guard가 최종 authority다.

## Dependency Mutation

preflight PASS + Tirith 허용 이후 exact package manager command를 **정확히 1회** 실행한다.

```text
prod → pnpm add <pkg...>
dev  → pnpm add -D <pkg...>
```

terminal timeout:

```text
timeout=600
```

shell `timeout` wrapper를 사용하지 않는다.

timeout/exit 124이면 자동 반복하지 않고:

```text
DEPENDENCY_INSTALL_FAILURE_CLASS=TIMEOUT
```

으로 BLOCK한다.

기존 dependency tree 복원은:

```text
pnpm-lock.yaml 있음
→ pnpm install --frozen-lockfile

초기 migration/lock 생성 Task
→ pnpm install
```

을 사용한다.

## Hermes Runtime Isolation

test/lint/typecheck/build 같은 검증은 dependency mutation과 분리한다.

```bash
python3 /opt/custom-skills/shared/dev-node-dependencies/scripts/node_runtime.py \
  --workspace "<Task Workspace>" \
  [--cwd "<package root>"] \
  -- pnpm run <script>
```

runtime helper는:

```text
pnpm store/cache → /opt/data/node
TMP/XDG cache    → /opt/data/node
workspace command → lock으로 직렬화
HERMES_NEXT_DIST_DIR=.next-hermes
```

를 적용한다.

Next.js 프로젝트는 `next.config.*`에서 다음 convention을 사용한다.

```ts
distDir: process.env.HERMES_NEXT_DIST_DIR || ".next"
```

따라서 Windows host의 `next dev`는 기본 `.next`를 사용하고 Hermes build/typecheck는 `.next-hermes`를 사용해 generated type/output 충돌을 피한다. `.next-hermes/`는 반드시 `.gitignore` 대상이다.

## Mutation Verification

dependency 변경 후 최소 확인:

```text
package.json 반영
pnpm-lock.yaml 생성/갱신
legacy package-manager lockfile 없음
pnpm install/resolve 성공
project test/lint/typecheck/build 영향 범위 검증
```

## Handoff Evidence

```text
Node Dependency Preflight: PASS | BLOCKED
Package Root: ...
Package Manager Root: ...
Package Manager: pnpm
Package Manager Version: ...
Required Package Manager Version: ...
Node Runtime: managed-by-pnpm
Node Requirement: ...
Canonical Lockfile: .../pnpm-lock.yaml
Lockfile Present Before: true | false
Tirith Preflight: allow | approval_required | unavailable
Tirith Actual Guard: allow | approval_required | block | not_run
Install Command: ... | NOT_REQUIRED
Restore Command: ... | NOT_REQUIRED
Install Timeout Seconds: 600 | NOT_REQUIRED
Manifest Updated: true | false | not_required
Lockfile Updated: true | false | not_required
Verification:
- ...
Residual Risk:
- ...
```

## 불변식

- Node 프로젝트는 pnpm만 사용한다.
- `package.json`이 Node/pnpm toolchain source of truth다.
- `pnpm-lock.yaml`만 canonical lockfile로 사용한다.
- `node_modules`는 source of truth가 아니다.
- dependency mutation은 Tirith actual guard를 우회하지 않는다.
- 동일 실패 command를 자동 반복하지 않는다.
- 별도 Hermes 전용 Node version 설정 파일을 만들지 않는다.
