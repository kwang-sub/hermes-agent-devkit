#requires -Version 5.1

param(
    [string]$Container = "hermes-dev"
)

$ErrorActionPreference = "Stop"

function Invoke-DockerCheck {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,
        [Parameter(Mandatory = $true)]
        [string[]]$DockerArgs
    )

    & docker @DockerArgs
    if ($LASTEXITCODE -ne 0) {
        throw "[FAIL] $Label. The running container does not match the current DevKit image/profile contract. Re-run .\update-devkit.ps1 or rebuild/recreate the container."
    }
    Write-Host "[OK] $Label"
}

function Invoke-DockerExactOutputCheck {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,
        [Parameter(Mandatory = $true)]
        [string[]]$DockerArgs,
        [Parameter(Mandatory = $true)]
        [string]$Expected
    )

    $Output = & docker @DockerArgs
    $ExitCode = $LASTEXITCODE
    $Actual = (($Output | ForEach-Object { [string]$_ }) -join [Environment]::NewLine).Trim()
    if ($ExitCode -ne 0 -or $Actual -ne $Expected) {
        throw "[FAIL] $Label. Expected='$Expected', Actual='$Actual', ExitCode=$ExitCode. The running container does not match the current DevKit image/profile contract. Re-run .\update-devkit.ps1 or rebuild/recreate the container."
    }
    Write-Host "[OK] $Label -> $Actual"
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI was not found."
}

$PreviousPreference = $ErrorActionPreference
try {
    $ErrorActionPreference = "SilentlyContinue"
    $InspectOutput = & docker inspect $Container 2>$null
    $InspectExitCode = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $PreviousPreference
}

if ($InspectExitCode -ne 0) {
    throw "Container '$Container' does not exist. Start it first with: docker compose up -d --force-recreate"
}

try {
    $InspectResult = ConvertFrom-Json -InputObject ($InspectOutput -join [Environment]::NewLine)
    $ContainerInspect = @($InspectResult)[0]
}
catch {
    throw "Failed to parse docker inspect JSON for container '$Container'. Error=$($_.Exception.Message)"
}

if ($null -eq $ContainerInspect) {
    throw "Docker inspect returned no data for container '$Container'."
}

if (-not $ContainerInspect.State.Running) {
    throw "Container '$Container' is not running. Start it with: docker compose up -d --force-recreate"
}

$ExpectedJavaHomeEntry = "JAVA_HOME=/opt/jdks/temurin-17"
$ContainerEnv = @($ContainerInspect.Config.Env)
if ($ContainerEnv -notcontains $ExpectedJavaHomeEntry) {
    $DetectedJavaHome = @($ContainerEnv | Where-Object { $_ -like "JAVA_HOME=*" }) | Select-Object -First 1
    if ([string]::IsNullOrWhiteSpace($DetectedJavaHome)) {
        $DetectedJavaHome = "<missing>"
    }
    throw "[FAIL] JAVA_HOME. Expected '$ExpectedJavaHomeEntry', got '$DetectedJavaHome'. Rebuild/recreate the DevKit container."
}
Write-Host "[OK] JAVA_HOME -> /opt/jdks/temurin-17"

# Keep these checks shell-free. Windows PowerShell 5.1 native argument marshalling can
# split a `sh -lc` command containing nested quotes / $() before it reaches the container.
Invoke-DockerExactOutputCheck -Label "Pinned Git 2.55.0 runtime" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "/usr/local/bin/git", "--version"
) -Expected "git version 2.55.0"
Invoke-DockerExactOutputCheck -Label "Relative Git worktree paths" -DockerArgs @(
    "exec", "--user", "hermes", $Container,
    "/usr/local/bin/git", "config", "--system", "--bool", "--get", "worktree.useRelativePaths"
) -Expected "true"
Invoke-DockerCheck -Label "Default Java 17 command" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "/usr/local/bin/java", "-version"
)
Invoke-DockerCheck -Label "Default javac 17 command" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "/usr/local/bin/javac", "-version"
)
Invoke-DockerCheck -Label "Temurin JDK 8 java" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "/opt/jdks/temurin-8/bin/java", "-version"
)
Invoke-DockerCheck -Label "Temurin JDK 8 javac" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "/opt/jdks/temurin-8/bin/javac", "-version"
)
Invoke-DockerCheck -Label "Temurin JDK 17 java" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "/opt/jdks/temurin-17/bin/java", "-version"
)
Invoke-DockerCheck -Label "Temurin JDK 17 javac" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "/opt/jdks/temurin-17/bin/javac", "-version"
)
Invoke-DockerCheck -Label "Temurin JDK 21 java" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "/opt/jdks/temurin-21/bin/java", "-version"
)
Invoke-DockerCheck -Label "Temurin JDK 21 javac" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "/opt/jdks/temurin-21/bin/javac", "-version"
)
Invoke-DockerCheck -Label "hermes-java launcher" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "test", "-x", "/usr/local/bin/hermes-java"
)
Invoke-DockerExactOutputCheck -Label "Standalone pnpm 12.5.1 runtime" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "/usr/local/bin/pnpm", "--version"
) -Expected "12.5.1"
Invoke-DockerCheck -Label "Hermes CLI stable path" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "/usr/local/bin/hermes", "--help"
)


$DiscordKanbanNotifierCheck = @'
import ast
import inspect
import textwrap

import gateway.kanban_watchers_notifier as notifier

if "registered" not in notifier.TERMINAL_KINDS:
    raise SystemExit("registered event is missing from TERMINAL_KINDS")
if "registered" not in notifier._EVENT_FORMATTERS:
    raise SystemExit("registered event is missing from _EVENT_FORMATTERS")

source = textwrap.dedent(inspect.getsource(notifier._KanbanNotification._send_event))
tree = ast.parse(source)
method = tree.body[0]

formatter_calls = [
    node
    for node in ast.walk(method)
    if isinstance(node, ast.Call)
    and isinstance(node.func, ast.Name)
    and node.func.id == "_devkit_discord_kanban_message"
]
if len(formatter_calls) != 1:
    raise SystemExit(f"expected one Discord formatter call in _send_event, got {len(formatter_calls)}")

for node in method.body:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        continue
    nested_formatter_calls = [
        child
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
        and isinstance(child.func, ast.Name)
        and child.func.id == "_devkit_discord_kanban_message"
    ]
    if nested_formatter_calls:
        raise SystemExit(f"Discord formatter is incorrectly nested inside {node.name}()")
    nested_msg_writes = [
        child
        for child in ast.walk(node)
        if isinstance(child, ast.Name)
        and child.id == "msg"
        and isinstance(child.ctx, ast.Store)
    ]
    if nested_msg_writes:
        raise SystemExit(f"nested notifier function {node.name}() writes msg and can shadow the outer argument")

print("Discord Kanban notifier registration/msg-scope contract valid")
'@

$DiscordKanbanNotifierCheck | & docker exec -i --user hermes $Container /opt/hermes/.venv/bin/python -
if ($LASTEXITCODE -ne 0) {
    throw "[FAIL] Discord Kanban notifier registration/msg-scope contract. Re-run .\\update-devkit.ps1 or rebuild/recreate the container."
}
Write-Host "[OK] Discord Kanban notifier registration/msg-scope contract"

$MultiplexEnvEntry = @($ContainerEnv | Where-Object { $_ -like "GATEWAY_MULTIPLEX_PROFILES=*" }) | Select-Object -First 1
if ($MultiplexEnvEntry -ne "GATEWAY_MULTIPLEX_PROFILES=true") {
    throw "[FAIL] DevKit Gateway topology. Expected 'GATEWAY_MULTIPLEX_PROFILES=true', got '$MultiplexEnvEntry'. Rebuild/recreate the DevKit container."
}
Write-Host "[OK] DevKit Gateway topology -> default multiplex"

Invoke-DockerExactOutputCheck -Label "Default multiplex Gateway service is running" -DockerArgs @(
    "exec", $Container, "/package/admin/s6/command/s6-svstat", "-o", "up",
    "/run/service/gateway-default"
) -Expected "true"

$MultiplexRuntimeCheck = @'
import time

from hermes_cli.gateway_multiplex_mode import default_gateway_multiplexes
from hermes_cli.gateway_multiplex_served import recorded_served_profiles

required = {"default", "coder", "orchestrator", "reviewer"}
last = []
for _ in range(20):
    served = recorded_served_profiles()
    last = list(served or [])
    if default_gateway_multiplexes() and required.issubset(set(last)):
        print("true")
        raise SystemExit(0)
    time.sleep(0.5)

raise SystemExit(
    "default gateway is not serving the required DevKit profiles: "
    f"required={sorted(required)!r}, served={last!r}"
)
'@

$MultiplexRuntimeCheck | & docker exec -i --user hermes $Container /opt/hermes/.venv/bin/python -
if ($LASTEXITCODE -ne 0) {
    throw "[FAIL] Default multiplex Gateway served-profile contract. Re-run .\update-devkit.ps1 or rebuild/recreate the container."
}
Write-Host "[OK] Default multiplex Gateway serves default/coder/orchestrator/reviewer"
Invoke-DockerCheck -Label "Tirith routed-profile guard patch" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "sh", "-lc",
    "grep -q DEVKIT_TIRITH_PROFILE_GUARD_V1 /opt/hermes/tools/tirith_security.py"
)
Invoke-DockerCheck -Label "Codex Kanban worker-context runtime" -DockerArgs @(
    "exec", "--user", "hermes", $Container,
    "/opt/hermes/.venv/bin/python", "/opt/hermes/hermes_cli/devkit_kanban_worker_context.py", "--self-test"
)

$TirithProfileGuardCheck = @'
import os
from hermes_constants import reset_hermes_home_override, set_hermes_home_override
from tools.tirith_security import _devkit_only_analysis_incomplete, _devkit_tirith_subprocess_env

before_home = os.environ.get("HOME")
before_hermes_home = os.environ.get("HERMES_HOME")
token = set_hermes_home_override("/opt/data/profiles/coder")
try:
    env = _devkit_tirith_subprocess_env()
    if env.get("HERMES_HOME") != "/opt/data/profiles/coder":
        raise SystemExit(f"routed HERMES_HOME bridge mismatch: {env.get('HERMES_HOME')!r}")
    if not env.get("HOME"):
        raise SystemExit("Tirith subprocess HOME was not resolved")
    if os.environ.get("HOME") != before_home or os.environ.get("HERMES_HOME") != before_hermes_home:
        raise SystemExit("Tirith profile env helper mutated process-global environment")
    if not _devkit_only_analysis_incomplete([{"rule_id": "analysis_incomplete"}]):
        raise SystemExit("analysis_incomplete classification missing")
    if _devkit_only_analysis_incomplete([{"rule_id": "malware_package"}]):
        raise SystemExit("positive security finding was misclassified as analysis_incomplete")
finally:
    reset_hermes_home_override(token)
print("Tirith routed-profile guard contract valid")
'@

$TirithProfileGuardCheck | & docker exec -i --user hermes $Container /opt/hermes/.venv/bin/python -
if ($LASTEXITCODE -ne 0) {
    throw "[FAIL] Tirith routed-profile guard runtime contract. Re-run .\update-devkit.ps1 or rebuild/recreate the container."
}
Write-Host "[OK] Tirith routed-profile guard runtime contract"

$CodexContextRegistryCheck = @'
import os
os.environ["HERMES_KANBAN_TASK"] = "t_devkit_registry_check"
from model_tools import get_tool_definitions
from agent.transports.hermes_tools_mcp_server import EXPOSED_TOOLS
names = {
    item["function"]["name"]
    for item in get_tool_definitions(enabled_toolsets=["kanban"], quiet_mode=True)
    if isinstance(item, dict) and item.get("type") == "function"
}
if "kanban_worker_context" not in names:
    raise SystemExit(f"kanban_worker_context missing from Hermes registry: {sorted(names)!r}")
if "kanban_worker_context" not in EXPOSED_TOOLS:
    raise SystemExit("kanban_worker_context missing from Codex Hermes MCP EXPOSED_TOOLS")
print("Codex Kanban worker-context registry/MCP contract valid")
'@

$CodexContextRegistryCheck | & docker exec -i --user hermes $Container /opt/hermes/.venv/bin/python -
if ($LASTEXITCODE -ne 0) {
    throw "[FAIL] Codex Hermes MCP worker-context registry contract. Re-run .\update-devkit.ps1 or rebuild/recreate the container."
}
Write-Host "[OK] Codex Hermes MCP worker-context registry contract"

Invoke-DockerCheck -Label "Shared custom skill root" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "test", "-d", "/opt/custom-skills/shared"
)
Invoke-DockerCheck -Label "Shared Spring guideline capability" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "test", "-f", "/opt/custom-skills/shared/dev-spring-guidelines/SKILL.md"
)
Invoke-DockerCheck -Label "Shared Spring test capability" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "test", "-f", "/opt/custom-skills/shared/dev-spring-test/SKILL.md"
)
Invoke-DockerCheck -Label "Shared Node dependency capability" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "test", "-f", "/opt/custom-skills/shared/dev-node-dependencies/SKILL.md"
)
Invoke-DockerCheck -Label "Deprecated worktree skills removed" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "sh", "-lc",
    "test ! -e /opt/custom-skills/orchestrator/dev-worktree-dispatch && test ! -e /opt/custom-skills/orchestrator/dev-worktree-cleanup"
)

foreach ($Profile in @("orchestrator", "coder", "reviewer")) {
    Invoke-DockerCheck -Label "Bundled skill opt-out: $Profile" -DockerArgs @(
        "exec", "--user", "hermes", $Container,
        "test", "-f", "/opt/data/profiles/$Profile/.no-bundled-skills"
    )
}

$ProfileConfigCheck = @'
from pathlib import Path
import sys
import yaml

profile = sys.argv[1]
config = Path(f"/opt/data/profiles/{profile}/config.yaml")
expected = {
    "orchestrator": ["/opt/custom-skills/orchestrator", "/opt/custom-skills/shared"],
    "coder": ["/opt/custom-skills/coder", "/opt/custom-skills/shared"],
    "reviewer": ["/opt/custom-skills/reviewer", "/opt/custom-skills/shared"],
}[profile]
required_toolsets = ["hermes-cli", "kanban"]

data = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
actual = data.get("skills", {}).get("external_dirs")
if actual != expected:
    raise SystemExit(f"{profile}: expected external_dirs={expected!r}, got {actual!r}")

toolsets = data.get("toolsets")
if not isinstance(toolsets, list):
    raise SystemExit(f"{profile}: toolsets must be a YAML list, got {toolsets!r}")
missing = [item for item in required_toolsets if item not in toolsets]
if missing:
    raise SystemExit(f"{profile}: missing required toolsets={missing!r}, got {toolsets!r}")
'@

foreach ($Profile in @("orchestrator", "coder", "reviewer")) {
    $ProfileConfigCheck | & docker exec -i --user hermes $Container /opt/hermes/.venv/bin/python - $Profile
    if ($LASTEXITCODE -ne 0) {
        throw "[FAIL] Profile skill/toolset contract: $Profile"
    }
    Write-Host "[OK] Profile skill/toolset contract: $Profile"
}

Write-Host "[PASS] Hermes container runtime matches the current DevKit contract."
