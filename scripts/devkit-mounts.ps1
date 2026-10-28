# Mount-contract and evidence helpers; importing this file does not access Docker or .env.
Set-StrictMode -Version 2.0

function ConvertTo-FlatMounts {
    param([Parameter(Mandatory=$true)][string]$Json)
    $Decoded = ConvertFrom-Json -InputObject $Json -ErrorAction Stop
    $Flat = New-Object System.Collections.ArrayList
    foreach ($Entry in @($Decoded)) {
        if ($Entry -is [System.Array]) {
            foreach ($Child in $Entry) { [void]$Flat.Add($Child) }
        }
        else { [void]$Flat.Add($Entry) }
    }
    return ,($Flat.ToArray())
}

function Assert-PersistentMounts {
    param([object[]]$Mounts, [string]$Workspace)
    if ([string]::IsNullOrWhiteSpace($Workspace) -or -not $Workspace.StartsWith('/')) {
        throw 'Invalid container workspace directory'
    }
    $Seen = @{}
    foreach ($Mount in $Mounts) {
        foreach ($Key in @('Type','Source','Destination','RW')) {
            if ($null -eq $Mount.PSObject.Properties[$Key]) { throw "Mount missing field: $Key" }
        }
        $Target = [string]$Mount.Destination
        if (-not $Target.StartsWith('/') -or $Seen.ContainsKey($Target)) { throw 'Invalid or duplicate mount target' }
        $Seen[$Target] = $true
        if ($Mount.Type -notin @('bind','volume')) { throw "Unsupported existing mount type at $Target; refusing recreation" }
        if ([string]::IsNullOrWhiteSpace([string]$Mount.Source) -or $Mount.RW -isnot [bool]) { throw 'Mount source or writable state is unknown' }
        if ($Mount.Type -eq 'volume' -and ($null -eq $Mount.PSObject.Properties['Name'] -or [string]::IsNullOrWhiteSpace([string]$Mount.Name))) {
            throw 'Named volume identity is missing'
        }
        if ($null -ne $Mount.PSObject.Properties['SubPath'] -and $Mount.SubPath) { throw 'Volume subpath needs explicit migration support' }
    }
    $Data = @($Mounts | Where-Object { $_.Destination -ceq '/opt/data' })
    $Source = @($Mounts | Where-Object { $_.Destination -ceq $Workspace })
    if ($Data.Count -ne 1 -or -not $Data[0].RW) { throw 'Expected one writable persistent /opt/data mount' }
    if ($Source.Count -ne 1 -or $Source[0].Type -ne 'bind' -or -not $Source[0].RW) { throw 'Expected one writable workspace bind' }
}

function Get-MountSignature {
    param([object[]]$Mounts)
    $Rows = foreach ($Mount in $Mounts) {
        $Source = if ($Mount.Type -eq 'volume') { [string]$Mount.Name } else { [string]$Mount.Source }
        $Propagation = if ($null -ne $Mount.PSObject.Properties['Propagation']) { [string]$Mount.Propagation } else { '' }
        "{0}|{1}|{2}|{3}|{4}" -f $Mount.Type,$Source,$Mount.Destination,$Mount.RW,$Propagation
    }
    return (($Rows | Sort-Object) -join "`n")
}

function New-MountEvidenceDirectory {
    param([string]$Root = $env:HERMES_DEVKIT_UPDATE_HISTORY_ROOT)
    try {
        if ([string]::IsNullOrWhiteSpace($Root)) {
            $LocalData = [Environment]::GetFolderPath('LocalApplicationData')
            if ([string]::IsNullOrWhiteSpace($LocalData)) { throw 'Local application data directory is unavailable' }
            $Root = Join-Path $LocalData 'HermesAgentDevKit/update-history'
        }
        if (-not [IO.Path]::IsPathRooted($Root)) { throw 'Mount evidence root must be an absolute path' }
        if ([IO.Path]::DirectorySeparatorChar -eq '\' -and $Root -notmatch '^(?:[A-Za-z]:[\\/]|[\\/]{2}[^\\/]+[\\/][^\\/]+)') {
            throw 'Mount evidence root must include a drive or UNC share'
        }
        $Root = [IO.Path]::GetFullPath($Root)
        $Run = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ') + '-' + [Guid]::NewGuid().ToString('N')
        $Directory = Join-Path $Root $Run
        [void][IO.Directory]::CreateDirectory($Directory)
        return $Directory
    }
    catch {
        Write-Warning "Mount evidence directory could not be created ($($_.Exception.GetType().Name)); updater checks remain unchanged." -WarningAction Continue
        return $null
    }
}

function Write-MountEvidence {
    param(
        [string]$Directory,
        [ValidateSet('before','after')][string]$Phase,
        [AllowNull()][object]$Inspect,
        [string]$ContainerName,
        [object[]]$BeforeMounts = @()
    )
    if ([string]::IsNullOrWhiteSpace($Directory)) { return }
    try {
        $Mounts = @()
        $ContainerId = ''
        $ImageId = ''
        if ($null -ne $Inspect) {
            $Mounts = @($Inspect.Mounts)
            if ($null -ne $Inspect.PSObject.Properties['Id']) { $ContainerId = [string]$Inspect.Id }
            if ($null -ne $Inspect.PSObject.Properties['Image']) { $ImageId = [string]$Inspect.Image }
        }
        # Rebuild only mount fields. Never serialize Config.Env, labels or the Compose model.
        $Records = New-Object System.Collections.ArrayList
        foreach ($Mount in $Mounts) {
            $VolumeName = if ($null -ne $Mount.PSObject.Properties['Name']) { [string]$Mount.Name } else { $null }
            $Propagation = if ($null -ne $Mount.PSObject.Properties['Propagation']) { [string]$Mount.Propagation } else { '' }
            [void]$Records.Add([ordered]@{
                Type = [string]$Mount.Type; Name = $VolumeName; Source = [string]$Mount.Source
                Destination = [string]$Mount.Destination; RW = [bool]$Mount.RW; Propagation = $Propagation
            })
        }
        $Signature = Get-MountSignature $Mounts
        $Snapshot = [ordered]@{
            schema_version = 1; phase = $Phase; captured_at_utc = [DateTime]::UtcNow.ToString('o')
            container_name = $ContainerName; container_id = $ContainerId; image_id = $ImageId
            mounts = @($Records.ToArray()); signature = $Signature
        }
        if ($Phase -eq 'after') {
            $BeforeSignature = Get-MountSignature $BeforeMounts
            $BeforeRows = @()
            $AfterRows = @()
            if ($BeforeMounts.Count -gt 0) { $BeforeRows = @($BeforeSignature -split "`n") }
            if ($Mounts.Count -gt 0) { $AfterRows = @($Signature -split "`n") }
            $Snapshot.comparison = [ordered]@{
                had_previous_mounts = ($BeforeMounts.Count -gt 0)
                matches = ($BeforeSignature -ceq $Signature)
                before_signature = $BeforeSignature
                before_only = @($BeforeRows | Where-Object { $AfterRows -cnotcontains $_ })
                after_only = @($AfterRows | Where-Object { $BeforeRows -cnotcontains $_ })
            }
        }
        $Path = Join-Path $Directory ($Phase + '.json')
        $Pending = $Path + '.tmp'
        [IO.File]::WriteAllText($Pending, (ConvertTo-Json -InputObject $Snapshot -Depth 12), (New-Object Text.UTF8Encoding($false)))
        [IO.File]::Move($Pending, $Path)
        Write-Host "[INFO] Mount evidence ($Phase) -> $Path"
        if ($Phase -eq 'after' -and $BeforeMounts.Count -gt 0 -and -not $Snapshot.comparison.matches) {
            foreach ($Row in $Snapshot.comparison.before_only) { Write-Host "[MOUNT BEFORE ONLY] $Row" }
            foreach ($Row in $Snapshot.comparison.after_only) { Write-Host "[MOUNT AFTER ONLY] $Row" }
        }
    }
    catch {
        Write-Warning "Mount evidence ($Phase) could not be saved in $Directory ($($_.Exception.GetType().Name)); updater checks remain unchanged." -WarningAction Continue
    }
}

function New-PreservedMountOverride {
    param([object[]]$Mounts, [string]$Workspace, [object]$ComposeModel)
    Assert-PersistentMounts -Mounts $Mounts -Workspace $Workspace
    $Service = $ComposeModel.services.hermes
    if ([string]$Service.working_dir -cne $Workspace) {
        throw 'Compose workspace differs from the existing container. Reconcile .env before updating.'
    }
    $Targets = @($Mounts | ForEach-Object { [string]$_.Destination })
    foreach ($Mount in $Service.volumes) {
        if ($Targets -cnotcontains [string]$Mount.target) { throw 'Compose adds a mount not present in the existing container; explicit reconciliation required' }
    }
    $Volumes = @{}
    $Entries = New-Object System.Collections.ArrayList
    $Index = 0
    foreach ($Mount in $Mounts) {
        $Entry = @{ type = [string]$Mount.Type; target = [string]$Mount.Destination; read_only = (-not [bool]$Mount.RW) }
        if ($Mount.Type -eq 'volume') {
            $Key = "devkit_preserved_$Index"
            $Volumes[$Key] = @{ external = $true; name = [string]$Mount.Name }
            $Entry.source = $Key
            $Entry.volume = @{ nocopy = $true }
        }
        else {
            $Entry.source = [string]$Mount.Source
            $Entry.bind = @{ create_host_path = $false }
            if ($null -ne $Mount.PSObject.Properties['Propagation'] -and $Mount.Propagation) {
                $Entry.bind.propagation = [string]$Mount.Propagation
            }
        }
        [void]$Entries.Add($Entry)
        $Index++
    }
    return @{ services = @{ hermes = @{ working_dir = $Workspace; volumes = @($Entries.ToArray()) } }; volumes = $Volumes }
}
