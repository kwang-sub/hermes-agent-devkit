$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$source = Join-Path $PSScriptRoot 'design-plugins.ps1'
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($source, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors | Out-String) }
# Load only pure helpers, not the Docker/install entry point.
$functions = $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true)
foreach ($fn in $functions) { . ([ScriptBlock]::Create($fn.Extent.Text)) }
$count = 0
function Assert-Equal($Actual, $Expected) {
    if ($Actual -cne $Expected) { throw "Expected '$Expected', received '$Actual'." }
    $script:count++
}
function Assert-Throws([ScriptBlock]$Action) {
    $threw = $false
    try { & $Action } catch { $threw = $true }
    if (-not $threw) { throw 'Expected operation to fail closed.' }
    $script:count++
}
Assert-Equal (ConvertTo-ComparableHostPath 'D:\workspace\') 'D:/workspace'
Assert-Equal (ConvertTo-ComparableHostPath '/run/desktop/mnt/host/d/workspace') 'd:/workspace'
Assert-Equal (ConvertTo-ComparableHostPath '/host_mnt/d/workspace') 'd:/workspace'
Assert-Equal (ConvertTo-ComparableHostPath '/mnt/d/workspace') 'd:/workspace'
Assert-Equal (ConvertTo-ComparableHostPath '/unrelated/path') '/unrelated/path'
Assert-Equal (ConvertTo-ComparableHostPath '/mnt/d') 'd:'
Assert-LocalDockerEndpoint 'npipe:////./pipe/docker_engine'; $count++
Assert-LocalDockerEndpoint 'npipe:////./pipe/dockerDesktopLinuxEngine'; $count++
Assert-Throws { Assert-LocalDockerEndpoint 'tcp://127.0.0.1:2375' }
Assert-Throws { Assert-LocalDockerEndpoint 'ssh://remote-server' }
Assert-Throws { Assert-LocalDockerEndpoint 'npipe:////remote/pipe/docker_engine' }
Assert-Throws { Assert-LocalDockerEndpoint 'unix:///var/run/docker.sock' }


$temp = Join-Path ([IO.Path]::GetTempPath()) ('devkit-design-' + [Guid]::NewGuid().ToString('N'))
try {
    $repo = New-Item -ItemType Directory -Path (Join-Path $temp 'workspace with spaces/repo') -Force
    $workspace = (Get-Item $repo.Parent.FullName).FullName
    $mount = [PSCustomObject]@{Type='bind';Source=$workspace;Destination='/work/custom'}
    Assert-Equal (Resolve-ContainerPath -HostPath $repo.FullName -Mounts @($mount)) '/work/custom/repo'
    $nested = [PSCustomObject]@{Type='bind';Source=$repo.FullName;Destination='/more-specific'}
    Assert-Equal (Resolve-ContainerPath -HostPath $repo.FullName -Mounts @($mount, $nested)) '/more-specific'
    $conflict = [PSCustomObject]@{Type='bind';Source=$workspace;Destination='/ambiguous'}
    Assert-Throws { Resolve-ContainerPath -HostPath $repo.FullName -Mounts @($mount, $conflict) }
    $outside = New-Item -ItemType Directory -Path (Join-Path $temp 'workspace with spaces-other') -Force
    Assert-Throws { Resolve-ContainerPath -HostPath $outside.FullName -Mounts @($mount) }
    Assert-Throws { Resolve-ContainerPath -HostPath $repo.FullName -Mounts @() }
    $good = [PSCustomObject]@{HostIp='127.0.0.1';HostPort='8790'}
    Assert-LocalReviewPort -Bindings @($good); $count++
    Assert-Throws { Assert-LocalReviewPort -Bindings @() }
    Assert-Throws { Assert-LocalReviewPort -Bindings @([PSCustomObject]@{HostIp='0.0.0.0';HostPort='8790'}) }
    Assert-Throws { Assert-LocalReviewPort -Bindings @([PSCustomObject]@{HostIp='::';HostPort='8790'}) }
    Assert-Throws { Assert-LocalReviewPort -Bindings @([PSCustomObject]@{HostIp='127.0.0.1';HostPort='9999'}) }
    Assert-Throws { Assert-LocalReviewPort -Bindings @($good, $good) }
} finally {
    # Delete only the unique temporary directory created by this test.
    if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Recurse -Force }
}
Write-Output "[PASS] $count design-plugin Windows path/port contracts. No Docker commands executed."
