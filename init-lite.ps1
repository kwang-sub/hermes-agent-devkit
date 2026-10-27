#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$Container = "hermes-dev",
    [switch]$ArchiveLegacyProfiles,
    [switch]$DryRun
)
Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
try {
    foreach ($Source in @("scripts/lite_mode.py", "scripts/lite_default_profile.py")) {
        $File = Join-Path $Root $Source
        if (-not (Test-Path -LiteralPath $File -PathType Leaf)) {
            throw "Required Lite adapter missing: $File"
        }
    }
    $Running = & docker inspect --format "{{.State.Running}}" $Container 2>$null
    if ($LASTEXITCODE -ne 0 -or ((@($Running) -join "").Trim().ToLowerInvariant() -ne "true")) {
        throw "Hermes container is not running: $Container"
    }
    $RawMounts = & docker inspect --format "{{json .Mounts}}" $Container
    if ($LASTEXITCODE -ne 0) { throw "Failed to inspect Docker mounts" }
    $Decoded = ConvertFrom-Json -InputObject (@($RawMounts) -join "")
    $Mounts = @($Decoded | Where-Object { $_.Destination -eq "/opt/data" })
    if ($Mounts.Count -ne 1 -or $Mounts[0].Type -notin @("volume","bind") -or -not $Mounts[0].RW) {
        throw "Required persistent writable /opt/data mount missing"
    }
    foreach ($Pair in @(
        @{ From = "scripts/lite_mode.py"; To = "/tmp/lite_mode.py" },
        @{ From = "scripts/lite_default_profile.py"; To = "/tmp/devkit-lite-default-profile.py" }
    )) {
        & docker cp (Join-Path $Root $Pair.From) ("$Container" + ":" + $Pair.To)
        if ($LASTEXITCODE -ne 0) { throw "Failed to copy Lite Python adapter" }
    }
    $Mode = if ($DryRun) { "plan" } else { "apply" }
    $ArgsList = @("exec", "--user", "hermes", $Container,
                  "/opt/hermes/.venv/bin/python", "/tmp/devkit-lite-default-profile.py", $Mode)
    if ($ArchiveLegacyProfiles) { $ArgsList += "--archive-legacy-profiles" }
    & docker @ArgsList
    if ($LASTEXITCODE -ne 0) { throw "Lite default profile migration blocked; no persistent data removed" }
    Write-Host "[PASS] Lite default profile: $Mode"
    exit 0
}
catch {
    [Console]::Error.WriteLine("[FAIL] $($_.Exception.Message)")
    exit 1
}
