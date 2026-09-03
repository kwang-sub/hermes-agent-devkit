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
Invoke-DockerCheck -Label "Hermes CLI stable path" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "/usr/local/bin/hermes", "--help"
)
Invoke-DockerCheck -Label "Shared custom skill root" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "test", "-d", "/opt/custom-skills/shared"
)
Invoke-DockerCheck -Label "Shared Spring guideline capability" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "test", "-f", "/opt/custom-skills/shared/dev-spring-guidelines/SKILL.md"
)
Invoke-DockerCheck -Label "Shared Spring test capability" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "test", "-f", "/opt/custom-skills/shared/dev-spring-test/SKILL.md"
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
