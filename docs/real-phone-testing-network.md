# Real Phone Testing Network

Desktop validation cockpit:

```text
http://localhost:3000/validation
```

Phone on the same Wi-Fi:

```text
http://YOUR_PC_LAN_IP:3000/validation
```

Backend on the same Wi-Fi:

```text
http://YOUR_PC_LAN_IP:8000
```

Run:

```powershell
python backend\scripts\print_testing_urls.py
```

Mobile browsers often require HTTPS for camera access. Safe options:

- Use desktop upload first.
- Use a secure tunnel such as Cloudflare Tunnel or ngrok.
- Use local HTTPS certificates with mkcert if you are comfortable managing local certificates.

Do not force these tools automatically. Keep Android/iPhone on the same Wi-Fi as the PC when using LAN URLs.
