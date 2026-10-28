#requires -Version 5.1
# No Docker daemon, remote Git, .env or user data access. Exercise the real updater orchestration.
Set-StrictMode -Version 2.0
$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $PSScriptRoot
$OriginalLocal=$env:LOCALAPPDATA
$OriginalHistoryExists=Test-Path Env:HERMES_DEVKIT_UPDATE_HISTORY_ROOT
$OriginalHistory=$env:HERMES_DEVKIT_UPDATE_HISTORY_ROOT
$FixtureHistoryRoot=Join-Path ([IO.Path]::GetTempPath()) ('devkit-updater-evidence-test-'+[Guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($FixtureHistoryRoot)
$env:LOCALAPPDATA='C:\Users\fixture\AppData\Local'
$global:FixtureCalls=New-Object System.Collections.ArrayList
$global:FixtureMode='normal'
$global:FixtureRecreated=$false
$global:FixtureBuildComplete=$false
$global:FixtureOldDigest="sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
$global:FixtureNewDigest="sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
$global:FixtureLegacyDigest="sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
$global:FixtureMounts=@(
    [pscustomobject]@{Type='volume';Name='keep-me';Source='/var/lib/docker/volumes/keep-me/_data';Destination='/opt/data';RW=$true;Propagation=''},
    [pscustomobject]@{Type='bind';Source='D:/workspace';Destination='/workspace';RW=$true;Propagation='rprivate'},
    [pscustomobject]@{Type='bind';Source='E:/outside';Destination='/outside';RW=$false;Propagation='rprivate'}
)
$global:FixtureRoot=$Root
function global:Assert-FixtureBeforeEvidence {
    if ($global:FixtureMode -like 'history-unavailable*') { return }
    $Saved=@(Get-ChildItem -LiteralPath $global:FixtureRunHistory -Filter 'before.json' -Recurse -File)
    if ($Saved.Count -ne 1) { throw 'Before mount evidence was not saved before a build/preflight/runtime operation' }
}
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
        if ($global:FixtureMode -in @('mount-mismatch','history-unavailable-mismatch') -and $global:FixtureRecreated) {
            $Mounts=@([pscustomobject]@{Type='volume';Name='wrong-volume';Source='/wrong';Destination='/opt/data';RW=$true;Propagation=''})+$Mounts[1..2]
        }
        if ($global:FixtureMode -eq 'mount-case-mismatch' -and $global:FixtureRecreated) {
            $Mounts=@($Mounts[0],[pscustomobject]@{Type='bind';Source='d:/workspace';Destination='/workspace';RW=$true;Propagation='rprivate'},$Mounts[2])
        }
        $Id=if ($global:FixtureRecreated) {'fixture-after'} else {'fixture-before'}
        $Image=if ($global:FixtureRecreated) {$global:FixtureNewDigest} else {$global:FixtureLegacyDigest}
        ConvertTo-Json -InputObject @([pscustomobject]@{
            Id=$Id;Image=$Image;Mounts=$Mounts;State=[pscustomobject]@{Running=$true}
            Config=[pscustomobject]@{WorkingDir='/workspace';Env=@('TOKEN=never-store-env-secret');Labels=@{secret='never-store-label-secret'}}
        }) -Depth 10 -Compress
        return
    }
    if ($A[0] -eq 'image' -and $A[1] -eq 'inspect') {
        if ($A[-1] -eq $global:FixtureLegacyDigest) {
            # The original image is untagged/pruned, as on the user's PC.
            $global:LASTEXITCODE=1; return
        }
        if ($A[-1] -ne 'hermes-dev:0.1.0') { throw "Unexpected image lookup: $($A[-1])" }
        if (-not $global:FixtureBuildComplete -and $global:FixtureMode -eq 'image-missing-before-build') {
            $global:LASTEXITCODE=1; return
        }
        if ($global:FixtureBuildComplete -and $global:FixtureMode -eq 'image-missing-after-build') {
            $global:LASTEXITCODE=1; return
        }
        if ($global:FixtureBuildComplete) { $global:FixtureNewDigest }
        else { $global:FixtureOldDigest }
        return
    }
    if ($A[0] -eq 'compose') {
        if ($A -contains '--format') {
            [pscustomobject]@{services=[pscustomobject]@{hermes=[pscustomobject]@{
                container_name='fixture-hermes';working_dir='/workspace';image='hermes-dev:0.1.0';
                environment=[pscustomobject]@{HERMES_CONTAINER_CUSTOM_SKILLS_PATH='/opt/custom-skills'};
                volumes=@([pscustomobject]@{target='/opt/data'},[pscustomobject]@{target='/workspace'})
            }}} | ConvertTo-Json -Depth 10 -Compress
        }
        if ($A -contains 'build') {
            Assert-FixtureBeforeEvidence
            if ($global:FixtureMode -eq 'build-fail') {$global:LASTEXITCODE=1}
            else {$global:FixtureBuildComplete=$true}
        }
        if ($A -contains 'up') { Assert-FixtureBeforeEvidence; $global:FixtureRecreated=$true }
        return
    }
    if ($A[0] -eq 'run') {
        Assert-FixtureBeforeEvidence
        if ($A -notcontains '--read-only' -or $A -notcontains 'none' -or $A -notcontains 'fixture-hermes:ro') {
            throw 'Migration plan was not readonly/network-free'
        }
        $Entry=[Array]::IndexOf($A,'--entrypoint')
        if ($Entry -lt 0) { throw 'Migration subprocess entrypoint was not explicit' }
        $ActualImage=$A[$Entry+2]
        $Expected=if ($global:FixtureBuildComplete) {$global:FixtureNewDigest} else {$global:FixtureOldDigest}
        if ($ActualImage -ne $Expected) { throw "Migration used stale image: $ActualImage instead of $Expected" }
        if ($global:FixtureMode -eq 'active-worker') {$global:LASTEXITCODE=1}
        return
    }
    if ($A[0] -eq 'stop') { Assert-FixtureBeforeEvidence; return }
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
    $global:FixtureMode=$Mode; $global:FixtureRecreated=$false; $global:FixtureBuildComplete=$false; $global:FixtureCalls.Clear()
    $global:FixtureRunHistory=Join-Path $FixtureHistoryRoot ($Mode+'-'+[Guid]::NewGuid().ToString('N'))
    if ($Mode -like 'history-unavailable*') { [IO.File]::WriteAllText($global:FixtureRunHistory,'owned test blocker') }
    else { [void][IO.Directory]::CreateDirectory($global:FixtureRunHistory) }
    $env:HERMES_DEVKIT_UPDATE_HISTORY_ROOT=$global:FixtureRunHistory
    $global:FixtureCaughtMessage=''
    $Caught=$false
    try {
        & (Join-Path $Root 'update-devkit.ps1') -Container 'fixture-hermes' -Branch 'refactor/lite-only-runtime' -NoPull -SkipVerify -SkipGitHubAuth | Out-Null
    }
    catch { $Caught=$true; $global:FixtureCaughtMessage=$_.Exception.Message; Write-Host "[FIXTURE] $Mode -> $($_.Exception.Message)" }
    if ($Caught -ne $Fail) { throw "Unexpected updater result: $Mode (failed=$Caught)" }
    return @($global:FixtureCalls.ToArray())
}
function Read-FixtureEvidence([string]$Phase) {
    $Saved=@(Get-ChildItem -LiteralPath $global:FixtureRunHistory -Filter ($Phase+'.json') -Recurse -File)
    if ($Saved.Count -ne 1) { throw "Expected one retained $Phase snapshot for $global:FixtureMode" }
    $Raw=Get-Content -LiteralPath $Saved[0].FullName -Raw
    if ($Raw -match 'never-store|"Config"|"Env"|"Labels"|"value"') { throw 'History exposed unrelated inspect data or an array wrapper' }
    return ConvertFrom-Json -InputObject $Raw
}
try {
    $Calls=Run-Fixture 'normal' $false
    $Before=Read-FixtureEvidence 'before'
    $After=Read-FixtureEvidence 'after'
    if ($Before.container_id -cne 'fixture-before' -or $After.container_id -cne 'fixture-after' -or
        $Before.image_id -cne $global:FixtureLegacyDigest -or $After.image_id -cne $global:FixtureNewDigest -or
        $Before.mounts -isnot [array] -or $Before.mounts.Count -ne 3 -or $After.mounts.Count -ne 3 -or
        -not $After.comparison.matches) { throw 'Normal updater evidence did not retain the original and recreated identities' }
    $FirstHistory=$global:FixtureRunHistory
    if (@($Calls | Where-Object {$_ -like '* build --pull'}).Count -ne 1) { throw 'Latest was not built exactly once' }
    if (@($Calls | Where-Object {$_ -like 'docker run *'}).Count -ne 3) { throw 'Three readonly preflights required' }
    if (@($Calls | Where-Object {$_ -like '* up -d --force-recreate --no-build'}).Count -ne 1) { throw 'Expected one recreation' }
    if (@($Calls | Where-Object {$_ -like '* image inspect *'}).Count -ne 2) { throw 'Pre/post build tagged image lookup missing' }
    if (@($Calls | Where-Object {$_ -like '* image inspect *' + $global:FixtureLegacyDigest}).Count) {
        throw 'Obsolete container image was queried despite a usable tagged image'
    }
    if (@($Calls | Where-Object {$_ -eq 'docker inspect fixture-hermes'}).Count -ne 2) { throw 'History introduced another container inspection' }
    $Skipped=Run-Fixture 'image-missing-before-build' $false
    if (@($Skipped | Where-Object {$_ -like 'docker run *'}).Count -ne 2) { throw 'Both mandatory post-build gates missing after pre-build image lookup failed' }
    if (@($Skipped | Where-Object {$_ -like '* image inspect *' + $global:FixtureLegacyDigest}).Count -ne 1) {
        throw 'Missing tagged image did not trigger safe old-image fallback'
    }
    if (@(Get-ChildItem -LiteralPath $FirstHistory -Filter '*.json' -Recurse -File).Count -ne 2) { throw 'Another updater run removed previous history' }
    foreach ($Mode in @('active-worker','build-fail','dirty','image-missing-after-build')) {
        $Calls=Run-Fixture $Mode $true
        if (@($Calls | Where-Object {$_ -like 'docker stop *' -or $_ -like '* up -d *'}).Count) { throw "Current runtime changed after $Mode" }
        if ($Mode -ne 'dirty') { [void](Read-FixtureEvidence 'before') }
        if (@(Get-ChildItem -LiteralPath $global:FixtureRunHistory -Filter 'after.json' -Recurse -File).Count) {
            throw "After snapshot was invented before recreation after $Mode"
        }
    }
    $Calls=Run-Fixture 'mount-mismatch' $true
    if (@($Calls | Where-Object {$_ -like '* up -d *'}).Count -ne 1) { throw 'Mount mismatch triggered unsafe automatic repair' }
    $Before=Read-FixtureEvidence 'before'
    $After=Read-FixtureEvidence 'after'
    if ($Before.mounts[0].Name -cne 'keep-me' -or $After.mounts[0].Name -cne 'wrong-volume' -or
        $After.comparison.matches -or $After.comparison.before_only.Count -ne 1 -or $After.comparison.after_only.Count -ne 1 -or
        $global:FixtureCaughtMessage -notlike 'Mount identity changed after recreation.*') {
        throw 'Mismatch history or original failure was lost'
    }
    [void](Run-Fixture 'mount-case-mismatch' $true)
    $After=Read-FixtureEvidence 'after'
    if ($After.comparison.matches -or
        $After.comparison.before_only -cnotcontains 'bind|D:/workspace|/workspace|True|rprivate' -or
        $After.comparison.after_only -cnotcontains 'bind|d:/workspace|/workspace|True|rprivate') {
        throw 'Updater history hid a case-only mismatch'
    }
    [void](Run-Fixture 'history-unavailable' $false)
    [void](Run-Fixture 'history-unavailable-mismatch' $true)
    if ($global:FixtureCaughtMessage -notlike 'Mount identity changed after recreation.*') { throw 'History failure hid the original mount error' }
    Write-Host '[PASS] Image digest pinned after rebuild; pruned old image; missing image fallback; readonly plans; mount/dirty/build/worker guards'
    Write-Host '[PASS] Before/after mount history survives success and failure without changing updater decisions or exposing credentials'
}
finally {
    Remove-Item Function:\git -ErrorAction SilentlyContinue
    Remove-Item Function:\docker -ErrorAction SilentlyContinue
    Remove-Item Function:\Assert-FixtureBeforeEvidence -ErrorAction SilentlyContinue
    $env:LOCALAPPDATA=$OriginalLocal
    if ($OriginalHistoryExists) { $env:HERMES_DEVKIT_UPDATE_HISTORY_ROOT=$OriginalHistory }
    else { Remove-Item Env:HERMES_DEVKIT_UPDATE_HISTORY_ROOT -ErrorAction SilentlyContinue }
    if (Test-Path -LiteralPath $FixtureHistoryRoot) { Remove-Item -LiteralPath $FixtureHistoryRoot -Recurse -Force }
}
