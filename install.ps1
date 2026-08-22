param(
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$source = Join-Path $repoRoot '.agents\skills\ai-dg-estimator'
$skillsRoot = Join-Path $HOME '.agents\skills'
$destination = Join-Path $skillsRoot 'ai-dg-estimator'

if (-not (Test-Path $source)) {
    throw "Skill source not found: $source"
}

New-Item -ItemType Directory -Force -Path $skillsRoot | Out-Null

if (Test-Path $destination) {
    if (-not $Force) {
        throw "Skill already installed at $destination. Re-run with -Force to replace it."
    }
    Remove-Item -Recurse -Force $destination
}

Copy-Item -Recurse -Force $source $destination

Write-Host "Installed AI-dg skill to: $destination"
Write-Host "Codex and OpenCode can both discover ~/.agents/skills/ai-dg-estimator."
Write-Host "Restart the agent app/CLI if the skill does not appear immediately."
