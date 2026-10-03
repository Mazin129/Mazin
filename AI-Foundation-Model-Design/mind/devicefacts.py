"""
devicefacts — "what is the serial number / model / firmware / hostname of the HQ
FortiGate?" answered EXACTLY, never by a model's guess.

Facts come from everything the user gave Vio about their devices:
  • a configuration backup  — `#config-version=FG100F-7.2.5-FW-build1517-…` header,
    `set hostname`, `set alias` (FortiGate); `hostname`, `ASA Version` (Cisco);
    `<hostname>` (Palo Alto);
  • pasted/uploaded command output — `get system status` (FortiGate), `show version`
    (Cisco), `show system info` (Palo Alto): Serial-Number, Version, Hostname, uptime;
  • tables (an inventory spreadsheet with a serial column) and remembered facts.

A FortiOS config backup does NOT contain the device serial number; when it is not in
anything the user gave, the answer says so and says exactly how to provide it.
"""
from __future__ import annotations

import re

ATTRS = {
    "serial": r"serial(?:\s*(?:number|no\.?|#))?|\bs/?n\b",
    "model": r"\bmodel\b|\bhardware\b|\bplatform\b",
    "firmware": r"firmware|fortios|\bos\s+version\b|\bsoftware\s+version\b|\bversion\b|"
                r"\bbuild\b",
    "hostname": r"host\s*name|device\s+name",
    "uptime": r"\buptime\b|\bup\s*time\b",
}
_LABEL = {"serial": "serial number", "model": "model", "firmware": "firmware",
          "hostname": "hostname", "uptime": "uptime"}
_DEVICE_WORDS = r"fortigate|fortinet|firewall|fgt|\bfw\b|palo\s*alto|\bpan\b|asa|router|" \
                r"switch|device|appliance|box|unit"


def attribute_asked(q):
    """The device attribute a question asks for, or None. It must be about a device —
    'what is the version of TLS' is not."""
    low = (q or "").lower()
    if not re.search(r"\b(what|which|show|give|tell|get|find|list)\b|\?$|\bof\b|\bfrom\b",
                     low):
        return None
    for attr, pat in ATTRS.items():
        if re.search(pat, low):
            if attr in ("firmware", "model", "uptime") and not re.search(_DEVICE_WORDS, low):
                return None
            return attr
    return None


# --------------------------------------------------------------------------- #
# extraction
# --------------------------------------------------------------------------- #
def from_text(text):
    """All device facts found in one text (config backup or command output)."""
    f = {}
    t = text or ""
    m = re.search(r"#config-version=([A-Z0-9]+)-(\d+\.\d+\.\d+)-FW-build(\d+)", t)
    if m:
        f["model"] = _forti_model(m.group(1))
        f["firmware"] = f"FortiOS {m.group(2)} build {m.group(3)}"
    for pat, key in (
            (r"(?im)^\s*Serial[- ]Number\s*[:=]\s*(\S+)", "serial"),
            (r"(?im)^\s*serial\s*[:=]\s*([A-Z0-9]{8,})", "serial"),
            (r"(?im)Serial Number\s*[:]\s*([A-Z0-9]{6,})", "serial"),
            (r"(?im)^\s*Hostname\s*[:]\s*(\S+)", "hostname"),
            (r"(?im)^\s*Version\s*:\s*(Forti\w+[^\n]*)", "firmware"),
            (r"(?im)^\s*System time\s*:\s*([^\n]+)", "time"),
            (r"(?im)^\s*Uptime\s*[:]\s*([^\n]+)", "uptime"),
            (r"(?im)^\s*sw-version\s*:\s*(\S+)", "firmware"),
            (r"(?im)^\s*model\s*:\s*(\S+)", "model"),
            (r"(?im)^\s*Hardware\s*:\s*([^,\n]+)", "model"),
            (r"(?im)Cisco Adaptive Security Appliance Software Version\s+(\S+)", "firmware"),
            (r"(?im)^\s*ASA Version\s+(\S+)", "firmware"),
            (r"(?im)^\s*set hostname\s+\"?([^\"\n]+)\"?", "hostname"),
            (r"(?im)^\s*set alias\s+\"?([^\"\n]+)\"?", "alias"),
            (r"(?im)^\s*hostname\s+(\S+)\s*$", "hostname"),
            (r"(?im)<hostname>([^<]+)</hostname>", "hostname"),
            (r"(?im)\bup\s+(\d+\s+(?:days?|hours?|mins?)[^\n]*)", "uptime")):
        mm = re.search(pat, t)
        if mm and key not in f:
            f[key] = mm.group(1).strip().strip('"')
    # FortiGate serials start with the model prefix (FG100F…, FGT60F…, FGVM…)
    if "serial" not in f:
        mm = re.search(r"\b(F[GW][A-Z0-9]{3,6}[A-Z]{2}\d{8})\b", t)
        if mm and not re.search(r"(?i)(analyzer|manager|fortianalyzer|fortimanager)"
                                r"[^\n]{0,60}" + re.escape(mm.group(1)), t):
            f["serial"] = mm.group(1)
    return f


def _forti_model(code):
    m = re.match(r"(?:FGT|FG|FWF)(\w+)", code)
    return f"FortiGate-{m.group(1)}" if m and not code.startswith("FWF") else code


# --------------------------------------------------------------------------- #
# inventory
# --------------------------------------------------------------------------- #
def inventory(mind):
    """{device name: {attr: (value, source)}} from configs, command output, tables
    and memory. Cached until any of those change — it runs on every question."""
    try:
        key = (getattr(mind.lib, "version", 0), len(mind.config_snapshots()),
               len(getattr(mind, "tables", []) or []),
               len((getattr(mind, "mem", {}) or {}).get("facts", [])))
    except Exception:
        key = None
    cached = getattr(mind, "_inventory_cache", None)
    if key is not None and cached and cached[0] == key:
        return cached[1]
    inv = _inventory(mind)
    mind._inventory_cache = (key, inv)
    return inv


def _inventory(mind):
    inv = {}

    def put(dev, facts, source):
        d = inv.setdefault(dev, {})
        for k, v in facts.items():
            d.setdefault(k, (v, source))

    # 1. configuration snapshots (latest per device)
    try:
        latest = {}
        for name, stamp, path in mind.config_snapshots():
            latest[name] = path
        for name, path in latest.items():
            with open(path, encoding="utf-8", errors="ignore") as fh:
                facts = from_text(fh.read())
            put(facts.get("hostname") or name, facts, f"the configuration {name}")
            if facts.get("hostname") and facts["hostname"] != name:
                inv[facts["hostname"]].setdefault("file", (name, ""))
    except Exception:
        pass
    # 2. command output and documents in the library (get system status, show version)
    for d in getattr(mind.lib, "docs", []) or []:
        if re.search(r"(?i)serial[- ]number\s*[:=]|ASA Version|sw-version|#config-version", d):
            facts = from_text(d)
            host = facts.get("hostname")
            if host and len(facts) > 1:
                put(host, facts, "command output you gave me")
    # 3. tables: an inventory sheet with a serial / model / version column
    for tbl in getattr(mind, "tables", []) or []:
        heads = {h.lower(): h for h in tbl.headers}
        # the column that NAMES the device: hostname/device first, a site only last
        namecol = None
        for pat in (r"host\s*name|hostname", r"device|firewall|appliance", r"\bname\b",
                    r"site|location|branch"):
            namecol = next((heads[h] for h in heads if re.search(pat, h)), None)
            if namecol:
                break
        namecol = namecol or tbl.headers[0]
        for attr, pat in ATTRS.items():
            col = next((heads[h] for h in heads if re.search(pat, h)), None)
            if not col:
                continue
            for r in tbl.rows:
                if r.get(namecol) and r.get(col):
                    put(r[namecol].strip(), {attr: r[col].strip()}, f"the table “{tbl.name}”")
    # 4. remembered facts: "the HQ fortigate serial is FG100F…"
    for fact in (getattr(mind, "mem", {}) or {}).get("facts", []):
        for attr, pat in ATTRS.items():
            if re.search(pat, fact.lower()):
                mm = re.search(r"\b(?:is|=|:)\s*([A-Za-z0-9._/-]{4,})\s*$", fact.strip(". "))
                host = re.search(r"\b([A-Z][A-Za-z0-9_-]*[A-Z0-9][A-Za-z0-9_-]*)\b", fact)
                if mm and host:
                    put(host.group(1), {attr: mm.group(1)}, "what you told me")
    return inv


def _pieces(name):
    return {p for p in re.split(r"[^a-z0-9]+", (name or "").lower()) if p}


def match_devices(q, inv):
    """Devices the question names. 'HQ' matches 'HQ-FGT-01'; nothing named and one
    device known → that device."""
    words = set(re.findall(r"[a-z0-9][a-z0-9_-]*", (q or "").lower()))
    hits = []
    for dev in inv:
        p = _pieces(dev) | _pieces(inv[dev].get("file", ("", ""))[0])
        full = dev.lower()
        if full in words or (p & {w for w in words if len(w) >= 2 and w not in (
                "fortigate", "firewall", "fgt", "fw", "the", "of", "from", "what", "is",
                "serial", "number", "model", "version", "device", "my", "our")}):
            hits.append(dev)
    return hits


def answer(mind, q):
    """An exact answer dict for a device-attribute question, or None if it isn't one."""
    attr = attribute_asked(q)
    if not attr:
        return None
    inv = inventory(mind)
    devs = match_devices(q, inv)
    named = re.findall(r"\b([A-Z][A-Z0-9_-]{1,})\b", q or "")
    named = [n for n in named if n.lower() not in ("FGT", "FW", "SN", "OS", "HA")]
    if not devs and len(inv) == 1 and not named:
        devs = list(inv)
    label = _LABEL[attr]
    if not devs:
        known = ", ".join(sorted(inv)) or "none yet"
        who = " ".join(named) or "that device"
        return _r(f"I don't have any device called {who}. Devices I know: {known}.\n\n"
                  + _how_to(attr, who), False)
    lines, missing = [], []
    for dev in devs:
        val = inv[dev].get(attr)
        if val:
            lines.append(f"**{dev}** — {label}: `{val[0]}`  (from {val[1]})")
        else:
            missing.append(dev)
    for dev in missing:
        have = ", ".join(f"{_LABEL.get(k, k)} {v[0]}" for k, v in inv[dev].items()
                         if k in _LABEL and k != attr)
        why = (" A FortiOS configuration backup does not contain the serial number."
               if attr == "serial" else "")
        lines.append(f"**{dev}** — I don't have its {label}." + why
                     + (f" What I do have: {have}." if have else ""))
    body = "\n".join(lines)
    if missing:
        body += "\n\n" + _how_to(attr, missing[0])
    return _r(body, not missing)


def _how_to(attr, dev):
    cmd = {"serial": "get system status", "firmware": "get system status",
           "model": "get system status", "uptime": "get system performance status",
           "hostname": "get system status"}[attr]
    return (f"To give it to me: on {dev} run  `{cmd}`  (FortiGate; `show version` on Cisco, "
            f"`show system info` on Palo Alto) and paste the output here or upload it as a "
            f".txt — I'll read the {_LABEL[attr]} from it and keep it. Or tell me directly: "
            f"“remember: {dev} serial number is …”.")


def _r(text, ok):
    return {"answer": text, "how": "device facts (exact)" if ok else "device facts",
            "verified": ok, "confidence": 0.95 if ok else 0.4, "cortex": "skipped",
            "trace": ["answered from the device inventory — no model used"]}
