param(
  [switch]$Force
)

$ProjectRoot = Split-Path -Parent $PSScriptRoot
& "$ProjectRoot\scripts\run-app-now.ps1" -Force:$Force
