[CmdletBinding()]
param(
    [ValidateSet('plan', 'install', 'status', 'serve', 'sample', 'create', 'feedback')]
    [string]$Mode = 'plan',
    [string]$Container = 'hermes-dev',
    [string]$Decisions,
    [string]$ReviewId
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path

function ConvertTo-ComparableHostPath {
    param([Parameter(Mandatory=$true)][string]$Value)
    $p = $Value.Replace('\', '/').TrimEnd('/')
    # Docker Desktop may report bind sources in Linux-normalized form.
    if ($p -match '^/(?:run/desktop/mnt/host|host_mnt|mnt)/([A-Za-z])(?:/(.*))?$') {
        $tail = ''
        if ($Matches.ContainsKey(2)) { $tail = $Matches[2] }
        $p = $Matches[1] + ':/' + $tail
    }
    return $p.TrimEnd('/')
}

function Resolve-ContainerPath {
    param([Parameter(Mandatory=$true)][string]$HostPath, [object[]]$Mounts)
    $resolved = (Resolve-Path -LiteralPath $HostPath).Path
    $path = ConvertTo-ComparableHostPath $resolved
    $matchesFound = @()
    foreach ($mount in $Mounts) {
        if ($mount.Type -ne 'bind') { continue }
        $source = ConvertTo-ComparableHostPath ([string]$mount.Source)
        if ($path.Equals($source, [StringComparison]::OrdinalIgnoreCase) -or
            $path.StartsWith($source + '/', [StringComparison]::OrdinalIgnoreCase)) {
            $suffix = $path.Substring($source.Length)
            $matchesFound += [PSCustomObject]@{
                Length = $source.Length
                Path = ([string]$mount.Destination).TrimEnd('/') + $suffix
            }
        }
    }
    if ($matchesFound.Count -eq 0) {
        throw 'The requested path is not covered by an existing Docker bind mount. No mount was changed.'
    }
    $ordered = @($matchesFound | Sort-Object Length -Descending)
    if ($ordered.Count -gt 1 -and $ordered[0].Length -eq $ordered[1].Length -and $ordered[0].Path -ne $ordered[1].Path) {
        throw 'Ambiguous bind mapping. No path was guessed.'
    }
    return $ordered[0].Path
}

function Assert-LocalDockerEndpoint {
    param([Parameter(Mandatory=$true)][string]$Endpoint)
    # Only Windows local named pipes: remote tcp/ssh contexts have another localhost.
    if ($Endpoint -notmatch '^npipe:/+\./pipe/[^/\r\n]+$') {
        throw 'A local Windows Docker Desktop named-pipe endpoint is required. Remote or unknown Docker endpoints are not used.'
    }
}

function Assert-LocalReviewPort {
    param([object[]]$Bindings)
    if ($null -eq $Bindings -or $Bindings.Count -ne 1 -or
        $Bindings[0].HostIp -ne '127.0.0.1' -or $Bindings[0].HostPort -ne '8790') {
        throw 'Required mapping: 127.0.0.1:8790:8790. Apply compose.yml through the normal updater first; no restart was attempted.'
    }
}

if ($Mode -eq 'plan') {
    Get-Content -Raw -LiteralPath (Join-Path $RepoRoot 'shared/design-plugins/hermes-pack.yaml')
    Write-Output '[DESIGN] Plan only. No installation, configuration changes or container restart.'
    exit 0
}

$Docker = (Get-Command docker -ErrorAction Stop).Source
if (-not [string]::IsNullOrWhiteSpace($env:DOCKER_HOST) -and [string]::IsNullOrWhiteSpace($env:DOCKER_CONTEXT)) {
    Assert-LocalDockerEndpoint -Endpoint $env:DOCKER_HOST
} else {
    $contextName = & $Docker context show
    if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve the current Docker context.' }
    $endpointJson = & $Docker context inspect ($contextName -join '').Trim() --format '{{json .Endpoints.docker.Host}}'
    if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect the Docker context endpoint.' }
    $endpoint = ($endpointJson -join "`n") | ConvertFrom-Json
    Assert-LocalDockerEndpoint -Endpoint ([string]$endpoint)
}
$state = & $Docker inspect --format '{{.State.Running}}' $Container
if ($LASTEXITCODE -ne 0 -or ($state -join '').Trim() -ne 'true') {
    throw 'The selected container is not running. No container was started or recreated.'
}
$mountJson = & $Docker inspect --format '{{json .Mounts}}' $Container
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect container mounts.' }
$mounts = @((($mountJson -join "`n") | ConvertFrom-Json))
$root = Resolve-ContainerPath -HostPath $RepoRoot -Mounts $mounts

# Only loopback publishing is accepted, independently of dashboard/API bindings.
$portsJson = & $Docker inspect --format '{{json .NetworkSettings.Ports}}' $Container
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect container port bindings.' }
$ports = ($portsJson -join "`n") | ConvertFrom-Json
$property = $ports.PSObject.Properties['8790/tcp']
$bindings = @()
if ($null -ne $property -and $null -ne $property.Value) { $bindings = @($property.Value) }
Assert-LocalReviewPort -Bindings $bindings

$dockerArgs = @('exec')
if ($Mode -in @('install', 'serve')) { $dockerArgs += '-it' } else { $dockerArgs += '-i' }
$dockerArgs += @('--user', 'hermes', '--workdir', $root, $Container,
    '/opt/hermes/.venv/bin/python', ($root + '/scripts/design_plugins.py'), $Mode)
if ($Mode -eq 'create') {
    if ([string]::IsNullOrWhiteSpace($Decisions)) { throw '-Decisions is required for create.' }
    $dockerArgs += @('--decisions', (Resolve-ContainerPath -HostPath $Decisions -Mounts $mounts))
}
if ($Mode -eq 'feedback') {
    if ($ReviewId -notmatch '^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$') { throw 'A valid -ReviewId is required.' }
    $dockerArgs += @('--review-id', $ReviewId)
}
& $Docker @dockerArgs
if ($LASTEXITCODE -ne 0) { throw "Design operation failed (exit $LASTEXITCODE). No automatic cleanup or retry was performed." }
