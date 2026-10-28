#requires -Version 5.1
<#
.SYNOPSIS
Read-only migration plan for an existing container, or verify the booted Lite default.
.DESCRIPTION
Migration itself runs inside the image before upstream service reconciliation.
No role/config writes are performed against a live gateway by this host helper.
#>
[CmdletBinding()]
param(
    [string]$Container = 'hermes-dev',
    [ValidateSet('plan','status')][string]$Mode = 'status',
    [string]$SkillsRoot = '/opt/custom-skills',
    [string]$ImageReference
)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
if ($Mode -eq 'status') {
    & docker exec --user hermes $Container /opt/hermes/.venv/bin/python /opt/devkit/bin/lite_default_profile.py status --skills-root $SkillsRoot
    if ($LASTEXITCODE -ne 0) { throw 'Lite default configuration is not ready; inspect migration diagnostics' }
    return
}
if ([string]::IsNullOrWhiteSpace($ImageReference)) { throw 'Explicit migration image identity required for read-only plan' }
$Source = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'lite_default_profile.py') -Raw -Encoding UTF8
# A throw-away, read-only process also works when the old container is stopped.
# No secrets are copied from the volume or printed. No gateway/worker is started.
$PreviousEncoding = $OutputEncoding
try {
    $OutputEncoding = New-Object System.Text.UTF8Encoding($false)
    $Source | & docker run --rm -i --read-only --network none --user hermes `
        --volumes-from ($Container + ':ro') --env PYTHONDONTWRITEBYTECODE=1 `
        --entrypoint /opt/hermes/.venv/bin/python $ImageReference - plan `
        --data-root /opt/data --skills-root $SkillsRoot
    if ($LASTEXITCODE -ne 0) { throw 'Lite migration preflight blocked; the existing runtime and data were not recreated' }
}
finally { $OutputEncoding = $PreviousEncoding }
