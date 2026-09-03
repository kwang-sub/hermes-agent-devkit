#requires -Version 5.1

param(
    [switch]$EnvSelfTest
)

$ErrorActionPreference = "Stop"
$Script:DotEnvValues = @{}

function Import-DotEnv {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $Script:DotEnvValues = @{}
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return
    }

    foreach ($Line in Get-Content -LiteralPath $Path) {
        if ([string]::IsNullOrWhiteSpace($Line) -or $Line.TrimStart().StartsWith("#")) {
            continue
        }
        if ($Line -notmatch '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$') {
            throw "Unsupported .env line. Use KEY=VALUE with optional full-line comments."
        }

        $Value = $Matches[2].Trim()
        if ($Value.Length -ge 2) {
            $HasDoubleQuotes = $Value[0] -eq '"' -and $Value[$Value.Length - 1] -eq '"'
            $HasSingleQuotes = $Value[0] -eq "'" -and $Value[$Value.Length - 1] -eq "'"
            if ($HasDoubleQuotes -or $HasSingleQuotes) {
                $Value = $Value.Substring(1, $Value.Length - 2)
            }
        }
        $Script:DotEnvValues[$Matches[1]] = $Value
    }
}

function Get-EnvOrDefault {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [string]$Default
    )

    $ProcessValue = [Environment]::GetEnvironmentVariable($Name, "Process")
    if (-not [string]::IsNullOrEmpty($ProcessValue)) {
        return $ProcessValue
    }
    if ($Script:DotEnvValues.ContainsKey($Name) -and
        -not [string]::IsNullOrEmpty($Script:DotEnvValues[$Name])) {
        return $Script:DotEnvValues[$Name]
    }
    return $Default
}

function Join-ContainerPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root,

        [Parameter(Mandatory = $true)]
        [string]$Child
    )

    return $Root.TrimEnd("/") + "/" + $Child.TrimStart("/")
}

function Test-EnvHelpers {
    $Fixture = [System.IO.Path]::GetTempFileName()
    $ProcessKey = "HERMES_ENV_SELF_TEST_PROCESS"
    try {
        @'
HERMES_ENV_SELF_TEST_QUOTED="quoted value"
HERMES_ENV_SELF_TEST_EMPTY=
'@ | Set-Content -LiteralPath $Fixture -Encoding UTF8

        [Environment]::SetEnvironmentVariable($ProcessKey, "from-process", "Process")
        Import-DotEnv -Path $Fixture

        if ((Get-EnvOrDefault -Name $ProcessKey -Default "fallback") -ne "from-process") {
            throw "Process environment precedence self-test failed."
        }
        if ((Get-EnvOrDefault -Name "HERMES_ENV_SELF_TEST_QUOTED" -Default "fallback") -ne "quoted value") {
            throw "Quoted .env value self-test failed."
        }
        if ((Get-EnvOrDefault -Name "HERMES_ENV_SELF_TEST_EMPTY" -Default "fallback") -ne "fallback") {
            throw "Empty .env default self-test failed."
        }

        Write-Host "[PASS] .env helper self-test"
    }
    finally {
        [Environment]::SetEnvironmentVariable($ProcessKey, $null, "Process")
        Remove-Item -LiteralPath $Fixture -Force -ErrorAction SilentlyContinue
    }
}

if ($EnvSelfTest) {
    Test-EnvHelpers
    exit 0
}

Import-DotEnv -Path (Join-Path $PSScriptRoot ".env")

$Container = Get-EnvOrDefault -Name "HERMES_CONTAINER_NAME" -Default "hermes-dev"
$ContainerWorkspacePath = Get-EnvOrDefault -Name "HERMES_CONTAINER_WORKSPACE_PATH" -Default "/workspace"
$ContainerDataPath = "/opt/data"
$ContainerCustomSkillsPath = Get-EnvOrDefault -Name "HERMES_CONTAINER_CUSTOM_SKILLS_PATH" -Default "/opt/custom-skills"
$ContainerReviewerSkillsPath = Get-EnvOrDefault -Name "HERMES_CONTAINER_REVIEWER_SKILLS_PATH" -Default "/opt/reviewer-skills"
$ContainerSharedPath = Get-EnvOrDefault -Name "HERMES_CONTAINER_SHARED_PATH" -Default "/opt/data/shared"
$ContainerSharedSkillsPath = Join-ContainerPath -Root $ContainerCustomSkillsPath -Child "shared"

# The official Hermes image keeps the immutable application and venv under /opt/hermes.
# Use absolute paths instead of relying on the runtime user's PATH.
$HermesCliPath = "/opt/hermes/.venv/bin/hermes"
$PythonPath = "/opt/hermes/.venv/bin/python"

# Every profile reads its role-specific root plus the same shared root.
# Reviewer keeps /opt/reviewer-skills temporarily for backward compatibility with
# the existing Spring/API capability mounts; new common skills belong in shared.
$ExternalSkillDirs = @{
    orchestrator = @(
        (Join-ContainerPath -Root $ContainerCustomSkillsPath -Child "orchestrator"),
        $ContainerSharedSkillsPath
    )
    coder = @(
        (Join-ContainerPath -Root $ContainerCustomSkillsPath -Child "coder"),
        $ContainerSharedSkillsPath
    )
    reviewer = @(
        (Join-ContainerPath -Root $ContainerCustomSkillsPath -Child "reviewer"),
        $ContainerSharedSkillsPath,
        $ContainerReviewerSkillsPath
    )
}

# These official optional skills were present in the legacy DevKit profile baseline.
# Remove them only once per profile so later user-installed Hub skills are preserved.
$LegacyOfficialHubSkills = @(
    "ascii-art",
    "comfyui",
    "excalidraw",
    "pretext",
    "sketch",
    "touchdesigner-mcp",
    "evaluating-llms-harness",
    "huggingface-hub",
    "llama-cpp",
    "serving-llms-vllm",
    "weights-and-biases",
    "research-paper-writing",
    "openhue"
)
$SkillPolicyMigrationMarker = ".devkit-skill-policy-v1"

function Run-Docker {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Args
    )

    & docker @Args
    $ExitCode = $LASTEXITCODE

    if ($ExitCode -ne 0) {
        throw "Docker command failed. ExitCode=$ExitCode Args=$($Args -join ' ')"
    }
}

function Assert-Prerequisites {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker CLI was not found. Install Docker Desktop or add docker to PATH."
    }

    & docker version --format "{{.Client.Version}}" 1>$null 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker CLI cannot reach the Docker daemon. Start Docker Desktop and retry."
    }

    # Read the complete docker inspect JSON and parse it in PowerShell.
    # This avoids Docker Go-template quoting/escaping differences on Windows.
    $InspectOutput = & docker inspect $Container 2>$null
    $InspectExitCode = $LASTEXITCODE

    if ($InspectExitCode -ne 0) {
        throw "Container '$Container' does not exist. Start it with 'docker compose up -d'."
    }

    $InspectJson = $InspectOutput -join [Environment]::NewLine

    try {
        $InspectResult = ConvertFrom-Json -InputObject $InspectJson
    }
    catch {
        throw "Failed to parse docker inspect JSON for container '$Container'. Error=$($_.Exception.Message)"
    }

    $ContainerInspect = @($InspectResult)[0]

    if ($null -eq $ContainerInspect) {
        throw "Docker inspect returned no data for container '$Container'."
    }

    if (-not $ContainerInspect.State.Running) {
        throw "Container '$Container' is not running. Start it with 'docker compose up -d'."
    }

    Write-Host "[OK] Container running: $Container"

    $Mounts = @(
        $ContainerInspect.Mounts | ForEach-Object {
            "$($_.Type)|$($_.Destination)"
        }
    )

    foreach ($Destination in @(
        $ContainerWorkspacePath,
        $ContainerCustomSkillsPath,
        $ContainerSharedPath
    )) {
        $ExpectedMount = "bind|$Destination"

        if ($Mounts -notcontains $ExpectedMount) {
            $DetectedMounts = $Mounts -join ", "
            throw "Required bind mount is missing: $Destination. Detected mounts: $DetectedMounts"
        }

        Write-Host "[OK] Bind mount: $Destination"
    }

    Run-Docker -Args @(
        "exec",
        "--user", "hermes",
        $Container,
        $HermesCliPath,
        "--help"
    )
    Write-Host "[OK] Hermes CLI: $HermesCliPath"

    Run-Docker -Args @(
        "exec",
        "--user", "hermes",
        $Container,
        $PythonPath,
        "-c",
        "import yaml"
    )
    Write-Host "[OK] Python/PyYAML: $PythonPath"

    $RequiredPaths = @(
        $ExternalSkillDirs["orchestrator"] +
        $ExternalSkillDirs["coder"] +
        $ExternalSkillDirs["reviewer"] +
        @((Join-ContainerPath -Root $ContainerSharedPath -Child "AGENTS.common.md"))
    )

    foreach ($Path in $RequiredPaths) {
        Run-Docker -Args @(
            "exec",
            "--user", "hermes",
            $Container,
            "test", "-e", $Path
        )
        Write-Host "[OK] Required path: $Path"
    }
}

function Profile-Exists {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    & docker exec --user hermes $Container $HermesCliPath profile show $Name 1>$null 2>$null
    return ($LASTEXITCODE -eq 0)
}

function Ensure-Profile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    if (Profile-Exists -Name $Name) {
        Write-Host "[OK] Profile exists: $Name"
        return
    }

    Write-Host "[CREATE] Profile without bundled skills: $Name"

    Run-Docker -Args @(
        "exec",
        "--user", "hermes",
        $Container,
        $HermesCliPath,
        "profile", "create", $Name,
        "--description", $Description,
        "--no-skills"
    )
}

function Ensure-BundledSkillOptOut {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Profile
    )

    Write-Host "[SKILLS] Disable bundled skill seeding: $Profile"
    Run-Docker -Args @(
        "exec",
        "--user", "hermes",
        $Container,
        $HermesCliPath,
        "-p", $Profile,
        "skills", "opt-out", "--remove", "--yes"
    )

    $Marker = Join-ContainerPath -Root $ContainerDataPath -Child "profiles/$Profile/.no-bundled-skills"
    Run-Docker -Args @(
        "exec",
        "--user", "hermes",
        $Container,
        "test", "-f", $Marker
    )
    Write-Host "[OK] Bundled skill opt-out marker: $Profile"
}

function Remove-LegacyOfficialHubSkillsOnce {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Profile
    )

    $ProfileHome = Join-ContainerPath -Root $ContainerDataPath -Child "profiles/$Profile"
    $MigrationMarker = Join-ContainerPath -Root $ProfileHome -Child $SkillPolicyMigrationMarker

    & docker exec --user hermes $Container test -f $MigrationMarker 1>$null 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Legacy Hub skill migration already applied: $Profile"
        return
    }

    $LockFile = Join-ContainerPath -Root $ProfileHome -Child "skills/.hub/lock.json"
    $Py = @'
from pathlib import Path
import json
import sys

lock_path = Path(sys.argv[1])
wanted = sys.argv[2:]
if not lock_path.is_file():
    raise SystemExit(0)

try:
    data = json.loads(lock_path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    raise SystemExit(f"Invalid Hub lock file {lock_path}: {exc}")

installed = data.get("installed", {})
if not isinstance(installed, dict):
    raise SystemExit(f"Invalid Hub lock installed mapping: {lock_path}")

for name in wanted:
    if name in installed:
        print(name)
'@

    $DockerArgs = @(
        "exec", "-i",
        "--user", "hermes",
        $Container,
        $PythonPath,
        "-",
        $LockFile
    ) + $LegacyOfficialHubSkills

    $InstalledLegacy = @($Py | & docker @DockerArgs)
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to inspect Hub lock for '$Profile'."
    }

    foreach ($Skill in $InstalledLegacy) {
        $Name = ([string]$Skill).Trim()
        if ([string]::IsNullOrWhiteSpace($Name)) {
            continue
        }
        Write-Host "[REMOVE] Legacy Hub skill: $Profile -> $Name"
        Run-Docker -Args @(
            "exec",
            "--user", "hermes",
            $Container,
            $HermesCliPath,
            "-p", $Profile,
            "skills", "uninstall", $Name, "--yes"
        )
    }

    Run-Docker -Args @(
        "exec",
        "--user", "hermes",
        $Container,
        $PythonPath,
        "-c",
        "from pathlib import Path; import sys; Path(sys.argv[1]).touch()",
        $MigrationMarker
    )
    Write-Host "[OK] Legacy Hub skill migration complete: $Profile"
}

function Ensure-ExternalDirs {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Profile,

        [Parameter(Mandatory = $true)]
        [string[]]$ExternalDirs
    )

    $Config = Join-ContainerPath -Root $ContainerDataPath -Child "profiles/$Profile/config.yaml"

    # `hermes config set skills.external_dirs ...` serializes the list as a
    # scalar string in this environment. The embedded helper validates YAML,
    # changes only skills.external_dirs, backs up an existing file before a
    # required change, and writes atomically without printing config content.
    $Py = @'
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile
import yaml

p = Path(sys.argv[1])
external_dirs = sys.argv[2:]
if not external_dirs:
    raise SystemExit("At least one external skill directory is required")

p.parent.mkdir(parents=True, exist_ok=True)
original = p.read_text(encoding="utf-8") if p.exists() else ""

try:
    document = yaml.safe_load(original) if original.strip() else {}
except yaml.YAMLError as exc:
    raise SystemExit(f"Invalid YAML in {p}: {exc.problem or 'parse error'}")

if document is None:
    document = {}
if not isinstance(document, dict):
    raise SystemExit(f"Config root must be a YAML mapping: {p}")

skills = document.get("skills")
if skills is None:
    skills = {}
if not isinstance(skills, dict):
    raise SystemExit(f"The skills section must be a YAML mapping: {p}")

if skills.get("external_dirs") == external_dirs:
    print(f"[OK] External skills already configured: {p}")
    raise SystemExit(0)

lines = original.splitlines()
start = next(
    (i for i, line in enumerate(lines) if re.match(r"^skills\s*:", line)),
    None,
)

if start is None:
    if original and not original.endswith("\n"):
        original += "\n"
    rendered = "".join(f"    - {item}\n" for item in external_dirs)
    updated = original + "skills:\n  external_dirs:\n" + rendered
else:
    end = len(lines)
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if line and not line[0].isspace() and not line.lstrip().startswith("#"):
            end = i
            break

    section = lines[start:end]
    block_header = re.match(r"^skills\s*:\s*(?:#.*)?$", section[0])

    if block_header:
        child_indents = [
            len(line) - len(line.lstrip(" "))
            for line in section[1:]
            if line.strip() and not line.lstrip().startswith("#")
        ]
        child_indent = min(child_indents) if child_indents else 2
        prefix = " " * child_indent
        key_index = next(
            (
                i
                for i, line in enumerate(section[1:], 1)
                if re.match(rf"^{re.escape(prefix)}external_dirs\s*:", line)
            ),
            None,
        )
        replacement = [f"{prefix}external_dirs:"] + [
            f"{prefix}  - {item}" for item in external_dirs
        ]

        if key_index is None:
            section = [section[0], *replacement, *section[1:]]
        else:
            value_end = key_index + 1
            while value_end < len(section):
                candidate = section[value_end]
                if not candidate.strip():
                    value_end += 1
                    continue
                indent = len(candidate) - len(candidate.lstrip(" "))
                if indent <= child_indent:
                    break
                value_end += 1
            section = section[:key_index] + replacement + section[value_end:]
    else:
        skills["external_dirs"] = external_dirs
        section = yaml.safe_dump(
            {"skills": skills},
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        ).rstrip("\n").splitlines()

    updated = "\n".join(lines[:start] + section + lines[end:]) + "\n"

try:
    verified = yaml.safe_load(updated)
except yaml.YAMLError as exc:
    raise SystemExit(f"Refusing to write invalid YAML: {exc.problem or 'parse error'}")

if verified.get("skills", {}).get("external_dirs") != external_dirs:
    raise SystemExit("Refusing to write config: skills.external_dirs is not the expected YAML list")

if p.exists():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = p.with_name(f"{p.name}.bak-{stamp}")
    shutil.copy2(p, backup)
    print(f"[BACKUP] {backup}")

fd, temporary_name = tempfile.mkstemp(prefix=f".{p.name}.", dir=p.parent)
os.close(fd)
temporary = Path(temporary_name)
try:
    temporary.write_text(updated, encoding="utf-8")
    if p.exists():
        temporary.chmod(stat.S_IMODE(p.stat().st_mode))
    os.replace(temporary, p)
finally:
    temporary.unlink(missing_ok=True)

print(f"[UPDATE] External skills configured: {p}")
'@

    Write-Host "[CONFIG] $Profile -> $($ExternalDirs -join ', ')"
    $DockerArgs = @(
        "exec", "-i",
        "--user", "hermes",
        $Container,
        $PythonPath,
        "-",
        $Config
    ) + $ExternalDirs

    $Py | & docker @DockerArgs
    $ExitCode = $LASTEXITCODE

    if ($ExitCode -ne 0) {
        throw "Failed to configure external skills for '$Profile'. ExitCode=$ExitCode"
    }
}

function Verify-ExternalDirs {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Profile,

        [Parameter(Mandatory = $true)]
        [string[]]$Expected
    )

    $Config = Join-ContainerPath -Root $ContainerDataPath -Child "profiles/$Profile/config.yaml"

    $Py = @'
from pathlib import Path
import sys
import yaml

p = Path(sys.argv[1])
expected = sys.argv[2:]

if not p.is_file():
    raise SystemExit(f"Missing config: {p}")

try:
    document = yaml.safe_load(p.read_text(encoding="utf-8"))
except yaml.YAMLError as exc:
    raise SystemExit(f"Invalid YAML in {p}: {exc.problem or 'parse error'}")

if not isinstance(document, dict):
    raise SystemExit(f"Config root must be a YAML mapping: {p}")

skills = document.get("skills")
if not isinstance(skills, dict):
    raise SystemExit(f"The skills section must be a YAML mapping: {p}")

external_dirs = skills.get("external_dirs")
if not isinstance(external_dirs, list):
    raise SystemExit("skills.external_dirs must be a YAML list")

if external_dirs != expected:
    raise SystemExit(f"Unexpected skills.external_dirs value for {p}: {external_dirs!r}")

print(f"[PASS] YAML list verified: {p}")
'@

    $DockerArgs = @(
        "exec", "-i",
        "--user", "hermes",
        $Container,
        $PythonPath,
        "-",
        $Config
    ) + $Expected

    $Py | & docker @DockerArgs
    $ExitCode = $LASTEXITCODE

    if ($ExitCode -ne 0) {
        throw "Verification failed for '$Profile'. ExitCode=$ExitCode"
    }
}

Write-Host "=== Hermes Profile Initialization ==="

Assert-Prerequisites

Ensure-Profile `
    -Name "orchestrator" `
    -Description "Coordinates development requests, project approval, planning, dispatch, and workflow status."

Ensure-Profile `
    -Name "coder" `
    -Description "Implements approved development plans and tests in the assigned workspace."

Ensure-Profile `
    -Name "reviewer" `
    -Description "Reviews implementation changes and requests corrections or approves the task."

Write-Host ""
Write-Host "=== Apply Profile Skill Policy ==="

foreach ($Profile in @("orchestrator", "coder", "reviewer")) {
    Ensure-BundledSkillOptOut -Profile $Profile
    Remove-LegacyOfficialHubSkillsOnce -Profile $Profile
}

Write-Host ""
Write-Host "=== Configure External Skills ==="

Ensure-ExternalDirs `
    -Profile "orchestrator" `
    -ExternalDirs $ExternalSkillDirs["orchestrator"]

Ensure-ExternalDirs `
    -Profile "coder" `
    -ExternalDirs $ExternalSkillDirs["coder"]

Ensure-ExternalDirs `
    -Profile "reviewer" `
    -ExternalDirs $ExternalSkillDirs["reviewer"]

Write-Host ""
Write-Host "=== Verify YAML List Format ==="

Verify-ExternalDirs `
    -Profile "orchestrator" `
    -Expected $ExternalSkillDirs["orchestrator"]

Verify-ExternalDirs `
    -Profile "coder" `
    -Expected $ExternalSkillDirs["coder"]

Verify-ExternalDirs `
    -Profile "reviewer" `
    -Expected $ExternalSkillDirs["reviewer"]

Write-Host ""
Write-Host "=== Profile List ==="

Run-Docker -Args @(
    "exec",
    "--user", "hermes",
    $Container,
    $HermesCliPath,
    "profile", "list"
)

Write-Host ""
Write-Host "=== Initialization Complete ==="
Write-Host "Next:"
Write-Host "1. Configure model/OAuth for orchestrator"
Write-Host "2. Configure model/OAuth for coder"
Write-Host "3. Configure model/OAuth for reviewer"
Write-Host "4. Re-check config.yaml after model setup"
Write-Host "5. Start fresh Hermes sessions and verify role-specific/shared dev-* skills"
