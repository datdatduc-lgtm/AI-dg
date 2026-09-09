[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'bridge_sketchup'
$plugins = Join-Path $env:APPDATA 'SketchUp\SketchUp 2023\SketchUp\Plugins'
$destination = Join-Path $plugins 'ai_dg_bridge'

$files = @(
    @{ Source = Join-Path $source 'ai_dg_bridge.rb'; Destination = Join-Path $plugins 'ai_dg_bridge.rb' },
    # Deploy the staged runtime under the extension's expected main.rb path.
    @{ Source = Join-Path $source 'ai_dg_bridge\main_safe.rb'; Destination = Join-Path $destination 'main.rb' },
    @{ Source = Join-Path $source 'ai_dg_bridge\geometry_builder.rb'; Destination = Join-Path $destination 'geometry_builder.rb' }
)

New-Item -ItemType Directory -Path $destination -Force | Out-Null
foreach ($file in $files) {
    if (-not (Test-Path -LiteralPath $file.Source -PathType Leaf)) {
        throw "Missing bridge source: $($file.Source)"
    }
    Copy-Item -LiteralPath $file.Source -Destination $file.Destination -Force
}

foreach ($file in $files) {
    $sourceHash = (Get-FileHash -LiteralPath $file.Source -Algorithm SHA256).Hash
    $deployedHash = (Get-FileHash -LiteralPath $file.Destination -Algorithm SHA256).Hash
    if ($sourceHash -ne $deployedHash) {
        throw "Hash mismatch after deploy: $($file.Destination)"
    }
    [pscustomobject]@{ File = $file.Destination; SHA256 = $deployedHash }
}

# Remove files from older UI/embedded-agent deployments by exact path. The
# remaining installed extension contains only main.rb and geometry_builder.rb.
$retiredFiles = @(
    'helper_process.rb',
    'toolbar.rb',
    'control_center.rb',
    'agent_host_client.rb',
    'icons\ai_dg_mcp.svg',
    'agent_host\host.py',
    'ui\control_center.html',
    'ui\control_center.css',
    'ui\control_center.js'
)
foreach ($relativePath in $retiredFiles) {
    $retiredPath = Join-Path $destination $relativePath
    if (Test-Path -LiteralPath $retiredPath -PathType Leaf) {
        Remove-Item -LiteralPath $retiredPath -Force
    }
}
foreach ($relativeDirectory in @('icons', 'agent_host', 'ui')) {
    $retiredDirectory = Join-Path $destination $relativeDirectory
    if ((Test-Path -LiteralPath $retiredDirectory -PathType Container) -and -not (Get-ChildItem -LiteralPath $retiredDirectory -Force)) {
        Remove-Item -LiteralPath $retiredDirectory -Force
    }
}

Write-Host 'Bridge deployed. No SketchUp process was stopped or restarted.'
Write-Host 'If SketchUp is already running, reload the extension manually or restart gracefully after saving.'
