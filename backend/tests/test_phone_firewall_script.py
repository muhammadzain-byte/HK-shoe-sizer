from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_firewall_script_creates_exact_private_port_rules() -> None:
    source = (PROJECT_ROOT / "scripts" / "fix-phone-firewall.ps1").read_text(encoding="utf-8")

    assert "runtime\\local-stack.json" in source
    assert "MirrorStep Frontend $frontendPort" in source
    assert "MirrorStep Backend $backendPort" in source
    assert "New-NetFirewallRule" in source
    assert "-Direction Inbound" in source
    assert "-Action Allow" in source
    assert "-Protocol TCP" in source
    assert "-LocalPort $Port" in source
    assert "Private,Public" in source
    assert "Run PowerShell as Administrator and rerun this script." in source


def test_firewall_script_does_not_disable_firewall_or_open_all_ports() -> None:
    source = (PROJECT_ROOT / "scripts" / "fix-phone-firewall.ps1").read_text(encoding="utf-8")

    assert "Set-NetFirewallProfile" not in source
    assert "Disable-NetFirewallRule" not in source
    assert "-LocalPort Any" not in source
