#requires -Version 5.1
<#
.SYNOPSIS
Use the existing hermes-dev container with Lite or Standard Devkit policies.
.DESCRIPTION
No volume deletion, image rebuild, forced Git checkout, or Kanban mutation.
#>
[CmdletBinding()]
param(
    [ValidateSet("lite", "standard", "status")]
    [string]$Mode = "lite",
    [string]$LiteBranch = "experiment/hermes-lite",
    [string]$StandardBranch = "dev",
    [string]$Remote = "origin",
    [string]$Container = "hermes-dev",
    [switch]$NoFetch,
    [switch]$SelfTest
)
Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PriorLocation = Get-Location

# PowerShell reserves the automatic variable $args. Never use it as a
# parameter/argument-array name: native commands silently lose arguments.
function Run {
    param(
        [Parameter(Mandatory = $true)][string]$Program,
        [string[]]$Arguments = @()
    )
    & $Program @Arguments
    $ExitCode = $LASTEXITCODE
    if ($ExitCode -ne 0) {
        throw "Failed (exit $ExitCode): $Program $($Arguments -join ' ')"
    }
}
function Capture {
    param(
        [Parameter(Mandatory = $true)][string]$Program,
        [string[]]$Arguments = @()
    )
    $Result = & $Program @Arguments
    $ExitCode = $LASTEXITCODE
    if ($ExitCode -ne 0) {
        throw "Failed (exit $ExitCode): $Program $($Arguments -join ' ')"
    }
    return ((@($Result) | ForEach-Object { [string]$_ }) -join [Environment]::NewLine).Trim()
}
function Test-NativeArgumentForwarding {
    # Real git process, but no Docker and no repository changes.
    # Checks both one and several arguments through the very same wrappers
    # used by all update paths.
    $Version = Capture -Program "git" -Arguments @("--version")
    if ($Version -notmatch "^git version [0-9]") {
        throw "Git --version was not passed correctly: $Version"
    }
    $Resolved = Capture -Program "git" -Arguments @("-C", $Root, "rev-parse", "--show-toplevel")
    $Expected = (Resolve-Path -LiteralPath $Root).Path
    if ([IO.Path]::GetFullPath($Resolved).TrimEnd("\", "/") -ne
        [IO.Path]::GetFullPath($Expected).TrimEnd("\", "/")) {
        throw "Git multi-argument forwarding failed: $Resolved"
    }
    Run -Program "git" -Arguments @("-C", $Root, "rev-parse", "--is-inside-work-tree") | Out-Null
    Write-Host "[PASS] Real Git argv forwarding through Run and Capture"
}
function CheckGit {
    $Actual = Capture -Program "git" -Arguments @("rev-parse", "--show-toplevel")
    $Expected = (Resolve-Path -LiteralPath $Root).Path
    if ([IO.Path]::GetFullPath($Actual).TrimEnd("\", "/") -ne [IO.Path]::GetFullPath($Expected).TrimEnd("\", "/")) {
        throw "Must run from Devkit checkout."
    }
    if (Capture -Program "git" -Arguments @("status", "--porcelain=v1", "--untracked-files=normal")) {
        throw "Devkit checkout has uncommitted changes. Preserve them before switching."
    }
}
function CheckContainer {
    $Previous = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $Running = & docker inspect --format "{{.State.Running}}" $Container 2>$null
        $Code = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $Previous }
    if ($Code -ne 0 -or (@($Running) -join "").Trim() -ne "true") {
        throw "Container not running. Bootstrap once using .\update-devkit.ps1 -Branch $StandardBranch"
    }
    $Mounts = @(ConvertFrom-Json -InputObject (Capture -Program "docker" -Arguments @("inspect", "--format", "{{json .Mounts}}", $Container)))
    foreach ($Target in @("/opt/data", "/workspace", "/opt/custom-skills", "/opt/data/shared")) {
        $Found = @($Mounts | Where-Object { $_.Destination -eq $Target })
        if ($Found.Count -ne 1) { throw "Missing or duplicate mount at $Target" }
        $Required = if ($Target -eq "/opt/data") { "volume" } else { "bind" }
        if ($Found[0].Type -ne $Required) { throw "Mount type mismatch at $Target" }
    }
    $Volume = @($Mounts | Where-Object { $_.Destination -eq "/opt/data" })[0].Name
    if (-not $Volume) { throw "Persistent volume not resolved" }
    Write-Host "[OK] Existing container and named volume: $Volume"
}
function Adapter {
    param([string]$Action)
    $Source = Join-Path $Root "scripts\lite_mode.py"
    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) { throw "Missing Lite helper" }
    Run -Program "docker" -Arguments @("cp", $Source, ($Container + ":/tmp/devkit-lite-mode.py"))
    Run -Program "docker" -Arguments @("exec", "--user", "hermes", $Container, "/opt/hermes/.venv/bin/python", "/tmp/devkit-lite-mode.py", $Action)
}
function SwitchBranch {
    param([string]$Target)
    if ((Capture -Program "git" -Arguments @("branch", "--show-current")) -eq $Target) { return }
    CheckGit
    if ($Target -eq $LiteBranch -and -not $NoFetch) { Run -Program "git" -Arguments @("fetch", "--prune", $Remote) }
    & git show-ref --verify --quiet "refs/heads/$Target"
    if ($LASTEXITCODE -eq 0) {
        Run -Program "git" -Arguments @("switch", $Target)
    }
    elseif ($Target -eq $LiteBranch) {
        Run -Program "git" -Arguments @("switch", "--track", "-c", $Target, ($Remote + "/" + $Target))
    }
    else { throw "Local Standard branch missing: $Target" }
}
try {
    if ($SelfTest) {
        Test-NativeArgumentForwarding
        return
    }
    Set-Location -LiteralPath $Root
    foreach ($Command in @("git", "docker")) {
        if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) { throw "Missing executable: $Command" }
    }
    CheckGit
    CheckContainer
    $Current = Capture -Program "git" -Arguments @("branch", "--show-current")
    if ($Mode -eq "status") {
        Write-Host "[MODE] Branch=$Current"
        Adapter "status"
    }
    elseif ($Mode -eq "lite") {
        # After PR #188 was merged, Lite/Standard live in the same checkout.
        # A clean fix/feature branch may also run Lite if it includes this policy.
        # No user/project Git branch is modified.
        if (-not (Test-Path -LiteralPath (Join-Path $Root "lite\AGENTS.md") -PathType Leaf)) {
            throw "Lite policy file is missing in the current Devkit checkout."
        }
        if ($Current -eq $LiteBranch) { Adapter "guard" }
        # PR #188 was merged into dev; the deleted experiment branch is no
        # longer required. Apply the Lite overlay in the current checkout.
        # This is also compatible with a pre-existing local Lite branch.
        Adapter "apply"
        Run -Program "docker" -Arguments @("exec", "--user", "hermes", $Container, "/opt/hermes/.venv/bin/hermes", "--help")
        Write-Host "[PASS] Lite active on $Current. Start a NEW default-profile Hermes CLI session."
        Write-Host "docker exec -it --user hermes --workdir /workspace/hermes-agent-devkit/lite $Container /opt/hermes/.venv/bin/hermes -p default"
    }
    else {
        # Restore only Lite profile overlays, regardless of the Devkit branch.
        # The current checkout must still contain the Lite helper.
        Adapter "restore"
        # A pre-merge local Lite checkout can still return to dev, but no
        # branch switch is required for the merged/default dev configuration.
        if ($Current -eq $LiteBranch) { SwitchBranch $StandardBranch }
        Write-Host "[PASS] Standard profile policy restored; shared data preserved."
        Write-Host "Run .\update-devkit.ps1 for full Standard image and profile reconciliation when needed."
    }
}
finally { Set-Location $PriorLocation }
