# instrumented_skills install script (Windows / PowerShell)
# Run from the root of this repo (or point -Source at it). Copies each selected skill
# folder to %USERPROFILE%\.claude\skills\<name>, archiving whatever it replaces first.
#
# Usage:
#   .\install.ps1                                   # installs all five skills
#   .\install.ps1 -Skills critique,kb-search         # installs only the ones named
#
# If Windows blocks the script (downloaded from a zip), unblock it first:
#   Unblock-File .\install.ps1
#   powershell -ExecutionPolicy Bypass -File .\install.ps1

param(
    [string[]]$Skills = @("critique", "retrospective", "handoff", "kb-search", "close-session"),
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

# close-session composes retrospective/critique/handoff; it degrades gracefully without
# them (runs each missing phase's shape inline, per its own SKILL.md), so this is informational.
if ($Skills -contains "close-session") {
    foreach ($companion in @("retrospective", "critique", "handoff")) {
        if (-not ($Skills -contains $companion)) {
            Write-Host "  NOTE: installing close-session without $companion. It still works," -ForegroundColor Yellow
            Write-Host "        running that phase inline at reduced quality; install $companion too"
            Write-Host "        for the full protocol."
        }
    }
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
Write-Host "(registering retrospective's and handoff's optional hooks if you want them)."
