#requires -Version 5.1

param(
    [string]$Container = "hermes-dev"
)

$ErrorActionPreference = "Stop"

function Invoke-DockerCheck {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,
        [Parameter(Mandatory = $true)]
        [string[]]$DockerArgs
    )

    & docker @DockerArgs
    if ($LASTEXITCODE -ne 0) {
        throw "[FAIL] $Label. The running container does not match the current DevKit image. Rebuild with: docker compose build --no-cache; docker compose up -d --force-recreate"
    }
    Write-Host "[OK] $Label"
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI was not found."
}

$PreviousPreference = $ErrorActionPreference
try {
    $ErrorActionPreference = "SilentlyContinue"
    & docker inspect $Container 1>$null 2>$null
    $InspectExitCode = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $PreviousPreference
}

if ($InspectExitCode -ne 0) {
    throw "Container '$Container' does not exist. Start it first with: docker compose up -d --force-recreate"
}

$JavaHome = (& docker exec --user hermes $Container printenv JAVA_HOME 2>$null | Select-Object -First 1).Trim()
if ($LASTEXITCODE -ne 0 -or $JavaHome -ne "/opt/jdks/temurin-17") {
    throw "[FAIL] JAVA_HOME. Expected /opt/jdks/temurin-17, got '$JavaHome'. Rebuild/recreate the DevKit container."
}
Write-Host "[OK] JAVA_HOME -> $JavaHome"

Invoke-DockerCheck -Label "Default Java 17 command" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "/usr/local/bin/java", "-version"
)
Invoke-DockerCheck -Label "Default javac 17 command" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "/usr/local/bin/javac", "-version"
)
Invoke-DockerCheck -Label "Temurin JDK 8 java" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "/opt/jdks/temurin-8/bin/java", "-version"
)
Invoke-DockerCheck -Label "Temurin JDK 8 javac" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "/opt/jdks/temurin-8/bin/javac", "-version"
)
Invoke-DockerCheck -Label "Temurin JDK 17 java" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "/opt/jdks/temurin-17/bin/java", "-version"
)
Invoke-DockerCheck -Label "Temurin JDK 17 javac" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "/opt/jdks/temurin-17/bin/javac", "-version"
)
Invoke-DockerCheck -Label "Temurin JDK 21 java" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "/opt/jdks/temurin-21/bin/java", "-version"
)
Invoke-DockerCheck -Label "Temurin JDK 21 javac" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "/opt/jdks/temurin-21/bin/javac", "-version"
)
Invoke-DockerCheck -Label "hermes-java launcher" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "test", "-x", "/usr/local/bin/hermes-java"
)
Invoke-DockerCheck -Label "Reviewer capability root" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "test", "-f", "/opt/reviewer-skills/dev-spring-test/SKILL.md"
)
Invoke-DockerCheck -Label "Reviewer guidelines capability" -DockerArgs @(
    "exec", "--user", "hermes", $Container, "test", "-f", "/opt/reviewer-skills/dev-spring-guidelines/SKILL.md"
)

Write-Host "[PASS] Hermes container runtime matches the current DevKit contract."
