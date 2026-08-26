#requires -Version 5.1

param(
    [string]$Container = "hermes-dev"
)

$ErrorActionPreference = "Stop"

function Invoke-ContainerCheck {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,
        [Parameter(Mandatory = $true)]
        [string]$Command
    )

    & docker exec --user hermes $Container sh -lc $Command
    if ($LASTEXITCODE -ne 0) {
        throw "[FAIL] $Label. The running container does not match the current DevKit image. Rebuild with: docker compose build --no-cache; docker compose up -d --force-recreate"
    }
    Write-Host "[OK] $Label"
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI was not found."
}

& docker inspect $Container 1>$null 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Container '$Container' does not exist."
}

Invoke-ContainerCheck -Label "Default Java is Java 17" -Command 'test "$(java -version 2>&1 | head -n 1)" != "" && test "$JAVA_HOME" = "/opt/jdks/temurin-17"'
Invoke-ContainerCheck -Label "Temurin JDK 8" -Command '/opt/jdks/temurin-8/bin/java -version >/dev/null 2>&1 && /opt/jdks/temurin-8/bin/javac -version >/dev/null 2>&1'
Invoke-ContainerCheck -Label "Temurin JDK 17" -Command '/opt/jdks/temurin-17/bin/java -version >/dev/null 2>&1 && /opt/jdks/temurin-17/bin/javac -version >/dev/null 2>&1'
Invoke-ContainerCheck -Label "Temurin JDK 21" -Command '/opt/jdks/temurin-21/bin/java -version >/dev/null 2>&1 && /opt/jdks/temurin-21/bin/javac -version >/dev/null 2>&1'
Invoke-ContainerCheck -Label "hermes-java launcher" -Command 'test -x /usr/local/bin/hermes-java'
Invoke-ContainerCheck -Label "Reviewer capability root" -Command 'test -d /opt/reviewer-skills && test -f /opt/reviewer-skills/dev-spring-test/SKILL.md && test -f /opt/reviewer-skills/dev-spring-guidelines/SKILL.md'

Write-Host "[PASS] Hermes container runtime matches the current DevKit contract."
