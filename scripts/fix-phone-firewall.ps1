param(
  [switch]$AllowPublic
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RuntimePath = Join-Path $ProjectRoot "runtime\local-stack.json"

function Test-IsAdmin {
  $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = [Security.Principal.WindowsPrincipal]::new($identity)
  return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-CurrentProfiles {
  try {
    return @(Get-NetConnectionProfile -ErrorAction SilentlyContinue)
  } catch {
    return @()
  }
}

function Ensure-PortRule {
  param(
    [string]$DisplayName,
    [int]$Port,
    [string]$Profile
  )

  $existing = @(Get-NetFirewallRule -DisplayName $DisplayName -ErrorAction SilentlyContinue)
  if ($existing.Count -gt 0) {
    Write-Host "Firewall rule already exists: $DisplayName"
    return
  }

  New-NetFirewallRule `
    -DisplayName $DisplayName `
    -Direction Inbound `
    -Action Allow `
    -Protocol TCP `
    -LocalPort $Port `
    -Profile $Profile | Out-Null
  Write-Host "Created firewall rule: $DisplayName ($Profile, TCP $Port)"
}

if (-not (Test-Path $RuntimePath)) {
  Write-Host "Runtime file not found: $RuntimePath"
  Write-Host "Run .\scripts\run-app-now.ps1 -Force -Lan -PhoneAccess first."
  exit 1
}

$runtime = Get-Content $RuntimePath -Raw | ConvertFrom-Json
$frontendPort = [int]$runtime.frontend_port
$backendPort = [int]$runtime.backend_port

if (-not (Test-IsAdmin)) {
  Write-Host "Run PowerShell as Administrator and rerun this script."
  Write-Host "Command:"
  Write-Host ".\scripts\fix-phone-firewall.ps1"
  exit 1
}

$profiles = Get-CurrentProfiles
$publicProfiles = @($profiles | Where-Object { $_.NetworkCategory -eq "Public" })
if ($publicProfiles.Count -gt 0 -and -not $AllowPublic) {
  Write-Host "Your active Windows network profile is Public."
  Write-Host "For phone testing, set the Wi-Fi network profile to Private, then rerun this script."
  Write-Host "If you intentionally want to allow Public profile rules, rerun:"
  Write-Host ".\scripts\fix-phone-firewall.ps1 -AllowPublic"
}

$profile = if ($AllowPublic) { "Private,Public" } else { "Private" }

Ensure-PortRule -DisplayName "MirrorStep Frontend $frontendPort" -Port $frontendPort -Profile $profile
Ensure-PortRule -DisplayName "MirrorStep Backend $backendPort" -Port $backendPort -Profile $profile

Write-Host ""
Write-Host "Firewall setup complete."
Write-Host "Frontend: http://$($runtime.lan_ip):$frontendPort"
Write-Host "Backend health: http://$($runtime.lan_ip):$backendPort/api/v1/health"
