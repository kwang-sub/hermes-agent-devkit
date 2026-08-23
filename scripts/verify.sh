#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

run_check() {
    local description="$1"
    shift

    printf '[RUN ] %s\n' "$description"
    "$@"
    printf '[PASS] %s\n' "$description"
}

check_mount_template_source() {
    python3 - <<'PYTHON'
from pathlib import Path

source = Path("init-profiles.ps1").read_text(encoding="utf-8-sig")
expected = r'''$Mounts = @(& docker inspect --format '{{range .Mounts}}{{printf "%s|%s\n" .Type .Destination}}{{end}}' $Container)'''

if source.count(expected) != 1:
    raise SystemExit("init-profiles.ps1 must pass the unescaped Docker mount template exactly once")
PYTHON
}

check_powershell_syntax() {
    local powershell=""

    if command -v pwsh >/dev/null 2>&1; then
        powershell="pwsh"
    elif command -v powershell >/dev/null 2>&1; then
        powershell="powershell"
    else
        printf '[SKIP] PowerShell syntax: pwsh/powershell is not installed.\n'
        return 0
    fi

    printf '[RUN ] PowerShell syntax\n'
    "$powershell" -NoLogo -NoProfile -NonInteractive -Command '
        $tokens = $null
        $errors = $null
        $ast = [System.Management.Automation.Language.Parser]::ParseFile(
            (Resolve-Path "init-profiles.ps1"),
            [ref]$tokens,
            [ref]$errors
        )
        if ($errors.Count -ne 0) {
            $errors | ForEach-Object { [Console]::Error.WriteLine($_.Message) }
            exit 1
        }

        $expected = "{{range .Mounts}}{{printf `"%s|%s\n`" .Type .Destination}}{{end}}"
        $templates = $ast.FindAll({
            param($node)
            $node -is [System.Management.Automation.Language.StringConstantExpressionAst] -and
                $node.Value -eq $expected
        }, $true)
        if ($templates.Count -ne 1) {
            [Console]::Error.WriteLine("Expected exactly one valid Docker mount template string.")
            exit 1
        }
    '
    "$powershell" -NoLogo -NoProfile -NonInteractive -File init-profiles.ps1 -EnvSelfTest
    printf '[PASS] PowerShell syntax and .env helper self-test\n'
}

check_docker_compose() {
    if ! command -v docker >/dev/null 2>&1; then
        printf '[SKIP] Docker/Compose validation: docker CLI is not installed.\n'
        return 0
    fi

    if ! docker compose version >/dev/null 2>&1; then
        printf '[SKIP] Docker/Compose validation: Compose plugin is not available.\n'
        return 0
    fi

    if ! docker info >/dev/null 2>&1; then
        printf '[SKIP] Docker/Compose validation: Docker daemon is not available.\n'
        return 0
    fi

    printf '[RUN ] Docker Compose configuration\n'
    if ! docker compose config --quiet >/dev/null 2>&1; then
        printf '[FAIL] Docker Compose configuration is invalid; diagnostic output is suppressed to avoid exposing secrets.\n' >&2
        return 1
    fi
    printf '[PASS] Docker Compose configuration\n'
}

run_check "Context budget and compact policy invariants" \
    python3 scripts/context_budget.py
run_check "Custom skill Python compilation" \
    python3 -m compileall -q custom-skills
run_check "Hermes CLI SyntaxWarning patch and strict compile" \
    python3 scripts/patch_hermes_syntax_warning.py --self-test
run_check "dev-workspace-dispatch regression tests" \
    python3 custom-skills/orchestrator/dev-workspace-dispatch/tests/test_prepare_dispatch.py
run_check "dev-implement-plan workspace verification tests" \
    python3 custom-skills/coder/dev-implement-plan/tests/test_verify_workspace.py
run_check "dev-code-review context tests" \
    python3 custom-skills/reviewer/dev-code-review/tests/test_review_context.py
run_check "dev-review-cycle contract" \
    python3 scripts/check_review_cycle_contract.py
run_check "dev-project-bootstrap metadata preservation tests" \
    python3 custom-skills/orchestrator/dev-project-bootstrap/tests/test_metadata_preservation.py
run_check "dev-project-resolve tests" \
    python3 custom-skills/orchestrator/dev-project-resolve/tests/test_project_resolve.py
run_check "dev-breakdown shell syntax" \
    bash -n custom-skills/orchestrator/dev-breakdown/scripts/collect_project_context.sh
run_check "Environment contract" \
    python3 scripts/check_env_contract.py
run_check "init-profiles Docker mount template" check_mount_template_source
check_powershell_syntax
check_docker_compose

printf '[PASS] Repository verification completed.\n'
