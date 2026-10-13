#requires -Version 5.1

# Hermetic native-process regression: no real Docker, Hermes or network needed.
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "profile-init-probe.ps1")

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) {
        throw "Profile probe regression failed: $Message"
    }
}

$FixtureDir = Join-Path ([System.IO.Path]::GetTempPath()) (
    "hermes-profile-probe-" + [guid]::NewGuid().ToString("N")
)
$OriginalPath = $env:PATH
$OldScenario = $env:HERMES_PROFILE_PROBE_SCENARIO
$OldCounter = $env:HERMES_PROFILE_PROBE_COUNTER
$OldMarker = $env:HERMES_PROFILE_PROBE_TRANSIENT_MARKER
$IsWindowsHost = [System.IO.Path]::DirectorySeparatorChar -eq '\'

try {
    New-Item -ItemType Directory -Force -Path $FixtureDir | Out-Null
    $Counter = Join-Path $FixtureDir "attempts.txt"
    $Marker = Join-Path $FixtureDir "transient.done"
    $env:HERMES_PROFILE_PROBE_COUNTER = $Counter
    $env:HERMES_PROFILE_PROBE_TRANSIENT_MARKER = $Marker
    $Container = "hermes-dev"
    $HermesCliPath = "/opt/hermes/.venv/bin/hermes"

    if ($IsWindowsHost) {
        $Docker = Join-Path $FixtureDir "docker.cmd"
        $MockSource = @'
@echo off
echo called>>"%HERMES_PROFILE_PROBE_COUNTER%"
if "%HERMES_PROFILE_PROBE_SCENARIO%"=="success_warning" goto success_warning
if "%HERMES_PROFILE_PROBE_SCENARIO%"=="transient_lock" goto transient_lock
if "%HERMES_PROFILE_PROBE_SCENARIO%"=="permanent_lock" goto permanent_lock
if "%HERMES_PROFILE_PROBE_SCENARIO%"=="missing" goto missing
if "%HERMES_PROFILE_PROBE_SCENARIO%"=="missing_with_lock" goto missing_with_lock
if "%HERMES_PROFILE_PROBE_SCENARIO%"=="missing_wrong_exit" goto missing_wrong_exit
if "%HERMES_PROFILE_PROBE_SCENARIO%"=="docker_failure" goto docker_failure
if "%HERMES_PROFILE_PROBE_SCENARIO%"=="venv_failure" goto venv_failure
if "%HERMES_PROFILE_PROBE_SCENARIO%"=="missing_text_success" goto missing_text_success
exit /b 0
:success_warning
1>&2 echo install out of sync - venv mismatch
1>&2 echo dependency lock still held after 10.0s; continuing without it
exit /b 0
:transient_lock
if exist "%HERMES_PROFILE_PROBE_TRANSIENT_MARKER%" exit /b 0
echo done>"%HERMES_PROFILE_PROBE_TRANSIENT_MARKER%"
1>&2 echo dependency lock still held after 10.0s; continuing without it
exit /b 1
:permanent_lock
1>&2 echo dependency lock still held after 10.0s; continuing without it
exit /b 1
:missing
1>&2 echo Error: Profile 'coder' does not exist.
exit /b 1
:missing_with_lock
1>&2 echo Error: Profile 'coder' does not exist.
1>&2 echo dependency lock still held after 10.0s; continuing without it
exit /b 1
:missing_wrong_exit
1>&2 echo Error: Profile 'coder' does not exist.
exit /b 125
:docker_failure
1>&2 echo Cannot connect to the Docker daemon
exit /b 125
:venv_failure
1>&2 echo install out of sync - venv mismatch
exit /b 1
:missing_text_success
1>&2 echo Error: Profile 'coder' does not exist.
exit /b 0
'@
        Set-Content -LiteralPath $Docker -Value $MockSource -Encoding Ascii
    }
    else {
        $Docker = Join-Path $FixtureDir "docker"
        $MockSource = @'
#!/bin/sh
printf 'called\n' >> "$HERMES_PROFILE_PROBE_COUNTER"
case "$HERMES_PROFILE_PROBE_SCENARIO" in
    success_warning)
        printf '%s\n' 'install out of sync - venv mismatch' 'dependency lock still held after 10.0s; continuing without it' >&2
        exit 0 ;;
    transient_lock)
        if [ -e "$HERMES_PROFILE_PROBE_TRANSIENT_MARKER" ]; then exit 0; fi
        touch "$HERMES_PROFILE_PROBE_TRANSIENT_MARKER"
        echo 'dependency lock still held after 10.0s; continuing without it' >&2
        exit 1 ;;
    permanent_lock)
        echo 'dependency lock still held after 10.0s; continuing without it' >&2
        exit 1 ;;
    missing)
        echo "Error: Profile 'coder' does not exist." >&2
        exit 1 ;;
    missing_with_lock)
        echo "Error: Profile 'coder' does not exist." >&2
        echo 'dependency lock still held after 10.0s; continuing without it' >&2
        exit 1 ;;
    missing_wrong_exit)
        echo "Error: Profile 'coder' does not exist." >&2
        exit 125 ;;
    docker_failure)
        echo 'Cannot connect to the Docker daemon' >&2
        exit 125 ;;
    venv_failure)
        echo 'install out of sync - venv mismatch' >&2
        exit 1 ;;
    missing_text_success)
        echo "Error: Profile 'coder' does not exist." >&2
        exit 0 ;;
esac
exit 0
'@
        Set-Content -LiteralPath $Docker -Value $MockSource -Encoding Ascii
        & chmod +x $Docker
        Assert-True ($LASTEXITCODE -eq 0) "could not make fake docker executable"
    }

    $env:PATH = $FixtureDir + [System.IO.Path]::PathSeparator + $OriginalPath
    $Resolved = (Get-Command docker -CommandType Application).Source
    Assert-True ($Resolved -eq $Docker) "mock Docker is not the selected executable"

    function Reset-Scenario {
        param([string]$Scenario)
        $env:HERMES_PROFILE_PROBE_SCENARIO = $Scenario
        Remove-Item -LiteralPath $Counter -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $Marker -Force -ErrorAction SilentlyContinue
    }

    function Assert-Calls {
        param([int]$Expected, [string]$Scenario)
        $Count = if (Test-Path -LiteralPath $Counter) {
            @(Get-Content -LiteralPath $Counter).Count
        } else {
            0
        }
        Assert-True ($Count -eq $Expected) "$Scenario called Docker $Count times instead of $Expected"
    }

    function Assert-ProbeThrows {
        param([string]$ExpectedError)
        $Caught = $null
        try {
            $null = Profile-Exists -Name coder -MaxAttempts 3 -RetryDelaySeconds 0
        }
        catch {
            $Caught = $_.Exception.Message
        }
        Assert-True ($null -ne $Caught) "expected profile lookup to fail"
        Assert-True ($Caught.Contains($ExpectedError)) "unexpected error classification: $Caught"
        Assert-True ($ErrorActionPreference -eq "Stop") "ErrorActionPreference was not restored after failure"
    }

    Reset-Scenario "success_warning"
    Assert-True (Profile-Exists -Name coder -MaxAttempts 3 -RetryDelaySeconds 0) "stderr warning with exit 0 must succeed"
    Assert-Calls 1 "success_warning"
    Assert-True ($ErrorActionPreference -eq "Stop") "ErrorActionPreference was not restored after success"

    Reset-Scenario "transient_lock"
    Assert-True (Profile-Exists -Name coder -MaxAttempts 3 -RetryDelaySeconds 0) "temporary lock should recover"
    Assert-Calls 2 "transient_lock"

    Reset-Scenario "missing"
    Assert-True (-not (Profile-Exists -Name coder -MaxAttempts 3 -RetryDelaySeconds 0)) "exact absent profile should be recognized"
    Assert-Calls 1 "missing"

    Reset-Scenario "missing_text_success"
    Assert-True (Profile-Exists -Name coder -MaxAttempts 3 -RetryDelaySeconds 0) "successful exit code takes precedence over stderr text"
    Assert-Calls 1 "missing_text_success"

    Reset-Scenario "permanent_lock"
    Assert-ProbeThrows "PROFILE_DEPENDENCY_LOCK_BUSY"
    Assert-Calls 3 "permanent_lock"

    Reset-Scenario "missing_with_lock"
    Assert-ProbeThrows "PROFILE_DEPENDENCY_LOCK_BUSY"
    Assert-Calls 3 "missing_with_lock"

    foreach ($Scenario in @("missing_wrong_exit", "docker_failure", "venv_failure")) {
        Reset-Scenario $Scenario
        Assert-ProbeThrows "PROFILE_INSPECTION_FAILED"
        Assert-Calls 1 $Scenario
    }

    Write-Host "[PASS] Native stderr, bounded Hermes lock retries, missing profile and Docker error classification"
}
finally {
    $env:PATH = $OriginalPath
    $env:HERMES_PROFILE_PROBE_SCENARIO = $OldScenario
    $env:HERMES_PROFILE_PROBE_COUNTER = $OldCounter
    $env:HERMES_PROFILE_PROBE_TRANSIENT_MARKER = $OldMarker
    Remove-Item -LiteralPath $FixtureDir -Recurse -Force -ErrorAction SilentlyContinue
}
