# claude-skills install script (Windows / PowerShell)
# Run from the root of this repo (or point -Source at it). Copies each selected skill
# folder to %USERPROFILE%\.claude\skills\<name>, archiving whatever it replaces first.
#
# Usage:
#   .\install.ps1                                   # installs all four skills
#   .\install.ps1 -Skills critique,token-aware       # installs only the ones named
#
# If Windows blocks the script (downloaded from a zip), unblock it first:
#   Unblock-File .\install.ps1
#   powershell -ExecutionPolicy Bypass -File .\install.ps1

param(
    [string[]]$Skills = @("critique", "token-aware", "retrospective", "handoff"),
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

Write-Host "`nInstalling to $Destination :"
foreach ($skill in $Skills) {
    $from = Join-Path $Source $skill
    $to = Join-Path $Destination $skill
    if (Test-Path $to) {
        Copy-Item $to "$to.bak-$stamp" -Recurse -Force
        Write-Host "  archived existing $skill -> $skill.bak-$stamp"
    }
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    Copy-Item $from $to -Recurse -Force
    Write-Host "  installed $skill"
}

Write-Host "`nDone. Read each skill's README.md for setup steps that can't be scripted"
Write-Host "(filling in token-aware/tools/rates.json, authoring the placeholder SKILL.md"
Write-Host "files flagged in token-aware and retrospective, reviewing handoff's"
Write-Host "reconstructed SKILL.md)."

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
