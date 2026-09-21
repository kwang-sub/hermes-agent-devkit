#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

BASE_IMAGE="${HERMES_BASE_IMAGE:-nousresearch/hermes-agent:latest}"
IMAGE_NAME="${HERMES_COMPAT_IMAGE:-hermes-devkit:latest-compat}"
CONTAINER_NAME="${HERMES_COMPAT_CONTAINER:-hermes-devkit-latest-compat}"
DATA_VOLUME="${HERMES_COMPAT_DATA_VOLUME:-hermes-devkit-latest-compat-data}"

cleanup() {
    docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
    docker volume rm -f "$DATA_VOLUME" >/dev/null 2>&1 || true
    docker image rm -f "$IMAGE_NAME" >/dev/null 2>&1 || true
}
trap cleanup EXIT

printf '[RUN ] Latest Hermes compatibility build\n'
printf 'BASE_IMAGE=%s\n' "$BASE_IMAGE"

docker build \
    --pull \
    --build-arg "HERMES_BASE_IMAGE=$BASE_IMAGE" \
    --target hermes-upstream-patched \
    --tag "$IMAGE_NAME" \
    .

printf '[RUN ] Pinned Git/runtime compatibility build\n'
docker build \
    --build-arg "HERMES_BASE_IMAGE=$BASE_IMAGE" \
    --target hermes-devkit-runtime \
    --tag "$IMAGE_NAME" \
    .

printf '[RUN ] Latest Hermes patched runtime smoke\n'
docker run --rm \
    --entrypoint /bin/sh \
    --mount "type=bind,source=$REPO_ROOT/custom-skills,target=/opt/custom-skills,readonly" \
    --mount "type=bind,source=$REPO_ROOT/shared,target=/opt/data/shared,readonly" \
    --mount "type=bind,source=$REPO_ROOT/scripts,target=/opt/devkit-tests,readonly" \
    "$IMAGE_NAME" \
    -ceu '
        test -x /opt/hermes/.venv/bin/hermes
        /opt/hermes/.venv/bin/hermes --help >/dev/null

        test "$(/usr/local/bin/git --version)" = "git version 2.55.0"
        test "$(/usr/local/bin/git config --system --bool --get worktree.useRelativePaths)" = "true"
        test "$(/usr/local/bin/pnpm --version)" = "12.5.1"

        runtime_smoke=/tmp/devkit-pnpm-runtime-smoke
        runtime_home=/tmp/devkit-pnpm-home
        mkdir -p "$runtime_smoke" "$runtime_home"
        cat > "$runtime_smoke/package.json" <<"JSON"
{
  "name": "devkit-pnpm-runtime-smoke",
  "private": true,
  "scripts": {
    "runtime-smoke": "node --version"
  },
  "devEngines": {
    "runtime": {
      "name": "node",
      "version": "22.23.2",
      "onFail": "download"
    },
    "packageManager": {
      "name": "pnpm",
      "version": ">=12.0.0 <13.0.0",
      "onFail": "download"
    }
  }
}
JSON
        (
          cd "$runtime_smoke"
          export PNPM_HOME="$runtime_home"
          export PATH="$PNPM_HOME:/usr/local/bin:$PATH"
          /usr/local/bin/pnpm install --lockfile-only
          test -f pnpm-lock.yaml
          runtime_version="$(/usr/local/bin/pnpm --silent run runtime-smoke | tail -n 1)"
          test "$runtime_version" = "v22.23.2"
        )
        rm -rf "$runtime_smoke" "$runtime_home"

        test -f /opt/hermes/hermes_cli/devkit_session_affinity.py
        test -f /opt/hermes/tools/kanban_tools.py
        grep -q "def _devkit_run_flow_model_transition" /opt/hermes/tools/kanban_tools.py
        grep -q "MODEL_POLICY_SNAPSHOT_V1" /opt/hermes/tools/kanban_tools.py

        grep -q "DEVKIT_SLASH_SUGGEST_V1" /opt/hermes/agent/skill_commands.py
        grep -q "DEVKIT_SLASH_SUGGEST_V1" /opt/hermes/hermes_cli/commands_completion.py
        grep -q "DEVKIT_SLASH_SUGGEST_V1" /opt/hermes/tui_gateway/methods_tools.py
        grep -q "DEVKIT_TIRITH_PROFILE_GUARD_V1" /opt/hermes/tools/tirith_security.py
        test -f /opt/data/shared/references/skill-slash-suggest-policy.json

        /opt/hermes/.venv/bin/python -m py_compile \
            /opt/hermes/tools/tirith_security.py \
            /opt/hermes/tools/kanban_tools.py \
            /opt/hermes/hermes_cli/devkit_session_affinity.py \
            /opt/hermes/agent/skill_commands.py \
            /opt/hermes/hermes_cli/commands_completion.py \
            /opt/hermes/tui_gateway/methods_tools.py

        /opt/hermes/.venv/bin/python - <<"PY"
import os
from hermes_constants import reset_hermes_home_override, set_hermes_home_override
from tools.tirith_security import _devkit_only_analysis_incomplete, _devkit_tirith_subprocess_env

before_home = os.environ.get("HOME")
before_hermes_home = os.environ.get("HERMES_HOME")
token = set_hermes_home_override("/tmp/devkit-tirith-profile")
try:
    env = _devkit_tirith_subprocess_env()
    assert env.get("HERMES_HOME") == "/tmp/devkit-tirith-profile", env
    assert env.get("HOME"), env
    assert os.environ.get("HOME") == before_home
    assert os.environ.get("HERMES_HOME") == before_hermes_home
    assert _devkit_only_analysis_incomplete([{"rule_id": "analysis_incomplete"}])
    assert not _devkit_only_analysis_incomplete([{"rule_id": "malware_package"}])
finally:
    reset_hermes_home_override(token)
PY

        test -f /opt/custom-skills/shared/dev-api-spec/SKILL.md
        test -f /opt/custom-skills/shared/dev-api-contract/SKILL.md
        test -f /opt/custom-skills/shared/dev-api-docs/SKILL.md
        test -f /opt/custom-skills/shared/dev-official-docs-context/SKILL.md
        test -f /opt/custom-skills/shared/dev-official-docs-context/scripts/context7_docs.py
        test -f /opt/custom-skills/shared/dev-official-docs-context/scripts/detect_dependency_versions.py
        /opt/hermes/.venv/bin/python /opt/custom-skills/shared/dev-official-docs-context/scripts/context7_docs.py --self-test
        test -x /opt/devkit/bin/devkit_kanban_notifier.py
        /opt/hermes/.venv/bin/python /opt/devkit/bin/devkit_kanban_notifier.py --self-test
        /opt/hermes/.venv/bin/hermes send --help >/dev/null
        test -x /opt/devkit/svscan/devkit-notifier/run
        test -x /etc/cont-init.d/019-devkit-kanban-notifier-policy
        test ! -e /etc/s6-overlay/s6-rc.d/devkit-notifier
        test -f /opt/custom-skills/shared/dev-java-guidelines/SKILL.md
        test -f /opt/custom-skills/shared/dev-java-guidelines/references/official-java-practices.md
        test -f /opt/custom-skills/shared/dev-kotlin-guidelines/SKILL.md
        test -f /opt/custom-skills/shared/dev-spring-guidelines/SKILL.md
        test -f /opt/custom-skills/shared/dev-spring-guidelines/references/official-spring-practices.md
        test -f /opt/custom-skills/shared/dev-spring-feature/SKILL.md
        test -f /opt/custom-skills/shared/dev-spring-data/SKILL.md
        test -f /opt/custom-skills/shared/dev-spring-test/SKILL.md
        test -f /opt/custom-skills/shared/dev-typescript-guidelines/SKILL.md
        test -f /opt/custom-skills/shared/dev-typescript-guidelines/references/official-typescript-practices.md
        test -f /opt/custom-skills/shared/dev-frontend-guidelines/SKILL.md
        test -f /opt/custom-skills/shared/dev-frontend-guidelines/references/official-react-practices.md
        test -f /opt/custom-skills/shared/dev-nextjs-feature/SKILL.md
        test -f /opt/custom-skills/shared/dev-nextjs-feature/references/official-nextjs-practices.md
        test -f /opt/custom-skills/shared/dev-node-dependencies/SKILL.md
        test -f /opt/data/shared/references/approval-gate-rules.md
        test -f /opt/data/shared/scripts/flow_model_policy.py
    '

printf '[RUN ] Latest Hermes live s6 notifier smoke\n'
docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
docker volume rm -f "$DATA_VOLUME" >/dev/null 2>&1 || true
docker volume create "$DATA_VOLUME" >/dev/null

docker run --rm \
    --entrypoint /bin/sh \
    --mount "type=volume,source=$DATA_VOLUME,target=/opt/data" \
    "$IMAGE_NAME" \
    -ceu 'chown -R "$(id -u hermes):$(id -g hermes)" /opt/data'

docker run -d \
    --name "$CONTAINER_NAME" \
    --mount "type=volume,source=$DATA_VOLUME,target=/opt/data" \
    -e HERMES_KANBAN_NOTIFY_ENABLED=false \
    "$IMAGE_NAME" \
    sleep infinity >/dev/null

ready=0
for _ in $(seq 1 60); do
    if docker exec "$CONTAINER_NAME" /command/s6-svstat -o up /run/service/devkit-notifier 2>/dev/null | grep -qx true; then
        ready=1
        break
    fi
    sleep 0.5
done

if [ "$ready" -ne 1 ]; then
    docker logs "$CONTAINER_NAME" >&2 || true
    docker exec "$CONTAINER_NAME" ls -la /run/service >&2 || true
    exit 1
fi

docker exec "$CONTAINER_NAME" test -x /run/service/devkit-notifier/run
test "$(docker exec "$CONTAINER_NAME" cat /proc/1/comm | tr -d '\r')" = "s6-svscan"
docker exec --user hermes "$CONTAINER_NAME" \
    /opt/hermes/.venv/bin/python /opt/devkit/bin/devkit_kanban_notifier.py --self-test

printf '[PASS] Latest Hermes base image, pinned Git/pnpm bootstrap, project Node runtime, DevKit patches, and live dynamic notifier supervision are compatible.\n'
