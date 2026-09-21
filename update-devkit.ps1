#requires -Version 5.1

<#
.SYNOPSIS
Updates the local Hermes Agent DevKit checkout, refreshes the DevKit image from
the pinned stable Hermes Agent base image, recreates the runtime, and reconciles profiles.

.DESCRIPTION
The script keeps the persistent hermes-data volume intact. It never runs
`docker compose down -v`, never resets local work, and only fast-forwards the
configured operational branch.

Default behavior:
1. Refuse to run on a dirty DevKit checkout.
2. Fetch the remote and fast-forward the current branch.
3. Classify changed files for warnings and runtime context.
4. Derive the Hermes-visible Windows Temp path from LOCALAPPDATA.
5. Temporarily override HERMES_BASE_IMAGE with nousresearch/hermes-agent:v2026.9.14.
6. Build with `docker compose build --pull` so the pinned stable Hermes base image is refreshed.
7. Force-recreate the container only after the build succeeds.
8. Keep the existing hermes-data volume and profile/OAuth/session state intact.
9. Run init-profiles.ps1 to reconcile the role profile and skill contract.
10. Ensure the default multiplex Gateway is running.
11. Verify the running container contract.
12. If verification fails, perform one normal cached rebuild + recreate repair,
    reconcile profiles and the default Gateway again, then verify once more unless -NoRepair is specified.
13. Re-apply Git commit identity from .env and ensure persistent GitHub CLI auth.

The process-local overrides are restored before the script exits.
#>

param(
    [string]$Branch = "dev",
    [string]$Remote = "origin",
    [string]$Container = "hermes-dev",
    [string]$HermesBaseImage = "nousresearch/hermes-agent:v2026.9.14",
    [switch]$NoPull,
    [switch]$ForceRebuild,
    [switch]$NoRepair,
    [switch]$SkipVerify,
    [switch]$SkipProfileInit,
    [switch]$SkipGitHubAuth
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

function Get-HermesWindowsTempContainerPath {
    $LocalAppData = [Environment]::GetEnvironmentVariable("LOCALAPPDATA", "Process")
    if ([string]::IsNullOrWhiteSpace($LocalAppData)) {
        throw "LOCALAPPDATA is not defined. Cannot derive the Windows Temp mount path."
    }

    $Normalized = $LocalAppData.TrimEnd('\', '/')
    if ($Normalized -notmatch '^([A-Za-z]):[\\/](.+)$') {
        throw "Unsupported LOCALAPPDATA path: $LocalAppData"
    }

    $Drive = $Matches[1].ToLowerInvariant()
    $Tail = ($Matches[2] -replace '\\', '/').Trim('/')
    return "/mnt/$Drive/$Tail/Temp"
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

function Get-ContainerEnvValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ContainerName,
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $PreviousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $Output = & docker exec --user hermes $ContainerName printenv $Name 2>$null
        $ExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $PreviousPreference
    }

    if ($ExitCode -ne 0) {
        return ""
    }
    return Get-CapturedText -Output $Output
}

function Test-GitHubAuthentication {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ContainerName
    )

    $PreviousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $Output = & docker exec --user hermes $ContainerName gh auth status --hostname github.com 2>&1
        $ExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $PreviousPreference
    }

    return [pscustomobject]@{
        Ready = ($ExitCode -eq 0)
        Detail = Get-CapturedText -Output $Output
    }
}

function Initialize-GitPublishing {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ContainerName,
        [switch]$SkipAuthentication
    )

    $GitUserName = Get-ContainerEnvValue -ContainerName $ContainerName -Name "HERMES_GIT_USER_NAME"
    $GitUserEmail = Get-ContainerEnvValue -ContainerName $ContainerName -Name "HERMES_GIT_USER_EMAIL"
    $GhConfigDir = Get-ContainerEnvValue -ContainerName $ContainerName -Name "GH_CONFIG_DIR"

    if ([string]::IsNullOrWhiteSpace($GitUserName) -or [string]::IsNullOrWhiteSpace($GitUserEmail)) {
        throw "Git publish identity is not configured. Set HERMES_GIT_USER_NAME and HERMES_GIT_USER_EMAIL in .env, then re-run .\update-devkit.ps1."
    }
    if ([string]::IsNullOrWhiteSpace($GhConfigDir)) {
        throw "GH_CONFIG_DIR is not configured in the running container. Rebuild from the current compose.yml."
    }

    Invoke-Native -FilePath "docker" -Arguments @(
        "exec", "--user", "hermes", $ContainerName,
        "/usr/local/bin/git", "config", "--global", "user.name", $GitUserName
    )
    Invoke-Native -FilePath "docker" -Arguments @(
        "exec", "--user", "hermes", $ContainerName,
        "/usr/local/bin/git", "config", "--global", "user.email", $GitUserEmail
    )

    $ResolvedName = Get-CapturedText -Output (Invoke-NativeCapture -FilePath "docker" -Arguments @(
        "exec", "--user", "hermes", $ContainerName,
        "/usr/local/bin/git", "config", "--global", "--get", "user.name"
    ))
    $ResolvedEmail = Get-CapturedText -Output (Invoke-NativeCapture -FilePath "docker" -Arguments @(
        "exec", "--user", "hermes", $ContainerName,
        "/usr/local/bin/git", "config", "--global", "--get", "user.email"
    ))

    if ($ResolvedName -ne $GitUserName -or $ResolvedEmail -ne $GitUserEmail) {
        throw "Git publish identity verification failed after applying .env values."
    }

    Write-Host "[OK] Git commit identity -> $ResolvedName <$ResolvedEmail>"
    Write-Host "[OK] GitHub CLI config -> $GhConfigDir"

    if ($SkipAuthentication) {
        Write-Host "[SKIP] GitHub CLI authentication check disabled by -SkipGitHubAuth."
        return [pscustomobject]@{
            IdentityConfigured = $true
            GitHubAuthReady = $false
        }
    }

    $Auth = Test-GitHubAuthentication -ContainerName $ContainerName
    if (-not $Auth.Ready) {
        Write-Host "[AUTH] GitHub CLI authentication is missing. Starting interactive device login."
        Write-Host "[AUTH] Credentials will be stored under $GhConfigDir on the persistent hermes-data volume."
        Invoke-Native -FilePath "docker" -Arguments @(
            "exec", "-it", "--user", "hermes", $ContainerName,
            "gh", "auth", "login",
            "--hostname", "github.com",
            "--git-protocol", "https",
            "--web"
        )

        $Auth = Test-GitHubAuthentication -ContainerName $ContainerName
        if (-not $Auth.Ready) {
            throw "GitHub CLI authentication is still unavailable after interactive login.`n$($Auth.Detail)"
        }
    }

    Write-Host "[OK] GitHub CLI authentication -> github.com"
    return [pscustomobject]@{
        IdentityConfigured = $true
        GitHubAuthReady = $true
    }
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

function Invoke-ProfileInitialization {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Initializer,
        [Parameter(Mandatory = $true)]
        [string]$ContainerName
    )

    $PreviousContainerExists = Test-Path Env:HERMES_CONTAINER_NAME
    $PreviousContainer = if ($PreviousContainerExists) { $env:HERMES_CONTAINER_NAME } else { $null }
    try {
        $env:HERMES_CONTAINER_NAME = $ContainerName
        & $Initializer
        if ($LASTEXITCODE -ne 0) {
            throw "Profile initialization failed. ExitCode=$LASTEXITCODE"
        }
    }
    finally {
        if ($PreviousContainerExists) {
            $env:HERMES_CONTAINER_NAME = $PreviousContainer
        }
        else {
            Remove-Item Env:HERMES_CONTAINER_NAME -ErrorAction SilentlyContinue
        }
    }
}

function Ensure-DefaultMultiplexGateway {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ContainerName
    )

    Write-Host "[RUN ] Ensure default multiplex Gateway is running"
    Invoke-Native -FilePath "docker" -Arguments @(
        "exec", "--user", "hermes", $ContainerName,
        "/opt/hermes/.venv/bin/hermes", "gateway", "start"
    )
}

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$OriginalLocation = Get-Location
$ImageRebuilt = $false
$ContainerRecreated = $false
$ProfilesReconciled = $false
$AutomaticRepairUsed = $false
$GitIdentityConfigured = $false
$GitHubAuthReady = $false
$PreviousHermesBaseImageExists = Test-Path Env:HERMES_BASE_IMAGE
$PreviousHermesBaseImage = if ($PreviousHermesBaseImageExists) { $env:HERMES_BASE_IMAGE } else { $null }
$PreviousWindowsTempPathExists = Test-Path Env:HERMES_WINDOWS_TEMP_CONTAINER_PATH
$PreviousWindowsTempPath = if ($PreviousWindowsTempPathExists) { $env:HERMES_WINDOWS_TEMP_CONTAINER_PATH } else { $null }

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

    $WindowsTempContainerPath = Get-HermesWindowsTempContainerPath

    Write-Host ""
    Write-Host "== DevKit update plan =="
    Write-Host "Before            : $BeforeSha"
    Write-Host "After             : $AfterSha"
    Write-Host "Hermes base image : $HermesBaseImage"
    Write-Host "Windows temp      : $WindowsTempContainerPath"
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

    $BuildRequired = $true
    $RecreateRequired = $true

    if ($ChangedFiles -contains "sample.env") {
        Write-Warning "sample.env changed. Existing .env is intentionally not overwritten; review the new sample manually."
    }

    $env:HERMES_BASE_IMAGE = $HermesBaseImage
    $env:HERMES_WINDOWS_TEMP_CONTAINER_PATH = $WindowsTempContainerPath

    Write-Host "Action            : pull pinned Hermes v2026.9.14 base + build + force-recreate + profile reconcile"
    Invoke-Native -FilePath "docker" -Arguments @("compose", "config", "--quiet")

    Write-Host "[RUN ] docker compose build --pull"
    Invoke-Native -FilePath "docker" -Arguments @("compose", "build", "--pull")
    $ImageRebuilt = $true

    Write-Host "[RUN ] docker compose up -d --force-recreate"
    Invoke-Native -FilePath "docker" -Arguments @("compose", "up", "-d", "--force-recreate")
    $ContainerRecreated = $true

    $ProfileInitializer = Join-Path $RepoRoot "init-profiles.ps1"
    if (-not $SkipProfileInit) {
        if (-not (Test-Path -LiteralPath $ProfileInitializer -PathType Leaf)) {
            throw "Profile initializer is missing: $ProfileInitializer"
        }
        Write-Host "[RUN ] Profile/skill reconciliation"
        Invoke-ProfileInitialization -Initializer $ProfileInitializer -ContainerName $Container
        $ProfilesReconciled = $true
    }
    else {
        Write-Host "[SKIP] Profile initialization disabled by -SkipProfileInit."
    }

    Ensure-DefaultMultiplexGateway -ContainerName $Container

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

            if (-not $SkipProfileInit) {
                Write-Host "[RUN ] Profile/skill reconciliation after repair"
                Invoke-ProfileInitialization -Initializer $ProfileInitializer -ContainerName $Container
                $ProfilesReconciled = $true
            }

            Ensure-DefaultMultiplexGateway -ContainerName $Container

            Write-Host "[RUN ] Runtime verification after repair"
            if (-not (Invoke-RuntimeVerification -Verifier $Verifier -ContainerName $Container)) {
                throw "Runtime verification still fails after one automatic repair. Inspect the verifier output before using the DevKit."
            }
        }
    }

    Write-Host "[RUN ] Git publish identity/auth bootstrap"
    $GitPublishState = Initialize-GitPublishing -ContainerName $Container -SkipAuthentication:$SkipGitHubAuth
    $GitIdentityConfigured = [bool]$GitPublishState.IdentityConfigured
    $GitHubAuthReady = [bool]$GitPublishState.GitHubAuthReady

    Write-Host ""
    Write-Host "[PASS] DevKit update completed."
    Write-Host "UPDATED_FROM=$BeforeSha"
    Write-Host "UPDATED_TO=$AfterSha"
    Write-Host "HERMES_BASE_IMAGE=$HermesBaseImage"
    Write-Host "HERMES_WINDOWS_TEMP_CONTAINER_PATH=$WindowsTempContainerPath"
    Write-Host "IMAGE_REBUILT=$($ImageRebuilt.ToString().ToLowerInvariant())"
    Write-Host "CONTAINER_RECREATED=$($ContainerRecreated.ToString().ToLowerInvariant())"
    Write-Host "PROFILES_RECONCILED=$($ProfilesReconciled.ToString().ToLowerInvariant())"
    Write-Host "AUTOMATIC_REPAIR_USED=$($AutomaticRepairUsed.ToString().ToLowerInvariant())"
    Write-Host "GIT_IDENTITY_CONFIGURED=$($GitIdentityConfigured.ToString().ToLowerInvariant())"
    Write-Host "GITHUB_AUTH_READY=$($GitHubAuthReady.ToString().ToLowerInvariant())"
}
finally {
    if ($PreviousHermesBaseImageExists) {
        $env:HERMES_BASE_IMAGE = $PreviousHermesBaseImage
    }
    else {
        Remove-Item Env:HERMES_BASE_IMAGE -ErrorAction SilentlyContinue
    }

    if ($PreviousWindowsTempPathExists) {
        $env:HERMES_WINDOWS_TEMP_CONTAINER_PATH = $PreviousWindowsTempPath
    }
    else {
        Remove-Item Env:HERMES_WINDOWS_TEMP_CONTAINER_PATH -ErrorAction SilentlyContinue
    }

    Set-Location $OriginalLocation
}
