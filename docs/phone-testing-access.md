# Phone Testing Access

Phase 6I prepares MirrorStep for testing from a phone on the same Wi-Fi as the laptop.

## LAN Mode

Start the app for phone testing:

```powershell
.\scripts\run-app-now.ps1 -Force -Lan -PhoneAccess
```

The launcher detects the laptop LAN IPv4 address, starts the backend and frontend on `0.0.0.0`, writes
`runtime\local-stack.json`, and writes `frontend\public\local-stack.json` with LAN backend URLs.

The final output prints:

- Backend health URL
- Frontend URL
- New Scan URL
- Validation URL
- Phone Test URL

It also saves the same URLs to:

```text
artifacts\phone-access\phone-url.txt
```

## Firewall Setup

If the phone cannot open the backend health URL, Windows Firewall is the first thing to check.

Run PowerShell as Administrator:

```powershell
.\scripts\fix-phone-firewall.ps1
```

The script creates only exact inbound TCP port rules for the current runtime frontend and backend ports.
It does not disable the firewall and does not open all ports.

If your active Windows network profile is Public, switch it to Private for local device testing. Public rules
are only created if you explicitly run:

```powershell
.\scripts\fix-phone-firewall.ps1 -AllowPublic
```

## Diagnostic Command

Run:

```powershell
.\scripts\diagnose-phone-access.ps1
```

It prints LAN IPs, runtime config, public runtime config, listener binding, firewall rules, network profile,
VPN-like adapters, and the exact phone URLs to open.

## Phone Test Page

Open this on the phone:

```text
http://LAN_IP:FRONTEND_PORT/phone-test
```

The page shows the runtime API base and backend health URL seen by the phone browser. It can test backend
health, `auth/me` when logged in, and a tiny local image upload when a token exists.

If the page loads but backend health fails, the likely causes are Windows Firewall, Wi-Fi client isolation,
VPN, or a wrong LAN IP.

## HTTPS And Tunnel Fallback

LAN HTTP should work for page and upload testing when firewall and Wi-Fi allow it. Mobile camera access may
require HTTPS depending on the browser and device.

Optional HTTPS paths:

1. Cloudflare Tunnel
2. ngrok
3. local HTTPS with mkcert

The helper script only prints available options:

```powershell
.\scripts\start-phone-tunnel.ps1
```

It does not install tunnel software automatically and does not force tunnel usage.

## Safety Notes

- Phone access does not prove measurement accuracy.
- Real accuracy still requires the validation dataset with real phone images and manual millimeter ground truth.
- Do not expose these local URLs on untrusted networks.
- Keep research models disabled unless explicitly debugging.
