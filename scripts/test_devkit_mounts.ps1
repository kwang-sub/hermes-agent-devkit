#requires -Version 5.1
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'devkit-mounts.ps1')
function Reject([scriptblock]$Action) {
    $Rejected=$false
    try { & $Action | Out-Null } catch { $Rejected=$true }
    if (-not $Rejected) { throw 'Unsafe mount fixture was accepted' }
}
$Workspace=[pscustomobject]@{ Type='bind'; Source='D:/workspace'; Destination='/workspace'; RW=$true; Propagation='rprivate' }
$Data=[pscustomobject]@{ Type='volume'; Source='/var/lib/docker/volumes/original/_data'; Name='original'; Destination='/opt/data'; RW=$true }
$Extra=[pscustomobject]@{ Type='bind'; Source='E:/external'; Destination='/external'; RW=$false; Propagation='rprivate' }
$Model=[pscustomobject]@{ services=[pscustomobject]@{ hermes=[pscustomobject]@{ working_dir='/workspace'; volumes=@([pscustomobject]@{target='/workspace'},[pscustomobject]@{target='/opt/data'}) } } }
$Mounts=@($Data,$Workspace,$Extra)
$Parsed=ConvertTo-FlatMounts -Json (ConvertTo-Json -InputObject $Mounts -Depth 8)
if ($Parsed.Count -ne 3) { throw 'Mount JSON flatten regression' }
$Override=New-PreservedMountOverride -Mounts $Parsed -Workspace '/workspace' -ComposeModel $Model
if ($Override.volumes.devkit_preserved_0.name -ne 'original') { throw 'Original volume not preserved' }
if ($Override.services.hermes.volumes.Count -ne 3) { throw 'External mount dropped' }
if (-not $Override.services.hermes.volumes[2].read_only) { throw 'External mount became writable' }
$Bind=[pscustomobject]@{ Type='bind'; Source='E:/hermes-data'; Destination='/opt/data'; RW=$true; Propagation='rprivate' }
$BindOverride=New-PreservedMountOverride -Mounts @($Bind,$Workspace) -Workspace '/workspace' -ComposeModel $Model
if ($BindOverride.services.hermes.volumes[0].source -ne 'E:/hermes-data') { throw 'Data bind converted to volume' }
Reject { Assert-PersistentMounts -Mounts @($Data,$Data,$Workspace) -Workspace '/workspace' }
Reject { Assert-PersistentMounts -Mounts @($Workspace) -Workspace '/workspace' }
Reject { Assert-PersistentMounts -Mounts @([pscustomobject]@{ Type='tmpfs'; Source='tmpfs'; Destination='/opt/data'; RW=$true },$Workspace) -Workspace '/workspace' }
Reject { Assert-PersistentMounts -Mounts @([pscustomobject]@{ Type='bind'; Source='E:/data'; Destination='/opt/data'; RW=$false },$Workspace) -Workspace '/workspace' }
Reject { New-PreservedMountOverride -Mounts $Mounts -Workspace '/other' -ComposeModel $Model }
if ((Get-MountSignature $Mounts) -eq (Get-MountSignature @($Bind,$Workspace,$Extra))) { throw 'Data replacement not detected' }
Write-Host '[PASS] Named volume, host bind, external mount, read-only, duplicate and mismatch fixtures'

$HistoryRoot=Join-Path ([IO.Path]::GetTempPath()) ('devkit-mount-evidence-test-'+[Guid]::NewGuid().ToString('N'))
$OriginalWarningPreference=$WarningPreference
try {
    $First=New-MountEvidenceDirectory -Root $HistoryRoot
    $Second=New-MountEvidenceDirectory -Root $HistoryRoot
    if (-not $First -or -not $Second -or $First -eq $Second) { throw 'History runs did not receive separate directories' }
    $Inspect=[pscustomobject]@{
        Id='fixture-container'; Image='sha256:fixture'; Mounts=$Mounts
        Config=[pscustomobject]@{Env=@('TOKEN=never-store-env-secret');Labels=@{secret='never-store-label-secret'}}
    }
    $Output=@(Write-MountEvidence -Directory $First -Phase before -Inspect $Inspect -ContainerName 'fixture')
    if ($Output.Count) { throw 'Evidence logging polluted the success stream' }
    $BeforePath=Join-Path $First 'before.json'
    $BeforeRaw=Get-Content -LiteralPath $BeforePath -Raw
    $Before=ConvertFrom-Json -InputObject $BeforeRaw
    if ($Before.schema_version -ne 1 -or $Before.phase -cne 'before' -or
        $Before.container_id -cne 'fixture-container' -or $Before.image_id -cne 'sha256:fixture') {
        throw 'Evidence lost snapshot identity'
    }
    if ($Before.mounts -isnot [array] -or $Before.mounts.Count -ne 3 -or
        $Before.mounts[0].Name -cne 'original' -or $Before.mounts[0].RW -isnot [bool]) {
        throw 'Mount evidence did not round-trip as an array with typed fields'
    }
    if ($BeforeRaw -match 'never-store|"Config"|"Env"|"Labels"|"value"') { throw 'Evidence serialized unrelated inspect data or an array wrapper' }

    $Inspect.Mounts=@($Extra,$Workspace,$Data)
    Write-MountEvidence -Directory $First -Phase after -Inspect $Inspect -ContainerName 'fixture' -BeforeMounts $Mounts
    $After=ConvertFrom-Json -InputObject (Get-Content -LiteralPath (Join-Path $First 'after.json') -Raw)
    if (-not $After.comparison.had_previous_mounts -or -not $After.comparison.matches -or
        $After.comparison.before_only.Count -ne 0 -or $After.comparison.after_only.Count -ne 0) {
        throw 'Reordered unchanged mounts were reported as different'
    }
    if ((Get-Content -LiteralPath $BeforePath -Raw) -cne $BeforeRaw) { throw 'After evidence replaced the before snapshot' }

    $CaseWorkspace=[pscustomobject]@{Type='bind';Source='d:/workspace';Destination='/workspace';RW=$true;Propagation='rprivate'}
    $Inspect.Mounts=@($Data,$CaseWorkspace,$Extra)
    Write-MountEvidence -Directory $Second -Phase after -Inspect $Inspect -ContainerName 'fixture' -BeforeMounts $Mounts
    $Changed=ConvertFrom-Json -InputObject (Get-Content -LiteralPath (Join-Path $Second 'after.json') -Raw)
    if ($Changed.comparison.matches -or $Changed.comparison.before_only.Count -ne 1 -or
        $Changed.comparison.after_only.Count -ne 1 -or
        $Changed.comparison.before_only -cnotcontains 'bind|D:/workspace|/workspace|True|rprivate' -or
        $Changed.comparison.after_only -cnotcontains 'bind|d:/workspace|/workspace|True|rprivate') {
        throw 'Evidence lost a case-sensitive mount difference'
    }

    $BlockedRoot=Join-Path $HistoryRoot 'blocked-by-file'
    [IO.File]::WriteAllText($BlockedRoot,'owned test blocker')
    $WarningPreference='Stop'
    if ([IO.Path]::DirectorySeparatorChar -eq '\' -and $HistoryRoot -match '^[A-Za-z]:') {
        $PreviousDirectory=[Environment]::CurrentDirectory
        try {
            [Environment]::CurrentDirectory=$HistoryRoot
            $DriveRelative=$HistoryRoot.Substring(0,2)+'drive-relative'
            $RootRelative=$HistoryRoot.Substring(2)+'\root-relative'
            foreach ($RelativeRoot in @($DriveRelative,$RootRelative)) {
                if ($null -ne (New-MountEvidenceDirectory -Root $RelativeRoot)) { throw 'A drive-relative or root-relative history path was accepted' }
            }
            if ((Test-Path -LiteralPath (Join-Path $HistoryRoot 'drive-relative')) -or
                (Test-Path -LiteralPath (Join-Path $HistoryRoot 'root-relative'))) { throw 'Relative history validation created a directory' }
        }
        finally { [Environment]::CurrentDirectory=$PreviousDirectory }
    }
    if ($null -ne (New-MountEvidenceDirectory -Root $BlockedRoot)) { throw 'Failed history directory creation reported success' }
    $Output=@(Write-MountEvidence -Directory $BlockedRoot -Phase after -Inspect $Inspect -ContainerName 'fixture' -BeforeMounts $Mounts)
    if ($Output.Count) { throw 'Failed evidence logging polluted the success stream' }
    Write-MountEvidence -Directory $null -Phase before -Inspect $Inspect -ContainerName 'fixture'
    Write-Host '[PASS] Persistent mount evidence, JSON arrays, case-sensitive differences, secret exclusion and nonfatal logging failures'
}
finally {
    $WarningPreference=$OriginalWarningPreference
    if (Test-Path -LiteralPath $HistoryRoot) { Remove-Item -LiteralPath $HistoryRoot -Recurse -Force }
}
