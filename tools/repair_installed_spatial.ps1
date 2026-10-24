$ErrorActionPreference = 'Stop'
$project = Split-Path $PSScriptRoot -Parent
$scene = Join-Path $env:LOCALAPPDATA 'DIEF JARVIS\versions\2.0.3\core\spatial'
$output = Join-Path $project 'validation'
$sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$vendor = Join-Path $scene 'vendor\package\build'
New-Item -ItemType Directory -Path $vendor -Force | Out-Null
foreach ($name in @('three.module.js','three.core.js')) {
    Copy-Item -LiteralPath (Join-Path $project ('core\spatial\vendor\package\build\' + $name)) -Destination (Join-Path $vendor $name) -Force
}
& icacls.exe $scene /grant ('*' + $sid + ':(OI)(CI)(RX)') /T /Q | Out-File (Join-Path $output 'scene-access-repair.log')
if ($LASTEXITCODE -ne 0) { throw 'Falha ao preparar leitura dos recursos visuais.' }
& (Join-Path $project '.test-venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'probe_spatial_startup.py') $scene $output 1> (Join-Path $output 'repaired-scene-probe.log') 2> (Join-Path $output 'repaired-scene-errors.log')
