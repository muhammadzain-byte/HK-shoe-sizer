param()

$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RuntimePath = Join-Path $ProjectRoot "runtime\local-stack.json"
$PublicRuntimePath = Join-Path $ProjectRoot "frontend\public\local-stack.json"

function Read-JsonFile {
  param([string]$Path)
  if (-not (Test-Path $Path)) {
    return $null
  }
  try {
    return Get-Content $Path -Raw | ConvertFrom-Json
  } catch {
    Write-Host "Could not parse $Path`: $($_.Exception.Message)"
    return $null
  }
}

function Get-LanIPv4Addresses {
  try {
    return @(Get-NetIPConfiguration -ErrorAction SilentlyContinue |
      Where-Object { $_.IPv4Address -and $_.NetAdapter.Status -eq "Up" } |
      ForEach-Object {
        foreach ($address in $_.IPv4Address) {
          if (
            $address.IPAddress -and
            $address.IPAddress -notmatch "^127\." -and
            $address.IPAddress -notmatch "^169\.254\." -and
            $address.IPAddress -notmatch "^0\."
          ) {
            [pscustomobject]@{
              interface = $_.InterfaceAlias
              ipv4 = $address.IPAddress
            }
          }
        }
      })
  } catch {
    Write-Host "Could not list LAN IPv4 addresses: $($_.Exception.Message)"
    return @()
  }
}

function Test-ListeningOnAny {
  param([int]$Port)
  try {
    $connections = @(Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
      Where-Object { $_.State.ToString() -eq "Listen" })
    return [pscustomobject]@{
      listening = ($connections.Count -gt 0)
      listening_on_0_0_0_0 = [bool]($connections | Where-Object { $_.LocalAddress -eq "0.0.0.0" })
      listeners = $connections | Select-Object LocalAddress, LocalPort, State, OwningProcess
    }
  } catch {
    return [pscustomobject]@{
      listening = $false
      listening_on_0_0_0_0 = $false
      listeners = @()
      error = $_.Exception.Message
    }
  }
}

function Get-FirewallRulesForPort {
  param([int]$Port)
  try {
    $filters = @(Get-NetFirewallPortFilter -ErrorAction SilentlyContinue |
      Where-Object { $_.Protocol -eq "TCP" -and $_.LocalPort -eq "$Port" })
    foreach ($filter in $filters) {
      $rule = Get-NetFirewallRule -AssociatedNetFirewallPortFilter $filter -ErrorAction SilentlyContinue
      foreach ($item in $rule) {
        [pscustomobject]@{
          display_name = $item.DisplayName
          enabled = $item.Enabled
          action = $item.Action
          direction = $item.Direction
          profile = $item.Profile
          port = $Port
        }
      }
    }
  } catch {
    Write-Host "Could not inspect firewall rules for port $Port`: $($_.Exception.Message)"
    return @()
  }
}

function Get-NetworkProfilesSafe {
  try {
    return @(Get-NetConnectionProfile -ErrorAction SilentlyContinue |
      ForEach-Object {
        [pscustomobject]@{
          Name = $_.Name
          InterfaceAlias = $_.InterfaceAlias
          NetworkCategory = $_.NetworkCategory.ToString()
          IPv4Connectivity = $_.IPv4Connectivity.ToString()
        }
      })
  } catch {
    Write-Host "Could not inspect Windows network profile: $($_.Exception.Message)"
    return @()
  }
}

function Get-VpnLikeAdapters {
  try {
    return @(Get-NetAdapter -ErrorAction SilentlyContinue |
      Where-Object {
        $_.Status -eq "Up" -and
        ($_.InterfaceDescription -match "VPN|TAP|TUN|WireGuard|OpenVPN|AnyConnect|ZeroTier|Tailscale|Hamachi" -or
          $_.Name -match "VPN|TAP|TUN|WireGuard|OpenVPN|AnyConnect|ZeroTier|Tailscale|Hamachi")
      } |
      Select-Object Name, InterfaceDescription, Status)
  } catch {
    Write-Host "Could not inspect VPN-like adapters: $($_.Exception.Message)"
    return @()
  }
}

$runtime = Read-JsonFile -Path $RuntimePath
$publicRuntime = Read-JsonFile -Path $PublicRuntimePath
$backendPort = if ($runtime) { [int]$runtime.backend_port } else { 0 }
$frontendPort = if ($runtime) { [int]$runtime.frontend_port } else { 0 }
$lanIp = if ($runtime -and $runtime.lan_ip) { $runtime.lan_ip } else { "LAN_IP" }
$backendHealthUrl = if ($runtime -and $runtime.health_url) { $runtime.health_url } else { "http://$lanIp`:$backendPort/api/v1/health" }
$frontendPhoneUrl = if ($runtime -and $runtime.frontend_url) { $runtime.frontend_url } else { "http://$lanIp`:$frontendPort" }
$newScanUrl = if ($runtime -and $runtime.new_scan_url) { $runtime.new_scan_url } else { "$frontendPhoneUrl/scans/new" }
$validationUrl = if ($runtime -and $runtime.validation_url) { $runtime.validation_url } else { "$frontendPhoneUrl/validation" }
$phoneTestUrl = "$frontendPhoneUrl/phone-test"

$backendListen = if ($backendPort -gt 0) { Test-ListeningOnAny -Port $backendPort } else { $null }
$frontendListen = if ($frontendPort -gt 0) { Test-ListeningOnAny -Port $frontendPort } else { $null }
$networkProfiles = @(Get-NetworkProfilesSafe)
$firewallBackend = if ($backendPort -gt 0) { @(Get-FirewallRulesForPort -Port $backendPort) } else { @() }
$firewallFrontend = if ($frontendPort -gt 0) { @(Get-FirewallRulesForPort -Port $frontendPort) } else { @() }

Write-Host ""
Write-Host "PHONE ACCESS DIAGNOSTIC"
Write-Host "Project: $ProjectRoot"
Write-Host ""

Write-Host "Current LAN IPv4 addresses:"
$lanAddresses = @(Get-LanIPv4Addresses)
if ($lanAddresses.Count -eq 0 -and $runtime -and $runtime.lan_ip) {
  $lanAddresses = @([pscustomobject]@{
      interface = "runtime"
      ipv4 = $runtime.lan_ip
    })
}
if ($lanAddresses.Count -gt 0) {
  $lanAddresses | Format-Table -AutoSize | Out-Host
} else {
  Write-Host "No LAN IPv4 address was detected."
}

Write-Host ""
Write-Host "Active runtime file: $RuntimePath"
if ($runtime) { $runtime | ConvertTo-Json -Depth 6 | Out-Host } else { Write-Host "Missing or unreadable." }

Write-Host ""
Write-Host "Frontend public runtime file: $PublicRuntimePath"
if ($publicRuntime) { $publicRuntime | ConvertTo-Json -Depth 6 | Out-Host } else { Write-Host "Missing or unreadable." }

Write-Host ""
Write-Host "Backend port: $backendPort"
Write-Host "Frontend port: $frontendPort"
Write-Host "Backend health URL: $backendHealthUrl"
Write-Host "Frontend phone URL: $frontendPhoneUrl"
Write-Host "Backend listening on 0.0.0.0: $($backendListen.listening_on_0_0_0_0)"
Write-Host "Frontend listening on 0.0.0.0: $($frontendListen.listening_on_0_0_0_0)"

Write-Host ""
Write-Host "Windows Firewall rules for selected ports:"
if ($firewallFrontend.Count -gt 0) {
  $firewallFrontend | Format-Table -AutoSize | Out-Host
} else {
  Write-Host "No frontend firewall port rule found for TCP $frontendPort."
}
if ($firewallBackend.Count -gt 0) {
  $firewallBackend | Format-Table -AutoSize | Out-Host
} else {
  Write-Host "No backend firewall port rule found for TCP $backendPort."
}

Write-Host ""
Write-Host "Windows network profiles:"
if ($networkProfiles.Count -gt 0) {
  $networkProfiles | Format-Table -AutoSize | Out-Host
} else {
  Write-Host "No network profile information found."
}

Write-Host ""
Write-Host "VPN-like active adapters:"
$vpnAdapters = Get-VpnLikeAdapters
if ($vpnAdapters.Count -gt 0) {
  $vpnAdapters | Format-Table -AutoSize | Out-Host
} else {
  Write-Host "No obvious VPN-like active adapters detected."
}

Write-Host ""
Write-Host "OPEN THESE ON PHONE:"
Write-Host "Backend health: $backendHealthUrl"
Write-Host "Frontend:       $frontendPhoneUrl"
Write-Host "New Scan:       $newScanUrl"
Write-Host "Validation:     $validationUrl"
Write-Host "Phone Test:     $phoneTestUrl"

Write-Host ""
Write-Host "If phone cannot open backend health:"
Write-Host "- Confirm phone and laptop are on the same Wi-Fi."
Write-Host "- Disable VPN on laptop and phone."
Write-Host "- Set Windows network profile to Private."
Write-Host "- Run .\scripts\fix-phone-firewall.ps1 as Administrator."
Write-Host "- Check router AP/client isolation."

$summary = [ordered]@{
  lan_ip = $lanIp
  backend_port = $backendPort
  frontend_port = $frontendPort
  backend_health_url = $backendHealthUrl
  frontend_phone_url = $frontendPhoneUrl
  new_scan_url = $newScanUrl
  validation_url = $validationUrl
  phone_test_url = $phoneTestUrl
  backend_listening_on_0_0_0_0 = if ($backendListen) { $backendListen.listening_on_0_0_0_0 } else { $false }
  frontend_listening_on_0_0_0_0 = if ($frontendListen) { $frontendListen.listening_on_0_0_0_0 } else { $false }
  frontend_firewall_rule_count = $firewallFrontend.Count
  backend_firewall_rule_count = $firewallBackend.Count
  network_profiles = $networkProfiles
  vpn_like_adapters = $vpnAdapters
}

Write-Host ""
$summary | ConvertTo-Json -Depth 6
