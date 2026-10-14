#requires -Version 5.1

# Read-only Hermes profile probe. The parent script supplies $Container and
# $HermesCliPath; it alone decides whether to create a missing profile.
function Profile-Exists {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [ValidateRange(1, 5)]
        [int]$MaxAttempts = 3,

        [ValidateRange(0, 30)]
        [int]$RetryDelaySeconds = 2
    )

    $MissingProfileMessage = "Error: Profile '$Name' does not exist."
    $DependencyLockPattern = 'dependency lock still held after\s+[0-9]+(?:\.[0-9]+)?s;\s*continuing without it'

    for ($Attempt = 1; $Attempt -le $MaxAttempts; $Attempt++) {
        # Windows PowerShell 5.1 can turn redirected native stderr (2>&1)
        # into a terminating NativeCommandError under the script's Stop policy.
        # Capture stderr as diagnostic data, then decide using LASTEXITCODE.
        $PreviousPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = "Continue"
            $ProbeLines = @(
                & docker exec --user hermes $Container $HermesCliPath profile show $Name 2>&1
            )
            $ExitCode = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $PreviousPreference
        }

        $ProbeText = ($ProbeLines | ForEach-Object { [string]$_ }) -join [Environment]::NewLine

        # Hermes can emit a benign install-lock warning on stderr and still
        # successfully show an existing profile. stderr is not an exit code.
        if ($ExitCode -eq 0) {
            return $true
        }

        # Lock contention and missing-profile output can appear together while
        # another Hermes process is activating dependencies. Never create a
        # profile from an ambiguous, lock-contended probe.
        if ([regex]::IsMatch($ProbeText, $DependencyLockPattern)) {
            if ($Attempt -lt $MaxAttempts) {
                Write-Warning (
                    "Hermes dependency lock busy during profile lookup '$Name'; " +
                    "retrying attempt $($Attempt + 1)/$MaxAttempts."
                )
                if ($RetryDelaySeconds -gt 0) {
                    Start-Sleep -Seconds $RetryDelaySeconds
                }
                continue
            }
            throw (
                "PROFILE_DEPENDENCY_LOCK_BUSY: Unable to inspect profile '$Name' " +
                "after $MaxAttempts attempts (ExitCode=$ExitCode). " +
                "Wait for the in-progress Hermes installation to finish and retry initialization."
            )
        }

        # Upstream profile show reports an absent profile as exit 1 plus this
        # exact message. Docker failures (125/126/127), CLI crashes and venv
        # errors are NOT evidence that the profile is missing.
        if ($ExitCode -eq 1 -and $ProbeText.Contains($MissingProfileMessage)) {
            return $false
        }

        throw (
            "PROFILE_INSPECTION_FAILED: Could not inspect profile '$Name' " +
            "(ExitCode=$ExitCode). This is not a confirmed missing profile; " +
            "profile creation is blocked. Inspect Hermes CLI and container logs."
        )
    }
}
