param()

$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RuntimePath = Join-Path $ProjectRoot "runtime\local-stack.json"

if (-not (Test-Path $RuntimePath)) {
  Write-Host "Runtime file not found: $RuntimePath"
  Write-Host "Run .\scripts\run-app-now.ps1 -Force -Lan -PhoneAccess first."
  exit 1
}

$runtime = Get-Content $RuntimePath -Raw | ConvertFrom-Json
$frontendPort = [int]$runtime.frontend_port
$frontendUrl = "http://localhost:$frontendPort"

Write-Host ""
Write-Host "PHONE HTTPS/TUNNEL FALLBACK"
Write-Host "Local frontend: $frontendUrl"
Write-Host ""

$cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
$ngrok = Get-Command ngrok -ErrorAction SilentlyContinue

if ($cloudflared) {
  Write-Host "cloudflared detected."
  Write-Host "Run:"
  Write-Host "cloudflared tunnel --url $frontendUrl"
  Write-Host ""
  Write-Host "Then open the generated HTTPS URL on your phone."
  exit 0
}

if ($ngrok) {
  Write-Host "ngrok detected."
  Write-Host "Run:"
  Write-Host "ngrok http $frontendPort"
  Write-Host ""
  Write-Host "Then open the generated HTTPS URL on your phone."
  exit 0
}

Write-Host "No tunnel tool was found."
Write-Host ""
Write-Host "Install one of these if LAN HTTP works but mobile camera needs HTTPS:"
Write-Host "- Cloudflare Tunnel: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
Write-Host "- ngrok: https://ngrok.com/download"
Write-Host "- Local HTTPS with mkcert: https://github.com/FiloSottile/mkcert"
Write-Host ""
Write-Host "Tunnel use is optional. LAN mode should still work for page/upload testing if firewall and Wi-Fi allow it."
