param(
  [switch]$Force
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if ($Force) {
  & "$ProjectRoot\scripts\restart-local-testing-stack.ps1" -Force
} else {
  & "$ProjectRoot\scripts\restart-local-testing-stack.ps1"
}
