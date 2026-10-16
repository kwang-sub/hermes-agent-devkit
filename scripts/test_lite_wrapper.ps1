#requires -Version 5.1
<#
.DESCRIPTION
End-to-end control-flow regression of updatekit_lite.ps1 under Windows
PowerShell 5.1 using a fake Docker function. Does NOT contact Docker, does
NOT modify Hermes data, and uses real Git only for read-only root checking.
#>
Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Updater = Join-Path $RepoRoot "updatekit_lite.ps1"
$PriorLocation = Get-Location

function Reset-MockState {
    $global:LiteMockDataType = "volume"
    $global:LiteMockDataRW = $true
    $global:LiteMockSkillsPresent = $true
    $global:LiteMockPolicyPresent = $true
    $global:LiteMockActiveWorker = $false
    $global:LiteMockLiteActive = $false
    $global:LiteMockHelpWorks = $true
    $global:LiteMockApplyCount = 0
    $global:LiteMockRestoreCount = 0
    $global:LiteMockGuardCount = 0
    $global:LiteMockStatusCount = 0
    $global:LiteMockLastDockerCommand = ""
}

# Shadow Docker in this test session; the updater resolves the function, not
# docker.exe. Every mock action sets LASTEXITCODE just as a native process does.
function docker {
    param([Parameter(ValueFromRemainingArguments=$true)][string[]]$CommandArguments)
    $global:LiteMockLastDockerCommand = ($CommandArguments -join " ")
    $global:LASTEXITCODE = 0
    if ($CommandArguments.Count -eq 0) {
        throw "Unexpected empty mock Docker argv"
    }
    switch ($CommandArguments[0]) {
        "inspect" {
            $Format = $CommandArguments[2]
            switch ($Format) {
                "{{.State.Running}}" { "true"; return }
                "{{.Config.WorkingDir}}" { "/workspace"; return }
                "{{json .Mounts}}" {
                    $Source = if ($global:LiteMockDataType -eq "volume") {
                        "/var/lib/docker/volumes/hermes-dev-data/_data"
                    } else {
                        "D:/HermesPersistent"
                    }
                    $Mounts = @(
                        [pscustomobject]@{
                            Type=$global:LiteMockDataType;Name="hermes-dev-data"
                            Source=$Source;Destination="/opt/data";RW=$global:LiteMockDataRW
                        },
                        [pscustomobject]@{
                            Type="bind";Source="D:/workspace"
                            Destination="/workspace";RW=$true
                        },
                        [pscustomobject]@{
                            Type="bind";Source="D:/workspace/devkit/custom-skills"
                            Destination="/opt/custom-skills";RW=$false
                        },
                        [pscustomobject]@{
                            Type="bind";Source="D:/workspace/devkit/shared"
                            Destination="/opt/data/shared";RW=$false
                        },
                        [pscustomobject]@{
                            Type="bind";Source="C:/WindowsTemp"
                            Destination="/mnt/c/WindowsTemp";RW=$false
                        }
                    )
                    ConvertTo-Json -InputObject $Mounts -Compress -Depth 5
                    return
                }
                default { throw "Unexpected mock inspect format: $Format" }
            }
        }
        "cp" {
            return
        }
        "exec" {
            $Executable = $CommandArguments[4]
            if ($Executable -eq "test") {
                $Path = $CommandArguments[6]
                if ($Path -eq "/opt/custom-skills/lite/dev-lite-session/SKILL.md" -and
                    -not $global:LiteMockSkillsPresent) {
                    $global:LASTEXITCODE = 1
                }
                if ($Path -match "/hermes-agent-devkit/lite/AGENTS.md$" -and
                    -not $global:LiteMockPolicyPresent) {
                    $global:LASTEXITCODE = 1
                }
                return
            }
            if ($Executable -eq "/opt/hermes/.venv/bin/hermes") {
                if (-not $global:LiteMockHelpWorks) {
                    $global:LASTEXITCODE = 1
                    return
                }
                "Hermes CLI mock help"
                return
            }
            if ($Executable -eq "/opt/hermes/.venv/bin/python") {
                $Action = $CommandArguments[6]
                switch ($Action) {
                    "guard" {
                        $global:LiteMockGuardCount++
                        if ($global:LiteMockActiveWorker) { $global:LASTEXITCODE = 1 }
                    }
                    "status" {
                        $global:LiteMockStatusCount++
                        if ($global:LiteMockLiteActive) {
                            '{"lite":true,"profile_fields_match":true}'
                        }
                        else {
                            '{"lite":false,"profile_fields_match":null}'
                        }
                    }
                    "apply" {
                        $global:LiteMockApplyCount++
                        if ($global:LiteMockActiveWorker) { $global:LASTEXITCODE = 1 }
                        else { $global:LiteMockLiteActive = $true }
                    }
                    "restore" {
                        $global:LiteMockRestoreCount++
                        $global:LiteMockLiteActive = $false
                    }
                    default { throw "Unexpected Lite Python action: $Action" }
                }
                return
            }
            throw "Unknown mock Docker exec: $global:LiteMockLastDockerCommand"
        }
        default {
            throw "Unknown mock Docker command: $global:LiteMockLastDockerCommand"
        }
    }
}

function Assert-True {
    param([bool]$Condition, [string]$Reason)
    if (-not $Condition) { throw "Lite integration check failed: $Reason" }
}
function Expect-Error {
    param([scriptblock]$Operation, [string]$MustContain)
    $Message = $null
    try { & $Operation | Out-Null } catch { $Message = $_.Exception.Message }
    if ($null -eq $Message -or $Message -notlike "*$MustContain*") {
        throw "Expected '$MustContain' but observed '$Message'"
    }
}

try {
    Set-Location -LiteralPath $RepoRoot

    Reset-MockState
    & $Updater -Mode lite | Out-Null
    Assert-True ($global:LiteMockLiteActive -and $global:LiteMockApplyCount -eq 1) "named volume Lite apply"
    & $Updater -Mode status | Out-Null
    Assert-True ($global:LiteMockStatusCount -gt 0) "status query"
    & $Updater -Mode standard | Out-Null
    Assert-True (-not $global:LiteMockLiteActive -and $global:LiteMockRestoreCount -eq 1) "Standard return"

    Reset-MockState
    $global:LiteMockDataType = "bind"
    & $Updater -Mode lite -WarningAction SilentlyContinue | Out-Null
    Assert-True ($global:LiteMockLiteActive -and $global:LiteMockApplyCount -eq 1) "host-bind /opt/data Lite apply"

    Reset-MockState
    $global:LiteMockDataType = "tmpfs"
    Expect-Error -MustContain "Unsupported mount" -Operation { & $Updater -Mode lite }
    Assert-True ($global:LiteMockApplyCount -eq 0) "tmpfs must not apply Lite"

    Reset-MockState
    $global:LiteMockDataRW = $false
    Expect-Error -MustContain "read-only" -Operation { & $Updater -Mode lite }
    Assert-True ($global:LiteMockApplyCount -eq 0) "read-only data must not be changed"

    Reset-MockState
    $global:LiteMockSkillsPresent = $false
    Expect-Error -MustContain "Command failed" -Operation { & $Updater -Mode lite }
    Assert-True ($global:LiteMockApplyCount -eq 0) "missing Lite skill must not change profile"

    Reset-MockState
    $global:LiteMockPolicyPresent = $false
    Expect-Error -MustContain "Command failed" -Operation { & $Updater -Mode lite }
    Assert-True ($global:LiteMockApplyCount -eq 0) "missing Lite AGENTS must not change profile"

    Reset-MockState
    $global:LiteMockHelpWorks = $false
    Expect-Error -MustContain "Command failed" -Operation { & $Updater -Mode lite -WarningAction SilentlyContinue }
    Assert-True ($global:LiteMockApplyCount -eq 1 -and $global:LiteMockRestoreCount -eq 1 -and -not $global:LiteMockLiteActive) "failed first apply must roll back"

    Reset-MockState
    $global:LiteMockLiteActive = $true
    $global:LiteMockHelpWorks = $false
    Expect-Error -MustContain "Command failed" -Operation { & $Updater -Mode lite -WarningAction SilentlyContinue }
    Assert-True ($global:LiteMockRestoreCount -eq 0 -and $global:LiteMockLiteActive) "existing Lite config must survive re-run failure"

    Reset-MockState
    $global:LiteMockActiveWorker = $true
    Expect-Error -MustContain "Command failed" -Operation { & $Updater -Mode lite }
    Assert-True ($global:LiteMockApplyCount -eq 0 -and $global:LiteMockGuardCount -eq 1) "active Worker guard"

    Reset-MockState
    $global:LiteMockSkillsPresent = $false
    $global:LiteMockPolicyPresent = $false
    $global:LiteMockLiteActive = $true
    & $Updater -Mode standard | Out-Null
    Assert-True (-not $global:LiteMockLiteActive) "Standard return must not require Lite skill files"

    Write-Host "[PASS] Full Lite updater flow: volume/bind, status, apply, restore, rollback, active worker and missing mounts"
}
finally {
    Set-Location $PriorLocation
}
