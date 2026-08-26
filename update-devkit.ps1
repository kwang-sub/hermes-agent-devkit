#requires -Version 5.1

<#
.SYNOPSIS
Updates the local Hermes Agent DevKit checkout and applies only the runtime work
required by the files that changed.

.DESCRIPTION
The script keeps the persistent hermes-data volume intact. It never runs
`docker compose down -v`, never resets local work, and only fast-forwards the
configured operational branch.

Default behavior:
1. Refuse to run on a dirty DevKit checkout.
2. Fetch the remote and fast-forward the current branch.
3. Classify changed files.
4. Build the image only for image-build inputs.
5. Force-recreate the container for Compose/runtime contract changes.
6. Leave bind-mounted custom-skills/shared-only updates in place without a build.
7. Verify the running container contract.
8. If verification fails, perform one normal cached rebuild + recreate repair and
   verify once more unless -NoRepair is specified.
#>

param(
    [string]$Branch = "dev",
    [string]$Remote = "origin",
    [string]$Container = "hermes-dev",
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
    Write-Host "Before : $BeforeSha"
    Write-Host "After  : $AfterSha"
    if ($ChangedFiles.Count -eq 0) {
        Write-Host "Changes: none"
    }
    else {
        Write-Host "Changes: $($ChangedFiles.Count) file(s)"
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

    $BuildRequired = $ForceRebuild.IsPresent -or
        (Test-AnyPathMatch -Paths $ChangedFiles -ExactPaths $ImageBuildInputs)
    $RecreateRequired = $BuildRequired -or ($ChangedFiles -contains "compose.yml")

    if (-not $BuildRequired -and $ChangedFiles -contains "compose.yml" -and $BeforeSha -ne $AfterSha) {
        $ComposeDiff = Get-CapturedText -Output (Invoke-NativeCapture -FilePath "git" -Arguments @(
            "diff", "--unified=0", $BeforeSha, $AfterSha, "--", "compose.yml"
        ))
        if ($ComposeDiff -match '(?m)^[+-].*HERMES_BASE_IMAGE') {
            $BuildRequired = $true
            $RecreateRequired = $true
        }
    }

    $BindMountedOnly = $false
    if ($ChangedFiles.Count -gt 0 -and -not $BuildRequired -and -not $RecreateRequired) {
        $RuntimeRelevant = @($ChangedFiles | Where-Object {
            $_ -like "custom-skills/*" -or $_ -like "shared/*"
        })
        $BindMountedOnly = $RuntimeRelevant.Count -gt 0
    }

    if ($BuildRequired) {
        Write-Host "Action  : build + force-recreate"
    }
    elseif ($RecreateRequired) {
        Write-Host "Action  : force-recreate"
    }
    elseif ($BindMountedOnly) {
        Write-Host "Action  : bind-mounted content is already live; no build required"
    }
    else {
        Write-Host "Action  : no image/container contract change detected"
    }

    if ($ChangedFiles -contains "sample.env") {
        Write-Warning "sample.env changed. Existing .env is intentionally not overwritten; review the new sample manually."
    }
    if ($ChangedFiles -contains "init-profiles.ps1") {
        Write-Warning "init-profiles.ps1 changed. Profile initialization is intentionally not run automatically; execute .\init-profiles.ps1 after this update if the profile contract changed."
    }

    Invoke-Native -FilePath "docker" -Arguments @("compose", "config", "--quiet")

    if ($BuildRequired) {
        Write-Host "[RUN ] docker compose build"
        Invoke-Native -FilePath "docker" -Arguments @("compose", "build")
        $ImageRebuilt = $true
        Write-Host "[RUN ] docker compose up -d --force-recreate"
        Invoke-Native -FilePath "docker" -Arguments @("compose", "up", "-d", "--force-recreate")
        $ContainerRecreated = $true
    }
    elseif ($RecreateRequired) {
        Write-Host "[RUN ] docker compose up -d --force-recreate"
        Invoke-Native -FilePath "docker" -Arguments @("compose", "up", "-d", "--force-recreate")
        $ContainerRecreated = $true
    }
    elseif (-not (Test-ContainerRunning -Name $Container)) {
        Write-Host "[RUN ] Container is missing/stopped; docker compose up -d"
        Invoke-Native -FilePath "docker" -Arguments @("compose", "up", "-d")
    }
    else {
        Write-Host "[OK] Container is already running; runtime recreation not required."
    }

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
    Write-Host "IMAGE_REBUILT=$($ImageRebuilt.ToString().ToLowerInvariant())"
    Write-Host "CONTAINER_RECREATED=$($ContainerRecreated.ToString().ToLowerInvariant())"
    Write-Host "AUTOMATIC_REPAIR_USED=$($AutomaticRepairUsed.ToString().ToLowerInvariant())"
}
finally {
    Set-Location $OriginalLocation
}
