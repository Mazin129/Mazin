"""
vendorparse — Palo Alto (PAN-OS) and Cisco ASA configurations, translated into the
same objects Vio uses for FortiGate.

Vio's analysis is written once, against FortiGate-shaped objects: kind "firewall
policy" with srcintf / dstintf / srcaddr / dstaddr / service / action, "firewall
address", "router static", "system interface", and so on. Translating other vendors
into that shape means every existing capability — listing, counting, the review,
hardening, exposure, cleanup, what-if, diff, compliance — works on them unchanged,
instead of growing a second copy of each.

Translation is conservative: a field the source config doesn't state is left absent,
never guessed, so the checks (which never treat absent as unsafe unless the vendor's
own default is unsafe) stay free of false positives.

  PAN-OS     `set` format (show with `set cli config-output-format set`).
             vsys / device-group / shared prefixes and pre/post rulebases handled.
  Cisco ASA  running-config: interfaces, objects, object-groups, extended ACLs bound
             with access-group, static routes, management access, SNMP, IKE/IPsec.
"""
from __future__ import annotations

import re
import shlex

from configparse import ConfigObject

PANOS, ASA = "panos", "asa"

_PAN_LINE = re.compile(
    r"^\s*set\s+(?:(?:vsys|device-group|template)\s+\S+\s+|shared\s+)?"
    r"(?:(?:pre-|post-)?rulebase|address|address-group|service|service-group|zone|"
    r"network|deviceconfig|mgt-config|application-group|profiles|profile-group)\b")
_ASA_LINE = re.compile(
    r"^(?:access-list\s+\S+\s+(?:extended|standard|remark)|access-group\s+\S+|"
    r"object(?:-group)?\s+(?:network|service)\s+\S+|interface\s+\S+|\s+nameif\s+\S+|"
    r"route\s+\S+\s+\d|(?:http|ssh|telnet)\s+\d+\.\d+\.\d+\.\d+\s+\d|"
    r"snmp-server\s+|crypto\s+(?:ikev[12]|ipsec)\s+|ASA Version|: Saved)", re.M)


def detect(text):
    """'panos', 'asa', or None. Needs several matching lines, so a sentence that merely
    mentions 'access-list' is never mistaken for a configuration."""
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return None
    pan = sum(1 for ln in lines if _PAN_LINE.match(ln))
    if pan >= 2 and pan >= len(lines) * 0.5:
        return PANOS
    asa = len(_ASA_LINE.findall(text))
    if asa >= 2 and not re.search(r"(?m)^\s*config\s+\S+", text):
        return ASA
    return None


# The exact SHAPE of each top-level ASA command, not just its first word: prose like
# "interface naming follows the slot number" must never pass for configuration.
_ASA_TOP = re.compile("|".join([
    r"^object(?:-group)?\s+(?:network|service|protocol|icmp-type|user|security)\s+\S+(?:\s+\S+)?$",
    r"^interface\s+\S*\d\S*$",
    r"^access-list\s+\S+\s+(?:extended|standard|remark|webtype|ethertype)\s",
    r"^access-group\s+\S+\s+(?:in|out|global)\b",
    r"^route\s+\S+\s+\d+\.\d+\.\d+\.\d+\s",
    r"^(?:http|ssh|telnet)\s+(?:\d+\.\d+\.\d+\.\d+\s|server\s|version\s|timeout\s|"
    r"key-exchange\s|cipher\s|scopy\s)",
    r"^snmp-server\s+(?:community|host|location|contact|enable|group|user)\b",
    r"^crypto\s+(?:ikev1|ikev2|ipsec|map|ca|key|dynamic-map)\b",
    r"^username\s+\S+\s+(?:password|nopassword|attributes)\b",
    r"^hostname\s+\S+$", r"^domain-name\s+\S+$", r"^nat\s+\(", r"^name\s+\d",
    r"^tunnel-group\s+\S+\s+(?:type|general-attributes|ipsec-attributes)\b",
    r"^group-policy\s+\S+\s+(?:internal|external|attributes)\b",
    r"^aaa\s+(?:authentication|authorization|accounting)\s",
    r"^logging\s+(?:enable|host|trap|buffered|timestamp)\b",
    r"^ntp\s+(?:server|authenticate|trusted-key)\b",
    r"^ASA Version\s", r"^same-security-traffic\s+permit\b",
    r"^icmp\s+(?:permit|deny|unreachable)\b", r"^timeout\s+\S+\s+\d",
    r"^threat-detection\s",
]))


def belongs_to(text, vendor):
    """Is this SMALL passage plausibly part of a config of `vendor` already present?

    A one-object ASA block ("object network X" + one indented line) has a single
    recognisable line, below what detect() needs to rule out prose. When the library
    already holds a clearly-detected config of that vendor, accept a passage whose
    EVERY line is shaped like that vendor's config — prose never is."""
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return False
    if vendor == ASA:
        tops = [ln for ln in lines if not ln.startswith((" ", "\t"))]
        return bool(tops) and all(_ASA_TOP.match(ln) for ln in tops)
    if vendor == PANOS:
        return all(_PAN_LINE.match(ln) for ln in lines)
    return False


def _q(values):
    """Values in FortiGate's quoted multi-value form, so shared helpers read them."""
    return " ".join(f'"{v}"' for v in values)


def _obj(store, order, kind, name):
    key = (kind, name)
    if key not in store:
        store[key] = ConfigObject(kind=kind, name=name, raw="")
        order.append(key)
    return store[key]


# =========================================================================== #
# PAN-OS
# =========================================================================== #
_WAN_ZONE = re.compile(r"untrust|outside|internet|external|wan|isp", re.I)
_PAN_DENY = {"deny", "drop", "reset-client", "reset-server", "reset-both"}


def _pan_tokens(line):
    try:
        t = shlex.split(line)
    except ValueError:
        t = line.split()
    t = [x for x in t if x not in ("[", "]")]
    if not t or t[0] != "set":
        return []
    t = t[1:]
    if t and t[0] in ("vsys", "device-group", "template"):
        t = t[2:]
    elif t and t[0] == "shared":
        t = t[1:]
    return t


def parse_panos(text):
    store, order = {}, []
    rule_app = {}
    zones, mgmt_profiles, iface_profile = {}, {}, {}
    permitted = []
    for line in (text or "").splitlines():
        t = _pan_tokens(line)
        if len(t) < 3:
            continue
        head = t[0]
        if head in ("rulebase", "pre-rulebase", "post-rulebase") and t[1] == "security" \
                and t[2] == "rules" and len(t) >= 6:
            name, field, vals = t[3], t[4], t[5:]
            o = _obj(store, order, "firewall policy", name)
            o.raw += line + "\n"
            if field == "from":
                o.fields["srcintf"] = _q(vals)
            elif field == "to":
                o.fields["dstintf"] = _q(vals)
            elif field == "source":
                o.fields["srcaddr"] = _q(vals)
            elif field == "destination":
                o.fields["dstaddr"] = _q(vals)
            elif field == "service":
                o.fields["service"] = _q(["ALL" if v == "any" else v for v in vals])
            elif field == "application":
                rule_app[name] = vals
            elif field == "action":
                o.fields["action"] = "deny" if vals[0] in _PAN_DENY else (
                    "accept" if vals[0] == "allow" else vals[0])
            elif field == "disabled":
                o.fields["status"] = "disable" if vals[0] == "yes" else "enable"
            elif field == "log-end":
                o.fields["logtraffic"] = "all" if vals[0] == "yes" else "disable"
            elif field == "profile-setting":
                o.fields["utm-status"] = "enable"
        elif head == "address" and len(t) >= 4:
            o = _obj(store, order, "firewall address", t[1])
            o.raw += line + "\n"
            kind, val = t[2], t[3]
            if kind == "ip-netmask":
                o.fields["subnet"] = val
            elif kind == "ip-range" and "-" in val:
                a, b = val.split("-", 1)
                o.fields.update({"type": "iprange", "start-ip": a, "end-ip": b})
            elif kind == "fqdn":
                o.fields.update({"type": "fqdn", "fqdn": f'"{val}"'})
        elif head == "address-group" and len(t) >= 4 and t[2] == "static":
            o = _obj(store, order, "firewall addrgrp", t[1])
            o.raw += line + "\n"
            o.fields["member"] = _q(t[3:])
        elif head == "service" and len(t) >= 6 and t[2] == "protocol":
            o = _obj(store, order, "firewall service custom", t[1])
            o.raw += line + "\n"
            if t[4] == "port":
                o.fields[f"{t[3]}-portrange"] = t[5]
        elif head == "zone" and len(t) >= 5 and t[2] == "network":
            zones.setdefault(t[1], []).extend(t[4:])
        elif head == "network":
            if t[1] == "interface-management-profile" and len(t) >= 5 and t[4] == "yes":
                mgmt_profiles.setdefault(t[2], set()).add(t[3])
            elif t[1] == "interface" and "interface-management-profile" in t:
                i = t.index("interface-management-profile")
                if i + 1 < len(t):
                    iface_profile[t[3] if t[2] == "ethernet" else t[2]] = t[i + 1]
            elif t[1] == "virtual-router" and "static-route" in t:
                i = t.index("static-route")
                if i + 2 < len(t):
                    rname, rest = t[i + 1], t[i + 2:]
                    o = _obj(store, order, "router static", rname)
                    o.raw += line + "\n"
                    if rest[0] == "destination" and len(rest) > 1:
                        o.fields["dst"] = rest[1]
                    elif rest[0] == "nexthop" and len(rest) > 2:
                        o.fields["gateway"] = rest[2]
                    elif rest[0] == "interface" and len(rest) > 1:
                        o.fields["device"] = f'"{rest[1]}"'
                    elif rest[0] == "admin-dist" and len(rest) > 1:
                        o.fields["distance"] = rest[1]
        elif head == "deviceconfig" and t[1] == "system" and len(t) >= 4:
            g = _obj(store, order, "system global", "")
            if t[2] == "hostname":
                g.fields["hostname"] = f'"{t[3]}"'
            elif t[2] == "permitted-ip":
                permitted.append(t[3])
        elif head == "mgt-config" and t[1] == "users" and len(t) >= 3:
            _obj(store, order, "system admin", t[2])

    # PAN: service application-default with application any = effectively any service
    for name, apps in rule_app.items():
        o = store.get(("firewall policy", name))
        if o and "any" in apps and o.fields.get("service", "") in ('"application-default"',):
            o.fields["service"] = '"ALL"'
    # interfaces: management services from their profile; WAN role from their zone
    for iface, prof in iface_profile.items():
        o = _obj(store, order, "system interface", iface)
        svc = sorted(s for s in mgmt_profiles.get(prof, ()) if s != "ping")
        if svc:
            o.fields["allowaccess"] = " ".join(svc)
    # zones: PAN policies name ZONES where FortiGate names interfaces, so each zone is
    # recorded as an object the interface checks recognise as a valid reference
    for zname, ifaces in zones.items():
        z = _obj(store, order, "system zone", zname)
        z.fields["interface"] = _q(ifaces)
        if _WAN_ZONE.search(zname):
            z.fields["role"] = "wan"
    for zname, ifaces in zones.items():
        if _WAN_ZONE.search(zname):
            for iface in ifaces:
                if ("system interface", iface) in store:
                    store[("system interface", iface)].fields["role"] = "wan"
    # admins: PAN's permitted-ip restricts management globally
    if permitted:
        for (kind, _n), o in store.items():
            if kind == "system admin":
                o.fields["trusthost1"] = permitted[0]
    return [store[k] for k in order]


# =========================================================================== #
# Cisco ASA
# =========================================================================== #
_IP = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")
_ASA_ENC = {"des": "des", "3des": "3des", "aes": "aes128", "aes-192": "aes192",
            "aes-256": "aes256", "aes-gcm": "aes128gcm", "aes-gcm-256": "aes256gcm"}
_ASA_HASH = {"md5": "md5", "sha": "sha1", "sha256": "sha256", "sha384": "sha384",
             "sha512": "sha512"}
_ESP = {"esp-des": "des", "esp-3des": "3des", "esp-aes": "aes128", "esp-aes-192": "aes192",
        "esp-aes-256": "aes256", "esp-md5-hmac": "md5", "esp-sha-hmac": "sha1",
        "esp-sha256-hmac": "sha256", "esp-sha384-hmac": "sha384",
        "esp-sha512-hmac": "sha512"}


def _asa_addr(tokens, i):
    """Consume one ACL address spec at tokens[i]; returns (name, next index)."""
    if i >= len(tokens):
        return None, i
    tok = tokens[i]
    if tok in ("any", "any4", "any6"):
        return "all", i + 1
    if tok in ("host", "object", "object-group", "interface") and i + 1 < len(tokens):
        return tokens[i + 1], i + 2
    if _IP.match(tok) and i + 1 < len(tokens) and _IP.match(tokens[i + 1]):
        return f"{tok} {tokens[i + 1]}", i + 2
    return tok, i + 1


def parse_asa(text):
    store, order = {}, []
    block, bobj = None, None
    acl_bind, acl_seq = {}, {}
    mgmt = []                                   # (proto, net, mask, ifname)
    for raw in (text or "").splitlines():
        if not raw.strip() or raw.strip().startswith(("!", ":")):
            block = None
            continue
        indented = raw.startswith((" ", "\t"))
        t = raw.split()
        if indented and block:
            kw = t[0]
            if block == "interface":
                if kw == "nameif" and len(t) > 1:
                    bobj.fields["nameif"] = t[1]
                elif kw == "security-level" and len(t) > 1:
                    bobj.fields["security-level"] = t[1]
                elif kw == "ip" and len(t) > 3 and t[1] == "address":
                    bobj.fields["ip"] = f"{t[2]} {t[3]}"
                elif kw == "shutdown":
                    bobj.fields["status"] = "down"
            elif block == "object network":
                if kw == "host" and len(t) > 1:
                    bobj.fields["subnet"] = f"{t[1]} 255.255.255.255"
                elif kw == "subnet" and len(t) > 2:
                    bobj.fields["subnet"] = f"{t[1]} {t[2]}"
                elif kw == "range" and len(t) > 2:
                    bobj.fields.update({"type": "iprange", "start-ip": t[1], "end-ip": t[2]})
                elif kw == "fqdn" and len(t) > 1:
                    bobj.fields.update({"type": "fqdn", "fqdn": f'"{t[-1]}"'})
            elif block == "object-group network" and kw == "network-object" and len(t) > 2:
                member = t[2] if t[1] in ("object", "host") else f"{t[1]} {t[2]}"
                bobj.fields["member"] = (bobj.fields.get("member", "") + f' "{member}"').strip()
            elif block == "object-group network" and kw == "group-object" and len(t) > 1:
                bobj.fields["member"] = (bobj.fields.get("member", "") + f' "{t[1]}"').strip()
            elif block == "ike":
                if kw == "encryption" and len(t) > 1:
                    bobj.fields["_enc"] = _ASA_ENC.get(t[1], t[1])
                elif kw in ("hash", "integrity") and len(t) > 1:
                    bobj.fields["_hash"] = _ASA_HASH.get(t[1], t[1])
                elif kw == "group" and len(t) > 1:
                    bobj.fields["dhgrp"] = " ".join(t[1:])
            bobj.raw += raw + "\n"
            continue

        block, bobj = None, None
        head = t[0]
        if head == "hostname" and len(t) > 1:
            _obj(store, order, "system global", "").fields["hostname"] = f'"{t[1]}"'
        elif head == "interface" and len(t) > 1:
            bobj = _obj(store, order, "system interface", t[1])
            bobj.raw = raw + "\n"
            block = "interface"
        elif head == "object" and len(t) > 2 and t[1] == "network":
            bobj = _obj(store, order, "firewall address", t[2])
            bobj.raw = raw + "\n"
            block = "object network"
        elif head == "object-group" and len(t) > 2 and t[1] == "network":
            bobj = _obj(store, order, "firewall addrgrp", t[2])
            bobj.raw = raw + "\n"
            block = "object-group network"
        elif head == "access-list" and len(t) > 4 and t[2] == "extended":
            acl, action = t[1], t[3]
            acl_seq[acl] = acl_seq.get(acl, 0) + 1
            o = _obj(store, order, "firewall policy", f"{acl}#{acl_seq[acl]}")
            o.raw = raw + "\n"
            o.fields["action"] = "accept" if action == "permit" else "deny"
            o.fields["_acl"] = acl
            i = 4
            if t[i] in ("object-group", "object"):
                svc, i = t[i + 1], i + 2
            else:
                proto, i = t[i], i + 1
                svc = None
            src, i = _asa_addr(t, i)
            dst, i = _asa_addr(t, i)
            if svc is None:
                port = None
                if i + 1 < len(t) and t[i] in ("eq", "lt", "gt", "neq"):
                    port = t[i + 1]
                elif i + 2 < len(t) and t[i] == "range":
                    port = f"{t[i + 1]}-{t[i + 2]}"
                svc = "ALL" if proto in ("ip", "any") and not port else (
                    port if port and not port.isdigit() else
                    f"{proto}/{port}" if port else proto)
            o.fields.update({"srcaddr": f'"{src}"', "dstaddr": f'"{dst}"',
                             "service": f'"{svc.upper() if svc else svc}"'})
            if "log" in t:
                o.fields["logtraffic"] = "all"
            if "inactive" in t:
                o.fields["status"] = "disable"
        elif head == "access-group" and len(t) >= 5 and t[2] == "in" and t[3] == "interface":
            acl_bind[t[1]] = t[4]
        elif head == "access-group" and len(t) >= 3 and t[2] == "global":
            acl_bind[t[1]] = "any"
        elif head == "route" and len(t) >= 5:
            n = sum(1 for k in order if k[0] == "router static") + 1
            o = _obj(store, order, "router static", str(n))
            o.raw = raw + "\n"
            o.fields.update({"device": f'"{t[1]}"', "dst": f"{t[2]} {t[3]}",
                             "gateway": t[4]})
            if len(t) >= 6 and t[5].isdigit():
                o.fields["distance"] = t[5]
        elif head in ("http", "ssh", "telnet") and len(t) >= 4 and _IP.match(t[1]):
            mgmt.append(("https" if head == "http" else head, t[1], t[2], t[3]))
        elif head == "snmp-server" and len(t) >= 3 and t[1] == "community":
            n = sum(1 for k in order if k[0] == "system snmp community") + 1
            o = _obj(store, order, "system snmp community", str(n))
            o.fields["name"] = f'"{t[2]}"'
        elif head == "username" and len(t) >= 2:
            _obj(store, order, "system admin", t[1])
        elif head == "crypto" and len(t) >= 4 and t[1] in ("ikev1", "ikev2") and \
                t[2] == "policy":
            bobj = _obj(store, order, "vpn ipsec phase1-interface", f"{t[1]}-policy-{t[3]}")
            bobj.raw = raw + "\n"
            block = "ike"
        elif head == "crypto" and len(t) >= 5 and t[1] == "ipsec" and \
                t[2] in ("transform-set", "ikev1") and "transform-set" in t:
            i = t.index("transform-set")
            if i + 1 < len(t):
                o = _obj(store, order, "vpn ipsec phase2-interface", t[i + 1])
                o.raw = raw + "\n"
                parts = [_ESP[x] for x in t[i + 2:] if x in _ESP]
                enc = [p for p in parts if not p.startswith(("md5", "sha"))]
                hsh = [p for p in parts if p.startswith(("md5", "sha"))]
                if enc and hsh:
                    o.fields["proposal"] = f"{enc[0]}-{hsh[0]}"

    # interface naming: ASA policies and routes refer to interfaces by nameif
    renamed = {}
    for key in [k for k in order if k[0] == "system interface"]:
        o = store[key]
        nameif = o.fields.pop("nameif", None)
        if nameif:
            o.name = nameif
            renamed[key] = nameif
        if o.fields.get("security-level") == "0":
            o.fields["role"] = "wan"
    # management access lines → allowaccess on the interface they name
    by_name = {store[k].name: store[k] for k in order if k[0] == "system interface"}
    for proto, net, mask, ifname in mgmt:
        o = by_name.get(ifname) or _obj(store, order, "system interface", ifname)
        have = set((o.fields.get("allowaccess") or "").split())
        o.fields["allowaccess"] = " ".join(sorted(have | {proto}))
    restricted = [f"{n} {m}" for _p, n, m, _i in mgmt if n != "0.0.0.0"]
    if mgmt and len(restricted) == len(mgmt):
        for k in order:
            if k[0] == "system admin":
                store[k].fields["trusthost1"] = restricted[0]
    # ACEs: the interface an ACL is bound to is the source interface of its entries
    for k in order:
        if k[0] == "firewall policy":
            o = store[k]
            acl = o.fields.pop("_acl", None)
            if acl in acl_bind:
                o.fields["srcintf"] = f'"{acl_bind[acl]}"'
        elif k[0] == "vpn ipsec phase1-interface":
            o = store[k]
            enc, hsh = o.fields.pop("_enc", None), o.fields.pop("_hash", None)
            if enc and hsh:
                o.fields["proposal"] = f"{enc}-{hsh}"
    return [store[k] for k in order]


# =========================================================================== #
# shared entry points
# =========================================================================== #
def parse(text, vendor=None):
    vendor = vendor or detect(text)
    if vendor == PANOS:
        return parse_panos(text)
    if vendor == ASA:
        return parse_asa(text)
    return []


def chunk(text, vendor=None):
    """Retrieval passages that keep each rule/object whole.

    Line-per-passage chunking split a PAN-OS rule across many one-line passages, and
    the stub filter then discarded every one of them — an uploaded PAN-OS config
    vanished entirely. Here every object's lines stay together."""
    vendor = vendor or detect(text)
    if vendor == PANOS:
        groups, order = {}, []
        for line in (text or "").splitlines():
            t = _pan_tokens(line)
            if not t:
                continue
            if t[0].endswith("rulebase") and len(t) >= 4:
                key = " ".join(t[:4])
            elif "static-route" in t:
                key = " ".join(t[:t.index("static-route") + 2])
            else:
                key = " ".join(t[:2])
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append(line.strip())
        # a one-line object (an address, the hostname, an admin) would be discarded as
        # a lone fragment by the stub filter — keep those together in one passage
        multi = ["\n".join(groups[k]) for k in order if len(groups[k]) > 1]
        singles = [groups[k][0] for k in order if len(groups[k]) == 1]
        if singles:
            multi.append("\n".join(singles))
        return multi
    if vendor == ASA:
        passages, cur, acls = [], [], {}
        for raw in (text or "").splitlines():
            if not raw.strip() or raw.strip().startswith(("!", ":")):
                if cur:
                    passages.append("\n".join(cur))
                    cur = []
                continue
            if raw.startswith("access-list "):
                acls.setdefault(raw.split()[1], []).append(raw.strip())
                continue
            if not raw.startswith((" ", "\t")) and cur:
                passages.append("\n".join(cur))
                cur = []
            cur.append(raw.rstrip())
        if cur:
            passages.append("\n".join(cur))
        passages += ["\n".join(lines) for lines in acls.values()]
        # one-line globals (route, http, snmp-server …) are merged so none is a stub
        singles = [p for p in passages if "\n" not in p]
        multi = [p for p in passages if "\n" in p]
        if singles:
            multi.append("\n".join(singles))
        return multi
    return []
