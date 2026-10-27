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
