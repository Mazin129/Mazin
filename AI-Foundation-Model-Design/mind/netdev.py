"""
netdev — live device interaction (roadmap T4).

Read-only SSH to real network equipment via netmiko. This is the biggest
"real world" step: Vio answers from the ACTUAL device, not a taught config.

Configuration (git-ignored JSON, path in VIO_DEVICES):
  [{"name": "HQ-FGT", "host": "10.0.0.1", "device_type": "fortinet",
    "username": "admin", "password": "…", "secret": "…"}]

Safety model:
  · READ-ONLY by contract: every command must match a per-vendor show/get
    allowlist; anything else is refused before it reaches the wire.
  · The tool holds the DEVICE permission — the Guardrail treats it as acting,
    gated like network access (advisory asks always; assisted needs the
    VIO_ALLOW_DEVICES opt-in; writes are not implemented here at all).
  · Every call is logged in the Task record (agent, command, duration).
"""
from __future__ import annotations

import json
import os
import re
import time

# read-only command shapes per vendor family (netmiko device_type prefix)
_SHOW_ALLOW = {
    "fortinet": (r"^get\s+(system\s+status|system\s+performance|router|"
                 r"firewall|system\s+interface)\b", r"^show\b", r"^diagnose\s+sys\b"),
    "cisco":    (r"^show\b",),
    "arista":   (r"^show\b",),
    "cisco_xe": (r"^show\b",),
}


def devices():
    """Configured devices from VIO_DEVICES (JSON list). Never raises."""
    path = os.environ.get("VIO_DEVICES", "")
    if not path or not os.path.exists(path):
        return []
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return []


def inventory_summary():
    """Names + hosts Vio knows about (for the coordinator's brief)."""
    return [{"name": d.get("name"), "host": d.get("host"),
             "type": d.get("device_type")} for d in devices()]


def _allowed(dev_type, command):
    fam = (dev_type or "").split("_")[0]
    pats = _SHOW_ALLOW.get(fam) or _SHOW_ALLOW.get(dev_type) or (r"^show\b", r"^get\b")
    return any(re.match(p, command.strip(), re.I) for p in pats)


def run(name, command, timeout=30):
    """Run ONE read-only command on a configured device. Returns a result dict."""
    try:
        from netmiko import ConnectHandler
    except Exception:
        return {"ok": False, "error": "netmiko is not installed (pip install netmiko)"}
    dev = next((d for d in devices() if (d.get("name") or "").lower() == (name or "").lower()),
               None)
    if not dev:
        known = ", ".join(d.get("name", "?") for d in devices()) or "none configured"
        return {"ok": False, "error": f"no device named '{name}' (configured: {known})"}
    cmd = (command or "").strip()
    if not _allowed(dev.get("device_type"), cmd):
        return {"ok": False,
                "error": f"refused: '{cmd}' is not on the read-only allowlist for "
                         f"{dev.get('device_type')} — only show/get/diagnose commands run"}
    t0 = time.time()
    try:
        with ConnectHandler(host=dev["host"], device_type=dev["device_type"],
                            username=dev.get("username", ""), password=dev.get("password", ""),
                            secret=dev.get("secret", ""), timeout=timeout) as conn:
            out = conn.send_command(cmd, read_timeout=timeout)
        return {"ok": True, "device": dev.get("name"), "command": cmd,
                "output": (out or "")[:20_000],
                "ms": round((time.time() - t0) * 1000)}
    except Exception as e:
        return {"ok": False, "device": dev.get("name"), "command": cmd,
                "error": f"{type(e).__name__}: {e}"[:200]}
