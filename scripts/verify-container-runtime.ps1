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
$SkillEnv = @($ContainerEnv | Where-Object { $_ -like "HERMES_CONTAINER_CUSTOM_SKILLS_PATH=*" }) | Select-Object -First 1
$SkillsRoot = if ($SkillEnv) { ($SkillEnv -split "=",2)[1] } else { "/opt/custom-skills" }

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
Invoke-DockerCheck -Label "hermes-maven launcher" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "/usr/local/bin/hermes-maven", "--help"
)

$MavenRuntimeCheck = @'
from pathlib import Path
import os
import tempfile

for key in ("HERMES_MAVEN_ROOT", "HERMES_MAVEN_REPO_ROOT", "HERMES_MAVEN_DIST_ROOT", "HERMES_MAVEN_DOWNLOAD_ROOT", "HERMES_MAVEN_LOCK_ROOT"):
    value = os.environ.get(key, "")
    if not value.startswith("/") or "\\n" in value or "\n" in value:
        raise SystemExit(f"Invalid Maven runtime environment: {key}")
    root = Path(value)
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryFile(dir=root):
        pass
assert os.environ.get("GRADLE_USER_HOME") == "/opt/data/gradle/user-home"
print("Managed Maven cache contract valid for Lite default")
'@

$MavenRuntimeCheck | & docker exec -i --user hermes $Container /opt/hermes/.venv/bin/python -
if ($LASTEXITCODE -ne 0) {
    throw "[FAIL] Managed Maven runtime/cache contract. Rebuild/recreate the DevKit container and verify volume permissions."
}
Write-Host "[OK] Managed Maven runtime/cache contract"

Invoke-DockerExactOutputCheck -Label "Standalone pnpm 12.5.1 runtime" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "/usr/local/bin/pnpm", "--version"
) -Expected "12.5.1"
Invoke-DockerCheck -Label "Hermes CLI stable path" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "/usr/local/bin/hermes", "--help"
)
Invoke-DockerCheck -Label "Kanban board inventory CLI" -DockerArgs @(
    "exec", "--user", "hermes", $Container,
    "/opt/hermes/.venv/bin/hermes", "kanban", "boards", "list", "--json"
)

$S6ScandirWriteProbe = @'
from pathlib import Path
import os

root = Path("/run/service")
probe = root / ".devkit-runtime-write-check"
if probe.exists():
    if probe.is_dir():
        probe.rmdir()
    else:
        probe.unlink()
probe.mkdir()
probe.rmdir()

for name in ("control", "lock"):
    path = root / ".s6-svscan" / name
    if path.exists() and not os.access(path, os.W_OK):
        raise SystemExit(f"hermes cannot write {path}")

print("true")
'@

$S6ScandirWriteProbe | & docker exec -i --user hermes $Container /opt/hermes/.venv/bin/python -
if ($LASTEXITCODE -ne 0) {
    throw "[FAIL] s6 dynamic Gateway scandir hermes-write contract. Re-run .\update-devkit.ps1 or rebuild/recreate the container."
}
Write-Host "[OK] s6 dynamic Gateway scandir is hermes-writable"


Invoke-DockerCheck -Label "DevKit Kanban notifier dynamic service" -DockerArgs @(
    "exec", "--user", "root", $Container, "test", "-x",
    "/run/service/devkit-notifier/run"
)

Invoke-DockerExactOutputCheck -Label "DevKit Kanban notifier service is running" -DockerArgs @(
    "exec", $Container, "/package/admin/s6/command/s6-svstat", "-o", "up",
    "/run/service/devkit-notifier"
) -Expected "true"

Invoke-DockerCheck -Label "DevKit Kanban notifier self-test" -DockerArgs @(
    "exec", "--user", "hermes", $Container,
    "/opt/hermes/.venv/bin/python", "/opt/devkit/bin/devkit_kanban_notifier.py", "--self-test"
)

$NotifierOwnershipCheck = @'
from pathlib import Path
try:
    import hermes_yaml as yaml
except ModuleNotFoundError as exc:
    if exc.name != "hermes_yaml":
        raise
    import yaml  # Legacy Hermes/PyYAML fallback

configs = {
    "default": Path("/opt/data/config.yaml"),
}
for profile, path in configs.items():
    if not path.is_file():
        raise SystemExit(f"{profile}: missing config {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    kanban = data.get("kanban", {}) if isinstance(data, dict) else {}
    if kanban.get("notify_in_gateway") is not False:
        raise SystemExit(f"{profile}: kanban.notify_in_gateway must be false")
    if kanban.get("auto_subscribe_on_create") is not False:
        raise SystemExit(f"{profile}: kanban.auto_subscribe_on_create must be false")
print("DevKit Kanban notifier ownership contract valid")
'@

$NotifierOwnershipCheck | & docker exec -i --user hermes $Container /opt/hermes/.venv/bin/python -
if ($LASTEXITCODE -ne 0) {
    throw "[FAIL] DevKit Kanban notifier ownership contract. Re-run .\update-devkit.ps1 or rebuild/recreate the container."
}
Write-Host "[OK] DevKit Kanban notifier ownership contract"

$MultiplexEnvEntry = @($ContainerEnv | Where-Object { $_ -like "GATEWAY_MULTIPLEX_PROFILES=*" }) | Select-Object -First 1
if ($MultiplexEnvEntry -ne "GATEWAY_MULTIPLEX_PROFILES=true") {
    throw "[FAIL] DevKit Gateway topology. Expected 'GATEWAY_MULTIPLEX_PROFILES=true', got '$MultiplexEnvEntry'. Rebuild/recreate the DevKit container."
}
Write-Host "[OK] DevKit Gateway topology -> default multiplex"

Invoke-DockerExactOutputCheck -Label "Default Gateway service is running" -DockerArgs @(
    "exec", $Container, "/package/admin/s6/command/s6-svstat", "-o", "up",
    "/run/service/gateway-default"
) -Expected "true"

# The s6 'up' state is distinct from the live default Gateway identity and
# multiplex served-profile publication. The probe inspects both, waits for
# bounded startup, attempts one control-socket rescan only for a live host,
# and prints a classified diagnostic on failure.
Invoke-DockerCheck -Label "Default Lite Gateway served-profile contract" -DockerArgs @(
    "exec", "--user", "hermes", $Container,
    "/opt/hermes/.venv/bin/python",
    "/opt/devkit/bin/devkit_gateway_readiness.py",
    "--wait-seconds", "60"
)

Write-Host "[OK] Default Lite Gateway serves default"
$SecurityContractCheck = @'
import os
from pathlib import Path
from tools.approval_detection import detect_hardline_command, detect_dangerous_command
from tools.approval_floors import _hardline_block_result
assert callable(detect_hardline_command)
assert callable(detect_dangerous_command)
assert callable(_hardline_block_result)

if Path("/opt/hermes/tools/tirith_security.py").is_file():
    from hermes_constants import reset_hermes_home_override, set_hermes_home_override
    from tools.tirith_security import _devkit_only_analysis_incomplete, _devkit_tirith_subprocess_env
    before_home = os.environ.get("HOME")
    before_hermes_home = os.environ.get("HERMES_HOME")
    token = set_hermes_home_override("/tmp/devkit-security-probe")
    try:
        env = _devkit_tirith_subprocess_env()
        assert env.get("HERMES_HOME") == "/tmp/devkit-security-probe"
        assert env.get("HOME")
        assert os.environ.get("HOME") == before_home
        assert os.environ.get("HERMES_HOME") == before_hermes_home
        assert _devkit_only_analysis_incomplete([{"rule_id": "analysis_incomplete"}])
        assert not _devkit_only_analysis_incomplete([{"rule_id": "malware_package"}])
    finally:
        reset_hermes_home_override(token)
    print("legacy Tirith routed-profile guard contract valid")
else:
    from hermes_cli.config_migrations import _RETIRED_TIRITH_KEYS
    assert "tirith_enabled" in _RETIRED_TIRITH_KEYS
    assert "tirith_fail_open" in _RETIRED_TIRITH_KEYS
    print("upstream retired Tirith; core approval guard contract valid")
'@

$SecurityContractCheck | & docker exec -i --user hermes $Container /opt/hermes/.venv/bin/python -
if ($LASTEXITCODE -ne 0) {
    throw "[FAIL] Hermes security guard runtime contract. Re-run .\update-devkit.ps1 or rebuild/recreate the container."
}
Write-Host "[OK] Hermes security guard runtime contract"

Invoke-DockerCheck -Label "Kanban tracking relation preview API v2" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "sh", "-lc",
    "grep -q DEVKIT_KANBAN_RELATION_PREVIEW_API_V2 /opt/hermes/plugins/kanban/dashboard/plugin_api.py && grep -q _devkit_tracking_parent_id /opt/hermes/plugins/kanban/dashboard/plugin_api.py"
)
Invoke-DockerCheck -Label "Kanban tracking relation preview UI v2" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "sh", "-lc",
    "grep -q DEVKIT_KANBAN_RELATION_PREVIEW_UI_V2 /opt/hermes/plugins/kanban/dashboard/dist/index.js && grep -q DEVKIT_KANBAN_RELATION_PREVIEW_CSS_V2 /opt/hermes/plugins/kanban/dashboard/dist/style.css"
)

$LiteDispatcherCheck = @'
import os
from gateway.kanban_watchers import GatewayKanbanWatchersMixin
assert os.environ.get("HERMES_KANBAN_DISPATCH_IN_GATEWAY") == "false"
assert GatewayKanbanWatchersMixin()._kanban_dispatcher_boot() is None
print("Native Kanban dispatcher disabled; no worker spawned")
'@
$LiteDispatcherCheck | & docker exec -i --user hermes $Container /opt/hermes/.venv/bin/python -
if ($LASTEXITCODE -ne 0) { throw "[FAIL] Lite record-only Kanban contract" }

Invoke-DockerCheck -Label "Shared custom skill root" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "test", "-d", "$SkillsRoot/shared"
)
Invoke-DockerCheck -Label "Shared Spring guideline capability" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "test", "-f", "$SkillsRoot/shared/dev-spring-guidelines/SKILL.md"
)
Invoke-DockerCheck -Label "Shared Spring test capability" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "test", "-f", "$SkillsRoot/shared/dev-spring-test/SKILL.md"
)
Invoke-DockerCheck -Label "Shared Node dependency capability" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "test", "-f", "$SkillsRoot/shared/dev-node-dependencies/SKILL.md"
)
Invoke-DockerCheck -Label "Lite default runtime adapter" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "/opt/hermes/.venv/bin/python", "/opt/devkit/bin/lite_default_profile.py", "status"
)
$DefaultLiteCheck = @'
from pathlib import Path
try:
    import hermes_yaml as yaml
except ModuleNotFoundError as exc:
    if exc.name != "hermes_yaml": raise
    import yaml

import os
root=Path(os.environ.get("HERMES_CONTAINER_CUSTOM_SKILLS_PATH","/opt/custom-skills"))
config=Path("/opt/data/config.yaml")
data=yaml.safe_load(config.read_text(encoding="utf-8")) or {}
skills=data.get("skills") or {}
assert {str(root/"shared"),str(root/"lite")}.issubset(set(skills.get("external_dirs") or []))
assert "dev-lite-session" in (skills.get("auto_load") or [])
assert {"hermes-cli", "kanban"}.issubset(set(data.get("toolsets") or []))
for profile in ("orchestrator", "coder", "reviewer"):
    assert not (Path("/opt/data/profiles") / profile).exists(), profile
for name in ("dev-lite-session", "dev-lite-review", "dev-worktree-create",
             "dev-worktree-remove", "dev-feature-docs", "dev-project-pattern",
             "git-pr-publish", "git-workspace-cleanup"):
    assert (root / "lite" / name / "SKILL.md").is_file(), name
print("Default-only Lite config and skills validated")
'@
$DefaultLiteCheck | & docker exec -i --user hermes $Container /opt/hermes/.venv/bin/python -
if ($LASTEXITCODE -ne 0) {
    throw "[FAIL] Default Lite skill/profile contract. Re-run .\update-devkit.ps1."
}
Write-Host "[OK] Default Lite skill/profile contract"

Write-Host "[PASS] Hermes container runtime matches the current DevKit contract."
