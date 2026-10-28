#requires -Version 5.1
# No Docker daemon, remote Git, .env or user data access. Exercise the real updater orchestration.
Set-StrictMode -Version 2.0
$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $PSScriptRoot
$OriginalLocal=$env:LOCALAPPDATA
$env:LOCALAPPDATA='C:\Users\fixture\AppData\Local'
$global:FixtureCalls=New-Object System.Collections.ArrayList
$global:FixtureMode='normal'
$global:FixtureRecreated=$false
$global:FixtureMounts=@(
    [pscustomobject]@{Type='volume';Name='keep-me';Source='/var/lib/docker/volumes/keep-me/_data';Destination='/opt/data';RW=$true;Propagation=''},
    [pscustomobject]@{Type='bind';Source='D:/workspace';Destination='/workspace';RW=$true;Propagation='rprivate'},
    [pscustomobject]@{Type='bind';Source='E:/outside';Destination='/outside';RW=$false;Propagation='rprivate'}
)
$global:FixtureRoot=$Root
function global:git {
    $A=@($args); $global:LASTEXITCODE=0
    [void]$global:FixtureCalls.Add('git '+($A -join ' '))
    switch ($A[0]) {
        'rev-parse' { if ($A[1] -eq '--show-toplevel') {$global:FixtureRoot} else {'fixture-sha'} }
        'status' { if ($global:FixtureMode -eq 'dirty') {' M user-file.txt'} }
        'branch' { 'refactor/lite-only-runtime' }
        default { throw 'Unexpected Git mutation in readonly fixture' }
    }
}
function global:docker {
    $A=@($args); $global:LASTEXITCODE=0
    [void]$global:FixtureCalls.Add('docker '+($A -join ' '))
    if ($A[0] -eq 'info') { 'fixture'; return }
    if ($A[0] -eq 'inspect') {
        $Mounts=$global:FixtureMounts
        if ($global:FixtureMode -eq 'mount-mismatch' -and $global:FixtureRecreated) {
            $Mounts=@([pscustomobject]@{Type='volume';Name='wrong-volume';Source='/wrong';Destination='/opt/data';RW=$true;Propagation=''})+$Mounts[1..2]
        }
        ConvertTo-Json -InputObject @([pscustomobject]@{Image='sha256:old';Mounts=$Mounts;State=[pscustomobject]@{Running=$true};Config=[pscustomobject]@{WorkingDir='/workspace'}}) -Depth 10 -Compress
        return
    }
    if ($A[0] -eq 'compose') {
        if ($A -contains '--format') {
            [pscustomobject]@{services=[pscustomobject]@{hermes=[pscustomobject]@{
                container_name='fixture-hermes';working_dir='/workspace';
                environment=[pscustomobject]@{HERMES_CONTAINER_CUSTOM_SKILLS_PATH='/opt/custom-skills'};
                volumes=@([pscustomobject]@{target='/opt/data'},[pscustomobject]@{target='/workspace'})
            }}} | ConvertTo-Json -Depth 10 -Compress
        }
        if ($A -contains 'build' -and $global:FixtureMode -eq 'build-fail') {$global:LASTEXITCODE=1}
        if ($A -contains 'up') { $global:FixtureRecreated=$true }
        return
    }
    if ($A[0] -eq 'run') {
        if ($A -notcontains '--read-only' -or $A -notcontains 'none' -or $A -notcontains 'fixture-hermes:ro') {
            throw 'Migration plan was not readonly/network-free'
        }
        if ($global:FixtureMode -eq 'active-worker') {$global:LASTEXITCODE=1}
        return
    }
    if ($A[0] -eq 'stop') { return }
    if ($A[0] -eq 'exec') {
        if ($A -contains 'printenv') {
            switch ($A[-1]) {
                'HERMES_GIT_USER_NAME' {'Fixture'}
                'HERMES_GIT_USER_EMAIL' {'fixture@example.invalid'}
                'GH_CONFIG_DIR' {'/opt/data/gh'}
            }
        }
        elseif ($A -contains '--get') { if ($A[-1] -eq 'user.name') {'Fixture'} else {'fixture@example.invalid'} }
        return
    }
    throw 'Unexpected Docker command in updater fixture'
}
function Run-Fixture([string]$Mode,[bool]$Fail) {
    $global:FixtureMode=$Mode; $global:FixtureRecreated=$false; $global:FixtureCalls.Clear()
    $Caught=$false
    try {
        & (Join-Path $Root 'update-devkit.ps1') -Container 'fixture-hermes' -Branch 'refactor/lite-only-runtime' -NoPull -SkipVerify -SkipGitHubAuth | Out-Null
    }
    catch { $Caught=$true; Write-Host "[FIXTURE] $Mode -> $($_.Exception.Message)" }
    if ($Caught -ne $Fail) { throw "Unexpected updater result: $Mode (failed=$Caught)" }
    return @($global:FixtureCalls.ToArray())
}
try {
    $Calls=Run-Fixture 'normal' $false
    if (@($Calls | Where-Object {$_ -like '* build --pull'}).Count -ne 1) { throw 'Latest was not built exactly once' }
    if (@($Calls | Where-Object {$_ -like 'docker run *'}).Count -ne 3) { throw 'Three readonly preflights required' }
    if (@($Calls | Where-Object {$_ -like '* up -d --force-recreate --no-build'}).Count -ne 1) { throw 'Expected one recreation' }
    foreach ($Mode in @('active-worker','build-fail','dirty')) {
        $Calls=Run-Fixture $Mode $true
        if (@($Calls | Where-Object {$_ -like 'docker stop *' -or $_ -like '* up -d *'}).Count) { throw "Current runtime changed after $Mode" }
    }
    $Calls=Run-Fixture 'mount-mismatch' $true
    if (@($Calls | Where-Object {$_ -like '* up -d *'}).Count -ne 1) { throw 'Mount mismatch triggered unsafe automatic repair' }
    Write-Host '[PASS] Updater success, dirty checkout, active worker, build failure and changed-mount fixtures'
}
finally {
    Remove-Item Function:\git -ErrorAction SilentlyContinue
    Remove-Item Function:\docker -ErrorAction SilentlyContinue
    $env:LOCALAPPDATA=$OriginalLocal
}
