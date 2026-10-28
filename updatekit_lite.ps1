#requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateSet('lite','status','standard')][string]$Mode='lite',
    [string]$Container='hermes-dev',
    [switch]$SelfTest,
    [switch]$MountSelfTest
)
$ErrorActionPreference='Stop'
if ($Mode -eq 'standard') { throw 'Standard Flow was retired. Restore a previous release explicitly; this command cannot recreate role profiles.' }
if ($SelfTest -or $MountSelfTest) { & (Join-Path $PSScriptRoot 'scripts/test_devkit_mounts.ps1'); return }
if ($Mode -eq 'status') { & (Join-Path $PSScriptRoot 'init-lite.ps1') -Container $Container -Mode status; return }
Write-Warning 'updatekit_lite.ps1 is a compatibility alias. Use update-devkit.ps1 for future updates.'
& (Join-Path $PSScriptRoot 'update-devkit.ps1') -Container $Container
