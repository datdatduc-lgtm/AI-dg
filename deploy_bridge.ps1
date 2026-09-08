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
    @{ Source = Join-Path $source 'ai_dg_bridge\geometry_builder.rb'; Destination = Join-Path $destination 'geometry_builder.rb' },
    @{ Source = Join-Path $source 'ai_dg_bridge\toolbar.rb'; Destination = Join-Path $destination 'toolbar.rb' },
    @{ Source = Join-Path $source 'ai_dg_bridge\control_center.rb'; Destination = Join-Path $destination 'control_center.rb' },
    @{ Source = Join-Path $source 'ai_dg_bridge\helper_process.rb'; Destination = Join-Path $destination 'helper_process.rb' },
    @{ Source = Join-Path $source 'ai_dg_bridge\icons\ai_dg_mcp.svg'; Destination = Join-Path $destination 'icons\ai_dg_mcp.svg' }
)

New-Item -ItemType Directory -Path $destination -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $destination 'icons') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $destination 'ui') -Force | Out-Null
$uiFiles = @('control_center.html', 'control_center.css', 'control_center.js')
foreach ($uiFile in $uiFiles) {
    $uiSource = Join-Path $source ("ai_dg_bridge\ui\" + $uiFile)
    $uiDestination = Join-Path $destination ("ui\" + $uiFile)
    if (-not (Test-Path -LiteralPath $uiSource -PathType Leaf)) {
        throw "Missing Control Center UI source: $uiSource"
    }
    Copy-Item -LiteralPath $uiSource -Destination $uiDestination -Force
}
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

foreach ($uiFile in $uiFiles) {
    $uiSource = Join-Path $source ("ai_dg_bridge\ui\" + $uiFile)
    $uiDestination = Join-Path $destination ("ui\" + $uiFile)
    $sourceHash = (Get-FileHash -LiteralPath $uiSource -Algorithm SHA256).Hash
    $deployedHash = (Get-FileHash -LiteralPath $uiDestination -Algorithm SHA256).Hash
    if ($sourceHash -ne $deployedHash) {
        throw "Hash mismatch after deploy: $uiDestination"
    }
    [pscustomobject]@{ File = $uiDestination; SHA256 = $deployedHash }
}

Write-Host 'Bridge deployed. No SketchUp process was stopped or restarted.'
Write-Host 'If SketchUp is already running, reload the extension manually or restart gracefully after saving.'
