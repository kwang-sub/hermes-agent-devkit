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
    $script:DataType = "volume"
    $script:DataRW = $true
    $script:SkillsPresent = $true
    $script:PolicyPresent = $true
    $script:ActiveWorker = $false
    $script:LiteActive = $false
    $script:HelpWorks = $true
    $script:ApplyCount = 0
    $script:RestoreCount = 0
    $script:GuardCount = 0
    $script:StatusCount = 0
    $script:LastDockerCommand = ""
}

# Shadow Docker in this test session; the updater resolves the function, not
# docker.exe. Every mock action sets LASTEXITCODE just as a native process does.
function docker {
    param([Parameter(ValueFromRemainingArguments=$true)][string[]]$CommandArguments)
    $script:LastDockerCommand = ($CommandArguments -join " ")
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
                    $Source = if ($script:DataType -eq "volume") {
                        "/var/lib/docker/volumes/hermes-dev-data/_data"
                    } else {
                        "D:/HermesPersistent"
                    }
                    $Mounts = @(
                        [pscustomobject]@{
                            Type=$script:DataType;Name="hermes-dev-data"
                            Source=$Source;Destination="/opt/data";RW=$script:DataRW
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
                    -not $script:SkillsPresent) {
                    $global:LASTEXITCODE = 1
                }
                if ($Path -match "/hermes-agent-devkit/lite/AGENTS.md$" -and
                    -not $script:PolicyPresent) {
                    $global:LASTEXITCODE = 1
                }
                return
            }
            if ($Executable -eq "/opt/hermes/.venv/bin/hermes") {
                if (-not $script:HelpWorks) {
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
                        $script:GuardCount++
                        if ($script:ActiveWorker) { $global:LASTEXITCODE = 1 }
                    }
                    "status" {
                        $script:StatusCount++
                        if ($script:LiteActive) {
                            '{"lite":true,"profile_fields_match":true}'
                        }
                        else {
                            '{"lite":false,"profile_fields_match":null}'
                        }
                    }
                    "apply" {
                        $script:ApplyCount++
                        if ($script:ActiveWorker) { $global:LASTEXITCODE = 1 }
                        else { $script:LiteActive = $true }
                    }
                    "restore" {
                        $script:RestoreCount++
                        $script:LiteActive = $false
                    }
                    default { throw "Unexpected Lite Python action: $Action" }
                }
                return
            }
            throw "Unknown mock Docker exec: $script:LastDockerCommand"
        }
        default {
            throw "Unknown mock Docker command: $script:LastDockerCommand"
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
    Assert-True ($script:LiteActive -and $script:ApplyCount -eq 1) "named volume Lite apply"
    & $Updater -Mode status | Out-Null
    Assert-True ($script:StatusCount -gt 0) "status query"
    & $Updater -Mode standard | Out-Null
    Assert-True (-not $script:LiteActive -and $script:RestoreCount -eq 1) "Standard return"

    Reset-MockState
    $script:DataType = "bind"
    & $Updater -Mode lite -WarningAction SilentlyContinue | Out-Null
    Assert-True ($script:LiteActive -and $script:ApplyCount -eq 1) "host-bind /opt/data Lite apply"

    Reset-MockState
    $script:DataType = "tmpfs"
    Expect-Error -MustContain "Unsupported mount" -Operation { & $Updater -Mode lite }
    Assert-True ($script:ApplyCount -eq 0) "tmpfs must not apply Lite"

    Reset-MockState
    $script:DataRW = $false
    Expect-Error -MustContain "read-only" -Operation { & $Updater -Mode lite }
    Assert-True ($script:ApplyCount -eq 0) "read-only data must not be changed"

    Reset-MockState
    $script:SkillsPresent = $false
    Expect-Error -MustContain "Command failed" -Operation { & $Updater -Mode lite }
    Assert-True ($script:ApplyCount -eq 0) "missing Lite skill must not change profile"

    Reset-MockState
    $script:PolicyPresent = $false
    Expect-Error -MustContain "Command failed" -Operation { & $Updater -Mode lite }
    Assert-True ($script:ApplyCount -eq 0) "missing Lite AGENTS must not change profile"

    Reset-MockState
    $script:HelpWorks = $false
    Expect-Error -MustContain "Command failed" -Operation { & $Updater -Mode lite -WarningAction SilentlyContinue }
    Assert-True ($script:ApplyCount -eq 1 -and $script:RestoreCount -eq 1 -and -not $script:LiteActive) "failed first apply must roll back"

    Reset-MockState
    $script:LiteActive = $true
    $script:HelpWorks = $false
    Expect-Error -MustContain "Command failed" -Operation { & $Updater -Mode lite -WarningAction SilentlyContinue }
    Assert-True ($script:RestoreCount -eq 0 -and $script:LiteActive) "existing Lite config must survive re-run failure"

    Reset-MockState
    $script:ActiveWorker = $true
    Expect-Error -MustContain "Command failed" -Operation { & $Updater -Mode lite }
    Assert-True ($script:ApplyCount -eq 0 -and $script:GuardCount -eq 1) "active Worker guard"

    Reset-MockState
    $script:SkillsPresent = $false
    $script:PolicyPresent = $false
    $script:LiteActive = $true
    & $Updater -Mode standard | Out-Null
    Assert-True (-not $script:LiteActive) "Standard return must not require Lite skill files"

    Write-Host "[PASS] Full Lite updater flow: volume/bind, status, apply, restore, rollback, active worker and missing mounts"
}
finally {
    Set-Location $PriorLocation
}
