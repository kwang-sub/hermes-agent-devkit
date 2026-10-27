#requires -Version 5.1

<#
.SYNOPSIS
Updates the local Hermes Agent DevKit checkout, refreshes the DevKit image from
the latest Hermes Agent base image and migrates to default-only Lite before services start.

.DESCRIPTION
The script keeps the persistent hermes-data volume intact. It never runs
`docker compose down -v`, never resets local work, and only fast-forwards the
configured operational branch.

Default behavior:
1. Reject dirty/divergent checkouts; fast-forward and re-exec an updated updater.
2. Inspect the actual container mounts and generate a private Compose override.
3. Read-only migration preflight against the existing persistent mounts.
4. Build latest once. A failed build leaves the current container running.
5. Recheck, stop, recheck read-only, then recreate preserving every mount.
6. Image boot migrates default configuration before any Gateway service starts.
7. Verify mount identity, default config, live Gateway and Git publishing.
No automatic repair/recreation is attempted after a data/migration failure.

The process-local Windows Temp override is restored before the script exits.
#>

param(
    [string]$Branch = "dev",
    [string]$Remote = "origin",
    [string]$Container = "hermes-dev",
    [switch]$NoPull,
    [switch]$ForceRebuild,
    [switch]$NoRepair, # Deprecated: unsafe automatic repair is no longer performed.
    [switch]$SkipVerify,
    [switch]$SkipProfileInit, # Deprecated; cannot bypass mandatory boot migration.
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

function Restart-UpdatedUpdater {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScriptPath,
        [Parameter(Mandatory = $true)]
        [string]$BranchName,
        [Parameter(Mandatory = $true)]
        [string]$RemoteName,
        [Parameter(Mandatory = $true)]
        [string]$ContainerName,
        [switch]$ForceRebuildRequested,
        [switch]$NoRepairRequested,
        [switch]$SkipVerifyRequested,
        [switch]$SkipProfileInitRequested,
        [switch]$SkipGitHubAuthRequested
    )

    $PowerShellExecutable = if ($PSVersionTable.PSEdition -eq "Core") {
        Join-Path $PSHOME "pwsh.exe"
    }
    else {
        Join-Path $PSHOME "powershell.exe"
    }

    if (-not (Test-Path -LiteralPath $PowerShellExecutable -PathType Leaf)) {
        throw "Current PowerShell executable was not found for updater restart: $PowerShellExecutable"
    }

    $RestartArgs = @(
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $ScriptPath,
        "-Branch", $BranchName,
        "-Remote", $RemoteName,
        "-Container", $ContainerName,
        "-NoPull"
    )
    if ($ForceRebuildRequested) { $RestartArgs += "-ForceRebuild" }
    if ($NoRepairRequested) { $RestartArgs += "-NoRepair" }
    if ($SkipVerifyRequested) { $RestartArgs += "-SkipVerify" }
    if ($SkipProfileInitRequested) { $RestartArgs += "-SkipProfileInit" }
    if ($SkipGitHubAuthRequested) { $RestartArgs += "-SkipGitHubAuth" }

    Write-Host "[RESTART] update-devkit.ps1 changed during fast-forward. Re-executing the updated script with -NoPull."
    & $PowerShellExecutable @RestartArgs
    $RestartExitCode = $LASTEXITCODE
    if ($RestartExitCode -ne 0) {
        throw "Updated updater failed. ExitCode=$RestartExitCode"
    }
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


function Read-ContainerInspect {
    param([string]$Name, [switch]$AllowMissing)
    $Prior = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $Raw = & docker inspect $Name 2>$null
        $Code = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $Prior }
    if ($Code -ne 0) {
        if ($AllowMissing) {
            # A daemon failure is not proof of an absent container.
            Invoke-Native -FilePath "docker" -Arguments @("info", "--format", "{{.ServerVersion}}")
            $Names = Get-CapturedText -Output (Invoke-NativeCapture -FilePath "docker" -Arguments @("container", "ls", "-a", "--format", "{{.Names}}"))
            if (@($Names -split "`n") -contains $Name) { throw "Existing container inspection failed" }
            return $null
        }
        throw "Container inspection failed: $Name"
    }
    $Result = @(ConvertFrom-Json -InputObject (Get-CapturedText -Output $Raw))
    if ($Result.Count -ne 1) { throw "Expected exactly one container inspection result" }
    return $Result[0]
}

function Invoke-MigrationPlan {
    param([string]$Name, [string]$SkillsRoot)
    & (Join-Path $RepoRoot "init-lite.ps1") -Container $Name -Mode plan -SkillsRoot $SkillsRoot
    if ($LASTEXITCODE -ne 0) { throw "Read-only migration preflight failed; no recreation performed" }
}

function Assert-PostUpdate {
    param([object[]]$BeforeMounts, [string]$Name, [string]$SkillsRoot)
    $After = Read-ContainerInspect -Name $Name
    if (-not $After.State.Running) { throw "Container boot/migration failed; inspect Docker logs. No automatic repair." }
    if ($BeforeMounts.Count -gt 0 -and (Get-MountSignature $BeforeMounts) -cne (Get-MountSignature @($After.Mounts))) {
        throw "Mount identity changed after recreation. Do not use the container; reconcile saved mount evidence."
    }
    # Boot is asynchronous. A bounded status wait does not re-run any migration.
    $Ready = $false
    for ($Attempt=0; $Attempt -lt 30; $Attempt++) {
        $Prior=$ErrorActionPreference
        try {
            $ErrorActionPreference="SilentlyContinue"
            & docker exec --user hermes $Name /opt/hermes/.venv/bin/python /opt/devkit/bin/lite_default_profile.py status --skills-root $SkillsRoot 1>$null 2>$null
            $Code=$LASTEXITCODE
        }
        finally { $ErrorActionPreference=$Prior }
        if ($Code -eq 0) { $Ready=$true; break }
        Start-Sleep -Seconds 2
    }
    if (-not $Ready) { throw "Default Lite configuration not ready. Inspect boot migration diagnostics; automatic repair is disabled." }
    & (Join-Path $RepoRoot "init-lite.ps1") -Container $Name -Mode status -SkillsRoot $SkillsRoot
    if ($LASTEXITCODE -ne 0) { throw "Mandatory default configuration verification failed" }
}

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$OriginalLocation = Get-Location
$PreviousWindowsTempPathExists = Test-Path Env:HERMES_WINDOWS_TEMP_CONTAINER_PATH
$PreviousWindowsTempPath = if ($PreviousWindowsTempPathExists) { $env:HERMES_WINDOWS_TEMP_CONTAINER_PATH } else { $null }
$HermesBaseImage = "nousresearch/hermes-agent:latest"
$OverrideFile = $null
try {
    Set-Location $RepoRoot
    . (Join-Path $RepoRoot "scripts/devkit-mounts.ps1")
    if ($SkipProfileInit) { throw "-SkipProfileInit is retired; default boot migration cannot be skipped." }
    if ($NoRepair) { Write-Host "[INFO] Automatic repair is disabled for all Lite updates." }
    foreach ($Command in @("git","docker")) {
        if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) { throw "Missing required command: $Command" }
    }
    Invoke-Native -FilePath "docker" -Arguments @("info", "--format", "{{.ServerVersion}}")
    Invoke-Native -FilePath "docker" -Arguments @("compose", "version")
    $GitRoot=Get-CapturedText -Output (Invoke-NativeCapture -FilePath "git" -Arguments @("rev-parse","--show-toplevel"))
    if ([IO.Path]::GetFullPath($GitRoot).TrimEnd('\','/') -ne [IO.Path]::GetFullPath($RepoRoot).TrimEnd('\','/')) {
        throw "Updater must run in its own DevKit checkout"
    }
    $Dirty=Get-CapturedText -Output (Invoke-NativeCapture -FilePath "git" -Arguments @("status", "--porcelain=v1", "--untracked-files=normal"))
    if ($Dirty) { throw "DevKit has local changes; preserve/reconcile them before updating." }
    $Current=Get-CapturedText -Output (Invoke-NativeCapture -FilePath "git" -Arguments @("branch","--show-current"))
    if ($Current -cne $Branch) { throw "Expected branch $Branch; current=$Current" }
    $BeforeSha=Get-CapturedText -Output (Invoke-NativeCapture -FilePath "git" -Arguments @("rev-parse","HEAD"))
    if (-not $NoPull) {
        Invoke-Native -FilePath "git" -Arguments @("fetch", "--prune", $Remote)
        $RemoteRef="$Remote/$Branch"
        $Counts=(Get-CapturedText -Output (Invoke-NativeCapture -FilePath "git" -Arguments @("rev-list","--left-right","--count","HEAD...$RemoteRef"))) -split '\s+'
        if ($Counts.Count -ne 2 -or [int]$Counts[0] -gt 0) { throw "Local commits/divergence detected; refusing merge or rebase" }
        Invoke-Native -FilePath "git" -Arguments @("merge", "--ff-only", $RemoteRef)
    }
    $AfterSha=Get-CapturedText -Output (Invoke-NativeCapture -FilePath "git" -Arguments @("rev-parse","HEAD"))
    $ChangedFiles=@()
    if ($BeforeSha -ne $AfterSha) {
        $ChangedFiles=@(Invoke-NativeCapture -FilePath "git" -Arguments @("diff","--name-only",$BeforeSha,$AfterSha))
    }
    if (-not $NoPull -and $ChangedFiles -contains "update-devkit.ps1") {
        Restart-UpdatedUpdater -ScriptPath $MyInvocation.MyCommand.Path -BranchName $Branch -RemoteName $Remote -ContainerName $Container -ForceRebuildRequested:$ForceRebuild -NoRepairRequested:$NoRepair -SkipVerifyRequested:$SkipVerify -SkipGitHubAuthRequested:$SkipGitHubAuth
        return
    }
    if ($ChangedFiles -contains "sample.env") { Write-Warning "sample.env changed. Existing .env is intentionally not overwritten." }
    $env:HERMES_WINDOWS_TEMP_CONTAINER_PATH=Get-HermesWindowsTempContainerPath
    $ComposeArgs=@("compose","--project-directory",$RepoRoot,"-f",(Join-Path $RepoRoot "compose.yml"))
    # Never print resolved compose configuration: it contains user credentials.
    $ModelRaw=Get-CapturedText -Output (Invoke-NativeCapture -FilePath "docker" -Arguments ($ComposeArgs+@("config","--format","json")))
    $Model=ConvertFrom-Json -InputObject $ModelRaw
    if ($Model.services.hermes.container_name -cne $Container) { throw "Container selection differs from .env/Compose; reconcile before updating" }
    $SkillsRoot=[string]$Model.services.hermes.environment.HERMES_CONTAINER_CUSTOM_SKILLS_PATH
    $Existing=Read-ContainerInspect -Name $Container -AllowMissing
    $BeforeMounts=@()
    if ($null -ne $Existing) {
        $BeforeMounts=@($Existing.Mounts)
        $Override=New-PreservedMountOverride -Mounts $BeforeMounts -Workspace ([string]$Existing.Config.WorkingDir) -ComposeModel $Model
        $OverrideFile=[IO.Path]::GetTempFileName()
        [IO.File]::WriteAllText($OverrideFile,($Override | ConvertTo-Json -Depth 30),(New-Object Text.UTF8Encoding($false)))
        $ComposeArgs+=@("-f",$OverrideFile)
        Invoke-MigrationPlan -Name $Container -SkillsRoot $SkillsRoot
    }
    Invoke-Native -FilePath "docker" -Arguments ($ComposeArgs+@("config","--quiet"))
    Write-Host "[RUN] Build latest Hermes once; existing runtime remains until success"
    Invoke-Native -FilePath "docker" -Arguments ($ComposeArgs+@("build","--pull"))
    if ($null -ne $Existing) {
        Invoke-MigrationPlan -Name $Container -SkillsRoot $SkillsRoot
        # No blind kill/claim reset. Active tasks fail the readonly plan before stop.
        Invoke-Native -FilePath "docker" -Arguments @("stop","--time","30",$Container)
        # Catch a task that started between preflight and graceful stop.
        Invoke-MigrationPlan -Name $Container -SkillsRoot $SkillsRoot
    }
    Write-Host "[RUN] Recreate with preserved mounts; pre-service boot migration is mandatory"
    Invoke-Native -FilePath "docker" -Arguments ($ComposeArgs+@("up","-d","--force-recreate","--no-build"))
    Assert-PostUpdate -BeforeMounts $BeforeMounts -Name $Container -SkillsRoot $SkillsRoot
    if (-not $SkipVerify) {
        & (Join-Path $RepoRoot "scripts/verify-container-runtime.ps1") -Container $Container
        if ($LASTEXITCODE -ne 0) { throw "Runtime verification failed; no automatic repair or data rollback" }
    }
    else { Write-Warning "Extended runtime verification skipped; mount/default safety checks still ran." }
    Write-Host "[RUN] Git publish identity/auth bootstrap"
    $GitState=Initialize-GitPublishing -ContainerName $Container -SkipAuthentication:$SkipGitHubAuth
    Write-Host "[PASS] Lite DevKit update completed"
    Write-Host "UPDATED_FROM=$BeforeSha"
    Write-Host "UPDATED_TO=$AfterSha"
    Write-Host "LITE_DEFAULT_RECONCILED=true"
    Write-Host "AUTOMATIC_REPAIR_USED=false"
    Write-Host "GIT_IDENTITY_CONFIGURED=$($GitState.IdentityConfigured)"
    Write-Host "GITHUB_AUTH_READY=$($GitState.GitHubAuthReady)"
}
finally {
    # Only our generated temporary override is removed, never a source or data mount.
    if ($OverrideFile -and (Test-Path -LiteralPath $OverrideFile)) { Remove-Item -LiteralPath $OverrideFile -Force }
    if ($PreviousWindowsTempPathExists) { $env:HERMES_WINDOWS_TEMP_CONTAINER_PATH=$PreviousWindowsTempPath }
    else { Remove-Item Env:HERMES_WINDOWS_TEMP_CONTAINER_PATH -ErrorAction SilentlyContinue }
    Set-Location $OriginalLocation
}
