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
    [string]$SkillsRoot = '/opt/custom-skills'
)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$InspectRaw = & docker inspect $Container
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect the existing Hermes container' }
$Inspect = @(ConvertFrom-Json -InputObject (@($InspectRaw) -join "`n"))[0]
if ($Mode -eq 'status') {
    & docker exec --user hermes $Container /opt/hermes/.venv/bin/python /opt/devkit/bin/lite_default_profile.py status --skills-root $SkillsRoot
    if ($LASTEXITCODE -ne 0) { throw 'Lite default configuration is not ready; inspect migration diagnostics' }
    return
}
$Source = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'scripts/lite_default_profile.py') -Raw -Encoding UTF8
# A throw-away, read-only process also works when the old container is stopped.
# No secrets are copied from the volume or printed. No gateway/worker is started.
$PreviousEncoding = $OutputEncoding
try {
    $OutputEncoding = New-Object System.Text.UTF8Encoding($false)
    $Source | & docker run --rm -i --read-only --network none --user hermes `
        --volumes-from ($Container + ':ro') --env PYTHONDONTWRITEBYTECODE=1 `
        --entrypoint /opt/hermes/.venv/bin/python $Inspect.Image - plan `
        --data-root /opt/data --skills-root $SkillsRoot
    if ($LASTEXITCODE -ne 0) { throw 'Lite migration preflight blocked; the existing runtime and data were not recreated' }
}
finally { $OutputEncoding = $PreviousEncoding }
