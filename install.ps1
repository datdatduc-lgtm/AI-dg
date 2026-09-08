param(
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$source = Join-Path $repoRoot '.agents\skills\ai-dg-estimator'
$userProfileRoot = [Environment]::GetFolderPath('UserProfile')
$skillsRoot = Join-Path $userProfileRoot '.agents\skills'
$destination = Join-Path $skillsRoot 'ai-dg-estimator'

if (-not (Test-Path $source)) {
    throw "Skill source not found: $source"
}

New-Item -ItemType Directory -Force -Path $skillsRoot | Out-Null

if ((Test-Path $destination) -and (-not $Force)) {
    Write-Host "Skill exists; merging AI-DG-owned files into: $destination"
}

New-Item -ItemType Directory -Force -Path $destination | Out-Null
Copy-Item -Recurse -Force (Join-Path $source '*') $destination

Write-Host "Installed AI-dg skill to: $destination"
Write-Host "Codex and OpenCode can both discover ~/.agents/skills/ai-dg-estimator."
Write-Host "Restart the agent app/CLI if the skill does not appear immediately."
