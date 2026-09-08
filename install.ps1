# instrumented_skills install script (Windows / PowerShell)
# Run from the root of this repo (or point -Source at it). Copies each selected skill
# folder to %USERPROFILE%\.claude\skills\<name>, archiving whatever it replaces first.
#
# Usage:
#   .\install.ps1                                   # installs all five skills
#   .\install.ps1 -Skills critique,token-aware       # installs only the ones named
#
# If Windows blocks the script (downloaded from a zip), unblock it first:
#   Unblock-File .\install.ps1
#   powershell -ExecutionPolicy Bypass -File .\install.ps1

param(
    [string[]]$Skills = @("critique", "token-aware", "retrospective", "handoff", "kb-search"),
    [string]$Source = $PSScriptRoot,
    [string]$Destination = "$env:USERPROFILE\.claude\skills"
)

$ErrorActionPreference = "Stop"
$stamp = Get-Date -Format "yyyyMMdd-HHmm"

Write-Host "Preflight:"
$missing = @($Skills | Where-Object { -not (Test-Path (Join-Path $Source "$_\SKILL.md")) })
if ($missing.Count -gt 0) {
    Write-Host "  Missing SKILL.md for: $($missing -join ', ')" -ForegroundColor Red
    Write-Host "  Nothing was copied. Check the -Skills list and that $Source is the repo root."
    exit 1
}
Write-Host "  all requested skill folders present: $($Skills -join ', ')"

# kb-search defers its grep-first gating rule to token-aware\references\search_policy.md.
if (($Skills -contains "kb-search") -and -not ($Skills -contains "token-aware")) {
    Write-Host "  NOTE: installing kb-search without token-aware. Its search policy" -ForegroundColor Yellow
    Write-Host "        (token-aware\references\search_policy.md) is a hard dependency; install token-aware too."
}

New-Item -ItemType Directory -Force -Path $Destination | Out-Null
Write-Host "`nInstalling to $Destination :"
foreach ($skill in $Skills) {
    $from = Join-Path $Source $skill
    $to = Join-Path $Destination $skill
    if (Test-Path $to) {
        $backup = "$to.bak-$stamp"
        Copy-Item $to $backup -Recurse -Force
        # Gate the removal on the backup existing, so a failed archive never
        # deletes an existing install without a copy to fall back on.
        if (-not (Test-Path $backup)) {
            Write-Host "  ERROR: backup of $skill failed; leaving existing install untouched." -ForegroundColor Red
            exit 1
        }
        Remove-Item $to -Recurse -Force
        Write-Host "  archived existing $skill -> $skill.bak-$stamp"
    }
    Copy-Item $from $to -Recurse -Force
    Write-Host "  installed $skill"
}

Write-Host "`nDone. Read each skill's README.md for setup steps that can't be scripted"
Write-Host "(filling in token-aware\tools\rates.json with current, verified rates, and"
Write-Host "registering retrospective's and handoff's optional hooks if you want them)."

if ($Skills -contains "token-aware") {
    Write-Host "`nRunning token-aware's test suite as a sanity check:"
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        Push-Location (Join-Path $Destination "token-aware\tools")
        try {
            & python -m pytest -q 2>&1 | Select-Object -Last 5
        } finally { Pop-Location }
    } else {
        Write-Host "  SKIPPED: python not on PATH. Run 'python -m pytest -q' in token-aware\tools yourself."
    }
}
