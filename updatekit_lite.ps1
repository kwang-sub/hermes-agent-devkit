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
    [switch]$NoFetch
)
Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PriorLocation = Get-Location

function Run {
    param([string]$Program, [string[]]$Args = @())
    & $Program @Args
    if ($LASTEXITCODE -ne 0) { throw "Failed: $Program $($Args -join ' ')" }
}
function Capture {
    param([string]$Program, [string[]]$Args = @())
    $Result = & $Program @Args
    if ($LASTEXITCODE -ne 0) { throw "Failed: $Program $($Args -join ' ')" }
    return ((@($Result) | ForEach-Object { [string]$_ }) -join [Environment]::NewLine).Trim()
}
function CheckGit {
    $Actual = Capture "git" @("rev-parse", "--show-toplevel")
    $Expected = (Resolve-Path -LiteralPath $Root).Path
    if ([IO.Path]::GetFullPath($Actual).TrimEnd("\", "/") -ne [IO.Path]::GetFullPath($Expected).TrimEnd("\", "/")) {
        throw "Must run from Devkit checkout."
    }
    if (Capture "git" @("status", "--porcelain=v1", "--untracked-files=normal")) {
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
        throw "Container not running. Bootstrap once using .\update-devkit.ps1 -Branch $LiteBranch"
    }
    $Mounts = @(ConvertFrom-Json -InputObject (Capture "docker" @("inspect", "--format", "{{json .Mounts}}", $Container)))
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
    Run "docker" @("cp", $Source, ($Container + ":/tmp/devkit-lite-mode.py"))
    Run "docker" @("exec", "--user", "hermes", $Container, "/opt/hermes/.venv/bin/python", "/tmp/devkit-lite-mode.py", $Action)
}
function SwitchBranch {
    param([string]$Target)
    if ((Capture "git" @("branch", "--show-current")) -eq $Target) { return }
    CheckGit
    if ($Target -eq $LiteBranch -and -not $NoFetch) { Run "git" @("fetch", "--prune", $Remote) }
    & git show-ref --verify --quiet "refs/heads/$Target"
    if ($LASTEXITCODE -eq 0) {
        Run "git" @("switch", $Target)
    }
    elseif ($Target -eq $LiteBranch) {
        Run "git" @("switch", "--track", "-c", $Target, ($Remote + "/" + $Target))
    }
    else { throw "Local Standard branch missing: $Target" }
}
try {
    Set-Location -LiteralPath $Root
    foreach ($Command in @("git", "docker")) {
        if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) { throw "Missing executable: $Command" }
    }
    CheckGit
    CheckContainer
    $Current = Capture "git" @("branch", "--show-current")
    if ($Mode -eq "status") {
        Write-Host "[MODE] Branch=$Current"
        Adapter "status"
    }
    elseif ($Mode -eq "lite") {
        if ($Current -notin @($LiteBranch, $StandardBranch)) { throw "Unknown Devkit branch: $Current" }
        if ($Current -eq $LiteBranch) { Adapter "guard" }
        SwitchBranch $LiteBranch
        Adapter "apply"
        Run "docker" @("exec", "--user", "hermes", $Container, "/opt/hermes/.venv/bin/hermes", "--help")
        Write-Host "[PASS] Lite active. Start a NEW default-profile Hermes CLI session."
        Write-Host "docker exec -it --user hermes $Container /opt/hermes/.venv/bin/hermes"
    }
    else {
        if ($Current -ne $LiteBranch) { throw "Standard restore must start on the Lite branch." }
        Adapter "restore"
        SwitchBranch $StandardBranch
        Write-Host "[PASS] Standard instructions restored; shared data preserved."
        Write-Host "Run .\update-devkit.ps1 for full Standard image and profile reconciliation when needed."
    }
}
finally { Set-Location $PriorLocation }
