$ErrorActionPreference = 'Stop'
$project = Split-Path $PSScriptRoot -Parent
$scene = Join-Path $env:LOCALAPPDATA 'DIEF JARVIS\versions\2.0.3\core\spatial'
$output = Join-Path $project 'validation'
Get-Acl -LiteralPath $scene | Format-List Owner,AccessToString | Out-File (Join-Path $output 'installed-scene-acl.log')
& (Join-Path $project '.test-venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'probe_spatial_startup.py') $scene $output 1> (Join-Path $output 'installed-scene-probe.log') 2> (Join-Path $output 'installed-scene-errors.log')
