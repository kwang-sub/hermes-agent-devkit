#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

BASE_IMAGE="${HERMES_BASE_IMAGE:-nousresearch/hermes-agent:latest}"
IMAGE_NAME="${HERMES_COMPAT_IMAGE:-hermes-devkit:latest-compat}"

cleanup() {
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

printf '[RUN ] Latest Hermes patched runtime smoke\n'
docker run --rm \
    --entrypoint /bin/sh \
    --mount "type=bind,source=$REPO_ROOT/custom-skills,target=/opt/custom-skills,readonly" \
    --mount "type=bind,source=$REPO_ROOT/shared,target=/opt/data/shared,readonly" \
    "$IMAGE_NAME" \
    -ceu '
        test -x /opt/hermes/.venv/bin/hermes
        /opt/hermes/.venv/bin/hermes --help >/dev/null

        test -f /opt/hermes/hermes_cli/devkit_session_affinity.py
        test -f /opt/hermes/tools/kanban_tools.py
        grep -q "def _devkit_run_flow_model_transition" /opt/hermes/tools/kanban_tools.py
        grep -q "MODEL_POLICY_SNAPSHOT_V1" /opt/hermes/tools/kanban_tools.py

        /opt/hermes/.venv/bin/python -m py_compile \
            /opt/hermes/tools/kanban_tools.py \
            /opt/hermes/hermes_cli/devkit_session_affinity.py

        test -f /opt/custom-skills/shared/dev-api-spec/SKILL.md
        test -f /opt/custom-skills/shared/dev-api-contract/SKILL.md
        test -f /opt/custom-skills/shared/dev-api-docs/SKILL.md
        test -f /opt/custom-skills/shared/dev-kotlin-guidelines/SKILL.md
        test -f /opt/data/shared/references/approval-gate-rules.md
        test -f /opt/data/shared/scripts/flow_model_policy.py
    '

printf '[PASS] Latest Hermes base image is compatible with the DevKit upstream patch stage.\n'
