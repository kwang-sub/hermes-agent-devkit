#requires -Version 5.1

<#
.SYNOPSIS
Updates the local Hermes Agent DevKit checkout, refreshes the DevKit image from
the latest Hermes Agent base image, and recreates the runtime safely.

.DESCRIPTION
The script keeps the persistent hermes-data volume intact. It never runs
`docker compose down -v`, never resets local work, and only fast-forwards the
configured operational branch.

Default behavior:
1. Refuse to run on a dirty DevKit checkout.
2. Fetch the remote and fast-forward the current branch.
3. Classify changed files for warnings and runtime context.
4. Temporarily override HERMES_BASE_IMAGE with nousresearch/hermes-agent:latest.
5. Build with `docker compose build --pull` so the latest Hermes base image is checked.
6. Force-recreate the container only after the build succeeds.
7. Keep the existing hermes-data volume and profile/OAuth/session state intact.
8. Verify the running container contract.
9. If verification fails, perform one normal cached rebuild + recreate repair and
   verify once more unless -NoRepair is specified.

The HERMES_BASE_IMAGE override is process-local and restored before the script exits,
so normal `docker compose up` continues to use the version configured in .env.
#>

param(
    [string]$Branch = "dev",
    [string]$Remote = "origin",
    [string]$Container = "hermes-dev",
    [string]$HermesBaseImage = "nousresearch/hermes-agent:latest",
    [switch]$NoPull,
    [switch]$ForceRebuild,
    [switch]$NoRepair,
    [switch]$SkipVerify
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [string[]]$Arguments = @()
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed. ExitCode=$LASTEXITCODE Command=$FilePath $($Arguments -join ' ')"
    }
}

function Invoke-NativeCapture {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [string[]]$Arguments = @()
    )

    $Output = & $FilePath @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        $Detail = (@($Output) -join [Environment]::NewLine).Trim()
        throw "Command failed. ExitCode=$LASTEXITCODE Command=$FilePath $($Arguments -join ' ')`n$Detail"
    }
    return @($Output)
}

function Get-CapturedText {
    param(
        [AllowNull()]
        [object]$Output
    )

    if ($null -eq $Output) {
        return ""
    }

    return ((@($Output) | ForEach-Object { [string]$_ }) -join [Environment]::NewLine).Trim()
}

function Test-AnyPathMatch {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [string[]]$Paths,
        [Parameter(Mandatory = $true)]
        [string[]]$ExactPaths
    )

    foreach ($Path in $Paths) {
        if ($ExactPaths -contains $Path) {
            return $true
        }
    }
    return $false
}

function Test-ContainerRunning {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $PreviousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $Output = & docker inspect --format "{{.State.Running}}" $Name 2>$null
        $ExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $PreviousPreference
    }

    if ($ExitCode -ne 0) {
        return $false
    }

    return (Get-CapturedText -Output $Output).ToLowerInvariant() -eq "true"
}

function Invoke-RuntimeVerification {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Verifier,
        [Parameter(Mandatory = $true)]
        [string]$ContainerName
    )

    try {
        & $Verifier -Container $ContainerName
        return $true
    }
    catch {
        Write-Warning $_.Exception.Message
        return $false
    }
}

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$OriginalLocation = Get-Location
$ImageRebuilt = $false
$ContainerRecreated = $false
$AutomaticRepairUsed = $false
$PreviousHermesBaseImageExists = Test-Path Env:HERMES_BASE_IMAGE
$PreviousHermesBaseImage = if ($PreviousHermesBaseImageExists) { $env:HERMES_BASE_IMAGE } else { $null }

try {
    Set-Location $RepoRoot

    foreach ($Command in @("git", "docker")) {
        if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) {
            throw "Required command was not found: $Command"
        }
    }

    Invoke-Native -FilePath "docker" -Arguments @("info")
    Invoke-Native -FilePath "docker" -Arguments @("compose", "version")

    $ResolvedRepoRoot = Get-CapturedText -Output (Invoke-NativeCapture -FilePath "git" -Arguments @("rev-parse", "--show-toplevel"))
    $ExpectedRepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
    if ([System.IO.Path]::GetFullPath($ResolvedRepoRoot).TrimEnd('\', '/') -ne
        [System.IO.Path]::GetFullPath($ExpectedRepoRoot).TrimEnd('\', '/')) {
        throw "update-devkit.ps1 must be run from its own DevKit repository. GitRoot=$ResolvedRepoRoot ScriptRoot=$ExpectedRepoRoot"
    }

    $Dirty = Get-CapturedText -Output (Invoke-NativeCapture -FilePath "git" -Arguments @("status", "--porcelain=v1", "--untracked-files=normal"))
    if (-not [string]::IsNullOrWhiteSpace($Dirty)) {
        throw "DevKit checkout has local changes. Commit/stash them before updating.`n$Dirty"
    }

    $CurrentBranch = Get-CapturedText -Output (Invoke-NativeCapture -FilePath "git" -Arguments @("branch", "--show-current"))
    if ($CurrentBranch -ne $Branch) {
        throw "Current branch is '$CurrentBranch'. Switch to '$Branch' before running the updater."
    }

    $BeforeSha = Get-CapturedText -Output (Invoke-NativeCapture -FilePath "git" -Arguments @("rev-parse", "HEAD"))
    $AfterSha = $BeforeSha

    if (-not $NoPull) {
        Write-Host "[RUN ] Fetch $Remote/$Branch"
        Invoke-Native -FilePath "git" -Arguments @("fetch", "--prune", $Remote)

        $RemoteRef = "$Remote/$Branch"
        Invoke-NativeCapture -FilePath "git" -Arguments @("rev-parse", "--verify", "$RemoteRef^{commit}") | Out-Null

        $CountsText = Get-CapturedText -Output (Invoke-NativeCapture -FilePath "git" -Arguments @("rev-list", "--left-right", "--count", "HEAD...$RemoteRef"))
        $Counts = @($CountsText -split '\s+' | Where-Object { $_ -ne "" })
        if ($Counts.Count -ne 2) {
            throw "Unexpected git divergence output: $CountsText"
        }

        $LocalOnly = [int]$Counts[0]
        $RemoteOnly = [int]$Counts[1]
        if ($LocalOnly -gt 0) {
            throw "Local '$Branch' contains $LocalOnly commit(s) not present in $RemoteRef. Refusing automatic merge/rebase."
        }

        if ($RemoteOnly -gt 0) {
            Write-Host "[RUN ] Fast-forward $Branch by $RemoteOnly commit(s)"
            Invoke-Native -FilePath "git" -Arguments @("merge", "--ff-only", $RemoteRef)
        }
        else {
            Write-Host "[OK] Repository already up to date."
        }

        $AfterSha = Get-CapturedText -Output (Invoke-NativeCapture -FilePath "git" -Arguments @("rev-parse", "HEAD"))
    }
    else {
        Write-Host "[SKIP] Git pull disabled by -NoPull."
    }

    $ChangedFiles = @()
    if ($BeforeSha -ne $AfterSha) {
        $ChangedFiles = @(
            Invoke-NativeCapture -FilePath "git" -Arguments @("diff", "--name-only", $BeforeSha, $AfterSha) |
                ForEach-Object { ([string]$_).Trim() } |
                Where-Object { $_ -ne "" }
        )
    }

    Write-Host ""
    Write-Host "== DevKit update plan =="
    Write-Host "Before            : $BeforeSha"
    Write-Host "After             : $AfterSha"
    Write-Host "Hermes base image : $HermesBaseImage"
    if ($ChangedFiles.Count -eq 0) {
        Write-Host "Changes           : none"
    }
    else {
        Write-Host "Changes           : $($ChangedFiles.Count) file(s)"
        foreach ($ChangedFile in $ChangedFiles) {
            Write-Host "  - $ChangedFile"
        }
    }

    $ImageBuildInputs = @(
        "Dockerfile",
        ".dockerignore",
        "scripts/hermes-java",
        "scripts/patch_hermes_syntax_warning.py"
    )

    # update-devkit.ps1 is the explicit Hermes upgrade boundary. Even when the
    # DevKit Git checkout did not change, running this script must check and use
    # the newest Hermes base image before recreating the runtime.
    $BuildRequired = $true
    $RecreateRequired = $true

    if ($ChangedFiles -contains "sample.env") {
        Write-Warning "sample.env changed. Existing .env is intentionally not overwritten; review the new sample manually."
    }
    if ($ChangedFiles -contains "init-profiles.ps1") {
        Write-Warning "init-profiles.ps1 changed. Profile initialization is intentionally not run automatically; execute .\init-profiles.ps1 after this update if the profile contract changed."
    }

    # Process environment overrides values loaded from .env by Docker Compose.
    # This makes the updater follow latest while normal compose commands remain
    # pinned to the version configured by the user.
    $env:HERMES_BASE_IMAGE = $HermesBaseImage

    Write-Host "Action            : pull latest Hermes base + build + force-recreate"
    Invoke-Native -FilePath "docker" -Arguments @("compose", "config", "--quiet")

    Write-Host "[RUN ] docker compose build --pull"
    Invoke-Native -FilePath "docker" -Arguments @("compose", "build", "--pull")
    $ImageRebuilt = $true

    Write-Host "[RUN ] docker compose up -d --force-recreate"
    Invoke-Native -FilePath "docker" -Arguments @("compose", "up", "-d", "--force-recreate")
    $ContainerRecreated = $true

    if ($SkipVerify) {
        Write-Host "[SKIP] Runtime verification disabled by -SkipVerify."
    }
    else {
        $Verifier = Join-Path $RepoRoot "scripts\verify-container-runtime.ps1"
        if (-not (Test-Path -LiteralPath $Verifier -PathType Leaf)) {
            throw "Runtime verifier is missing: $Verifier"
        }

        Write-Host "[RUN ] Runtime verification"
        $Verified = Invoke-RuntimeVerification -Verifier $Verifier -ContainerName $Container
        if (-not $Verified) {
            if ($NoRepair) {
                throw "Runtime verification failed and automatic repair is disabled by -NoRepair."
            }

            Write-Warning "Runtime verification failed. Performing one cached rebuild + force-recreate repair."
            $AutomaticRepairUsed = $true
            Invoke-Native -FilePath "docker" -Arguments @("compose", "build")
            $ImageRebuilt = $true
            Invoke-Native -FilePath "docker" -Arguments @("compose", "up", "-d", "--force-recreate")
            $ContainerRecreated = $true

            Write-Host "[RUN ] Runtime verification after repair"
            if (-not (Invoke-RuntimeVerification -Verifier $Verifier -ContainerName $Container)) {
                throw "Runtime verification still fails after one automatic repair. Inspect the verifier output before using the DevKit."
            }
        }
    }

    Write-Host ""
    Write-Host "[PASS] DevKit update completed."
    Write-Host "UPDATED_FROM=$BeforeSha"
    Write-Host "UPDATED_TO=$AfterSha"
    Write-Host "HERMES_BASE_IMAGE=$HermesBaseImage"
    Write-Host "IMAGE_REBUILT=$($ImageRebuilt.ToString().ToLowerInvariant())"
    Write-Host "CONTAINER_RECREATED=$($ContainerRecreated.ToString().ToLowerInvariant())"
    Write-Host "AUTOMATIC_REPAIR_USED=$($AutomaticRepairUsed.ToString().ToLowerInvariant())"
}
finally {
    if ($PreviousHermesBaseImageExists) {
        $env:HERMES_BASE_IMAGE = $PreviousHermesBaseImage
    }
    else {
        Remove-Item Env:HERMES_BASE_IMAGE -ErrorAction SilentlyContinue
    }
    Set-Location $OriginalLocation
}
