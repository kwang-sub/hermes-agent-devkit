#requires -Version 5.1
<#
.SYNOPSIS
Apply/restore Hermes Lite with the existing container and persistent data.
.DESCRIPTION
No Git branch switch, Docker rebuild/recreation, volume deletion, or Kanban mutation.
-SelfTest runs real Git argv tests; -MountSelfTest checks synthetic Docker inspect
mounts without accessing Docker or modifying files.
#>
[CmdletBinding()]
param(
    [ValidateSet("lite","standard","status")]
    [string]$Mode = "lite",
    [string]$Container = "hermes-dev",
    [switch]$SelfTest,
    [switch]$MountSelfTest
)
Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PriorLocation = Get-Location

function Invoke-Checked {
    param([Parameter(Mandatory=$true)][string]$Program, [string[]]$Arguments=@())
    & $Program @Arguments
    $Code = $LASTEXITCODE
    if ($Code -ne 0) {
        throw "Command failed (exit $Code): $Program $($Arguments -join ' ')"
    }
}
function Capture-Checked {
    param([Parameter(Mandatory=$true)][string]$Program, [string[]]$Arguments=@())
    $Output = & $Program @Arguments
    $Code = $LASTEXITCODE
    if ($Code -ne 0) {
        throw "Command failed (exit $Code): $Program $($Arguments -join ' ')"
    }
    return ((@($Output) | ForEach-Object { [string]$_ }) -join [Environment]::NewLine).Trim()
}
function Assert-DevkitCheckout {
    $GitRoot = Capture-Checked -Program "git" -Arguments @("rev-parse","--show-toplevel")
    $Expected = (Resolve-Path -LiteralPath $Root).Path
    if ([IO.Path]::GetFullPath($GitRoot).TrimEnd("\","/") -ne
        [IO.Path]::GetFullPath($Expected).TrimEnd("\","/")) {
        throw "Updater must run from its own Devkit checkout: $GitRoot"
    }
    # No dirty checkout restriction: this script NEVER performs git checkout.
}
function Parse-MountJson {
    param([Parameter(Mandatory=$true)][string]$Json)
    if ([string]::IsNullOrWhiteSpace($Json)) {
        throw "Docker inspect returned empty mount JSON"
    }
    try { $Decoded = ConvertFrom-Json -InputObject $Json -ErrorAction Stop }
    catch { throw "Cannot decode Docker mount JSON: $($_.Exception.Message)" }

    # Windows PowerShell 5.1 can wrap the parsed JSON array one level deeper.
    # Flatten explicitly instead of assuming @(... ConvertFrom-Json ...) is flat.
    $Flat = New-Object System.Collections.ArrayList
    foreach ($Entry in @($Decoded)) {
        if ($Entry -is [System.Array]) {
            foreach ($Child in $Entry) { [void]$Flat.Add($Child) }
        }
        else { [void]$Flat.Add($Entry) }
    }
    if ($Flat.Count -eq 0) { throw "Existing container has no Docker mounts" }
    foreach ($Entry in $Flat) {
        if ($null -eq $Entry -or
            $null -eq $Entry.PSObject.Properties["Destination"] -or
            $null -eq $Entry.PSObject.Properties["Type"]) {
            throw "Invalid Docker mount JSON item: Type or Destination absent"
        }
    }
    return ,($Flat.ToArray())
}
function Require-Mount {
    param(
        [Parameter(Mandatory=$true)][object[]]$Mounts,
        [Parameter(Mandatory=$true)][string]$Target,
        [Parameter(Mandatory=$true)][string[]]$AllowedTypes,
        [switch]$Writable
    )
    $Found = @($Mounts | Where-Object { [string]$_.Destination -ceq $Target })
    if ($Found.Count -ne 1) {
        $Observed = (@($Mounts | ForEach-Object { "$($_.Destination)[$($_.Type)]" }) -join ", ")
        throw "Expected one mount at '$Target'; found $($Found.Count). Observed=$Observed"
    }
    $Mount = $Found[0]
    $Type = ([string]$Mount.Type).Trim().ToLowerInvariant()
    if ($AllowedTypes -notcontains $Type) {
        throw "Unsupported mount Type='$Type' at '$Target'; expected=$($AllowedTypes -join '|'); Source='$($Mount.Source)'"
    }
    if ($null -eq $Mount.PSObject.Properties["Source"] -or
        [string]::IsNullOrWhiteSpace([string]$Mount.Source)) {
        throw "Mount at '$Target' has no persistent Source"
    }
    if ($Type -eq "volume" -and
        ($null -eq $Mount.PSObject.Properties["Name"] -or
         [string]::IsNullOrWhiteSpace([string]$Mount.Name))) {
        throw "Volume at '$Target' has no volume Name"
    }
    if ($Writable -and
        ($null -eq $Mount.PSObject.Properties["RW"] -or
         $Mount.RW -isnot [bool] -or
         -not $Mount.RW)) {
        throw "Mount at '$Target' is read-only or RW is unknown"
    }
    return $Mount
}
function Check-MountContract {
    param([object[]]$Mounts, [string]$WorkspaceTarget)
    $Data = Require-Mount -Mounts $Mounts -Target "/opt/data" -AllowedTypes @("volume","bind") -Writable
    $Workspace = Require-Mount -Mounts $Mounts -Target $WorkspaceTarget -AllowedTypes @("bind") -Writable
    $Skills = Require-Mount -Mounts $Mounts -Target "/opt/custom-skills" -AllowedTypes @("bind")
    $Shared = Require-Mount -Mounts $Mounts -Target "/opt/data/shared" -AllowedTypes @("bind")
    return [pscustomobject]@{
        DataType = ([string]$Data.Type).ToLowerInvariant()
        DataSource = [string]$Data.Source
        DataVolume = if ([string]$Data.Type -eq "volume") { [string]$Data.Name } else { "" }
        Workspace = $WorkspaceTarget
    }
}
function Check-ExistingContainer {
    param([string]$Name, [switch]$RequireLiteFiles)
    $Preference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $Running = & docker inspect --format "{{.State.Running}}" $Name 2>$null
        $Code = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $Preference }
    if ($Code -ne 0 -or (@($Running) -join "").Trim().ToLowerInvariant() -ne "true") {
        throw "Container '$Name' is not running. Bootstrap with .\update-devkit.ps1 -Branch dev"
    }
    $Json = Capture-Checked -Program "docker" -Arguments @("inspect","--format","{{json .Mounts}}",$Name)
    $Workspace = Capture-Checked -Program "docker" -Arguments @("inspect","--format","{{.Config.WorkingDir}}",$Name)
    if ([string]::IsNullOrWhiteSpace($Workspace) -or $Workspace[0] -ne "/") {
        throw "Docker container has an invalid WorkingDir: '$Workspace'"
    }
    $Contract = Check-MountContract -Mounts (Parse-MountJson -Json $Json) -WorkspaceTarget $Workspace
    # Docker reports the mount as writable, but Windows host permissions still
    # require a read-only probe as the actual Hermes user.
    Invoke-Checked -Program "docker" -Arguments @("exec","--user","hermes",$Name,"test","-w","/opt/data")
    $LiteDir = $Workspace.TrimEnd("/") + "/hermes-agent-devkit/lite"
    if ($RequireLiteFiles) {
        Invoke-Checked -Program "docker" -Arguments @("exec","--user","hermes",$Name,"test","-r","/opt/custom-skills/lite/dev-lite-session/SKILL.md")
        Invoke-Checked -Program "docker" -Arguments @("exec","--user","hermes",$Name,"test","-r",($LiteDir + "/AGENTS.md"))
    }
    if ($Contract.DataType -eq "bind") {
        Write-Warning "[DATA] /opt/data is an EXISTING persistent host bind, not a Docker volume; preserving $($Contract.DataSource)"
    }
    else {
        Write-Host "[OK] Existing data volume: $($Contract.DataVolume)"
    }
    Write-Host "[OK] Existing mounts and data write access verified"
    return [pscustomobject]@{ DataType = $Contract.DataType; LiteWorkdir = $LiteDir }
}
function Copy-LiteAdapter {
    param([string]$Name)
    $Source = Join-Path $Root "scripts\lite_mode.py"
    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) { throw "Missing Lite adapter: $Source" }
    Invoke-Checked -Program "docker" -Arguments @("cp",$Source,($Name + ":/tmp/devkit-lite-mode.py"))
}
function Adapter {
    param([string]$Action, [string]$Name)
    Copy-LiteAdapter -Name $Name
    Invoke-Checked -Program "docker" -Arguments @("exec","--user","hermes",$Name,"/opt/hermes/.venv/bin/python","/tmp/devkit-lite-mode.py",$Action)
}
function Get-OverlayStatus {
    param([string]$Name)
    Copy-LiteAdapter -Name $Name
    $Json = Capture-Checked -Program "docker" -Arguments @("exec","--user","hermes",$Name,"/opt/hermes/.venv/bin/python","/tmp/devkit-lite-mode.py","status")
    try { return ConvertFrom-Json -InputObject $Json }
    catch { throw "Unable to decode Lite overlay status: $($_.Exception.Message)" }
}
function Expect-Rejection {
    param([scriptblock]$Operation, [string]$Message)
    $Caught = $false
    try { & $Operation | Out-Null }
    catch {
        if ($_.Exception.Message -notlike "*$Message*") {
            throw "Unexpected rejection instead of '$Message': $($_.Exception.Message)"
        }
        $Caught = $true
    }
    if (-not $Caught) { throw "Unsafe mount fixture accepted: expected '$Message'" }
}
function Test-MountContract {
    # Pure Docker-inspect fixtures; validates Windows PowerShell 5.1 JSON
    # conversion and acceptance of BOTH existing named-volume and host-bind data.
    $Volume = [pscustomobject]@{Type="volume";Name="hermes-dev-data";Source="/var/lib/docker/volumes/hermes-dev-data/_data";Destination="/opt/data";RW=$true}
    $DataBind = [pscustomobject]@{Type="bind";Source="D:/HermesData";Destination="/opt/data";RW=$true}
    $Workspace = [pscustomobject]@{Type="bind";Source="D:/workspace";Destination="/workspace";RW=$true}
    $Skills = [pscustomobject]@{Type="bind";Source="D:/workspace/devkit/custom-skills";Destination="/opt/custom-skills";RW=$false}
    $Shared = [pscustomobject]@{Type="bind";Source="D:/workspace/devkit/shared";Destination="/opt/data/shared";RW=$false}
    $Temp = [pscustomobject]@{Type="bind";Source="C:/Users/example/AppData/Local/Temp";Destination="/mnt/c/Users/example/AppData/Local/Temp";RW=$false}
    $Array = @($Volume,$Workspace,$Skills,$Shared,$Temp)
    $Converted = Parse-MountJson -Json (ConvertTo-Json -InputObject $Array -Compress -Depth 5)
    if (@($Converted).Count -ne 5) { throw "Docker JSON array flattening failed" }
    $Result = Check-MountContract -Mounts $Converted -WorkspaceTarget "/workspace"
    if ($Result.DataType -ne "volume" -or $Result.DataVolume -ne "hermes-dev-data") { throw "Volume data fixture failed" }
    $Single = Parse-MountJson -Json (ConvertTo-Json -InputObject @($Volume) -Compress -Depth 5)
    if (@($Single).Count -ne 1 -or $Single[0].Destination -ne "/opt/data") { throw "Single element JSON flatten failed" }
    $Result = Check-MountContract -Mounts @($DataBind,$Workspace,$Skills,$Shared,$Temp) -WorkspaceTarget "/workspace"
    if ($Result.DataType -ne "bind" -or $Result.DataSource -ne "D:/HermesData") { throw "Host-bind data fixture failed" }
    $Alt = [pscustomobject]@{Type="bind";Source="E:/work";Destination="/work";RW=$true}
    $Result = Check-MountContract -Mounts @($Volume,$Alt,$Skills,$Shared) -WorkspaceTarget "/work"
    if ($Result.Workspace -ne "/work") { throw "Custom workspace fixture failed" }

    Expect-Rejection -Message "Unsupported mount" -Operation {
        $Bad = [pscustomobject]@{Type="tmpfs";Source="/memory";Destination="/opt/data";RW=$true}
        Check-MountContract -Mounts @($Bad,$Workspace,$Skills,$Shared) -WorkspaceTarget "/workspace"
    }
    Expect-Rejection -Message "read-only" -Operation {
        $Bad = [pscustomobject]@{Type="bind";Source="D:/HermesData";Destination="/opt/data";RW=$false}
        Check-MountContract -Mounts @($Bad,$Workspace,$Skills,$Shared) -WorkspaceTarget "/workspace"
    }
    Expect-Rejection -Message "found 2" -Operation {
        Check-MountContract -Mounts @($Volume,$DataBind,$Workspace,$Skills,$Shared) -WorkspaceTarget "/workspace"
    }
    Expect-Rejection -Message "found 0" -Operation {
        Check-MountContract -Mounts @($Volume,$Workspace,$Skills) -WorkspaceTarget "/workspace"
    }
    Expect-Rejection -Message "Unsupported mount" -Operation {
        $Bad = [pscustomobject]@{Type="volume";Name="wrong";Source="/vol";Destination="/opt/custom-skills";RW=$true}
        Check-MountContract -Mounts @($Volume,$Workspace,$Bad,$Shared) -WorkspaceTarget "/workspace"
    }
    Expect-Rejection -Message "no persistent Source" -Operation {
        $Bad = [pscustomobject]@{Type="bind";Source="";Destination="/opt/data";RW=$true}
        Check-MountContract -Mounts @($Bad,$Workspace,$Skills,$Shared) -WorkspaceTarget "/workspace"
    }
    Expect-Rejection -Message "Cannot decode" -Operation { Parse-MountJson -Json "{not-json" }
    Write-Host "[PASS] Docker mount JSON / volume / bind / safety cases"
}
function Test-GitForwarding {
    $Version = Capture-Checked -Program "git" -Arguments @("--version")
    if ($Version -notmatch "^git version [0-9]") { throw "Git argv forwarding failed: $Version" }
    $Found = Capture-Checked -Program "git" -Arguments @("-C",$Root,"rev-parse","--show-toplevel")
    $Expected = (Resolve-Path -LiteralPath $Root).Path
    if ([IO.Path]::GetFullPath($Found).TrimEnd("\","/") -ne [IO.Path]::GetFullPath($Expected).TrimEnd("\","/")) {
        throw "Git argv forwarding failed: $Found"
    }
    Invoke-Checked -Program "git" -Arguments @("-C",$Root,"rev-parse","--is-inside-work-tree") | Out-Null
    Write-Host "[PASS] Git native argv forwarding"
}
try {
    if ($SelfTest) { Test-GitForwarding; return }
    if ($MountSelfTest) { Test-MountContract; return }

    Set-Location -LiteralPath $Root
    foreach ($Cmd in @("git","docker")) {
        if (-not (Get-Command $Cmd -ErrorAction SilentlyContinue)) { throw "Required executable missing: $Cmd" }
    }
    Assert-DevkitCheckout
    $Runtime = Check-ExistingContainer -Name $Container -RequireLiteFiles:($Mode -eq "lite")
    if ($Mode -eq "status") {
        Write-Host "[MODE] Devkit branch: $(Capture-Checked -Program 'git' -Arguments @('branch','--show-current'))"
        Adapter -Action "status" -Name $Container
        return
    }
    if ($Mode -eq "standard") {
        Adapter -Action "restore" -Name $Container
        Write-Host "[PASS] Standard profile policy restored; Git and persistent data unchanged"
        return
    }
    # No branch switch since Lite was merged into dev (PR #188).
    $AppliedNow = $false
    try {
        # Preflight the active-worker guard before changing any profile fields.
        Adapter -Action "guard" -Name $Container
        # A pre-existing Lite overlay is not restored on a failed repeated call.
        $StateBefore = Get-OverlayStatus -Name $Container
        if ($null -eq $StateBefore.lite) { throw "Lite adapter status missing 'lite'" }
        $AppliedNow = -not [bool]$StateBefore.lite
        Adapter -Action "apply" -Name $Container
        Invoke-Checked -Program "docker" -Arguments @("exec","--user","hermes",$Container,"/opt/hermes/.venv/bin/hermes","--help")
    }
    catch {
        if ($AppliedNow) {
            Write-Warning "Lite startup failed; restoring the previous default profile fields"
            try { Adapter -Action "restore" -Name $Container }
            catch { Write-Warning "Restore failed: $($_.Exception.Message). Backup retained in /opt/data/devkit-lite." }
        }
        throw
    }
    Write-Host "[PASS] Lite applied; existing container and data retained"
    Write-Host "Start a NEW Lite session:"
    Write-Host "docker exec -it --user hermes --workdir $($Runtime.LiteWorkdir) $Container /opt/hermes/.venv/bin/hermes -p default"
    Write-Host "Restore Standard: .\updatekit_lite.ps1 -Mode standard"
}
finally { Set-Location $PriorLocation }
