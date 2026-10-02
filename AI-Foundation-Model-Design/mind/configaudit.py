"""
configaudit — the part of a senior review that can be done WITHOUT a model.

An LLM asked to "review my firewall" produces plausible prose. This produces findings
that are either true of your file or not at all: every one names the exact objects it
came from, and the reasoning is arithmetic over parsed fields — set containment, index
order, reference counting. Nothing is inferred, so nothing can be hallucinated.

What it finds, and why each one matters to somebody doing this for a living:

  SHADOWED POLICY      an earlier rule fully covers a later one, so the later rule can
                       never match. The classic silent misconfiguration: someone adds a
                       rule, tests nothing, and assumes it took effect.
  ANY/ANY ACCEPT       source, destination and service all unrestricted. Usually a
                       temporary rule that became permanent.
  OVERLY PERMISSIVE    one axis unrestricted on an accept rule — narrower, still worth
                       a look.
  DUPLICATE POLICY     identical match criteria; one is dead weight, and the pair will
                       drift apart during future edits.
  UNREACHABLE AFTER    a rule sits below an any/any accept and can never be evaluated.
  DISABLED             configured but switched off. Dead config people still read as live.
  NO LOGGING           an accept rule with logging off — invisible in an incident.
  UNUSED OBJECT        an address/service defined and referenced by nothing.
  DUPLICATE ROUTE      two static routes to the same destination.
  MULTIPLE DEFAULTS    more than one default route — deliberate (ECMP) or a mistake.
  DANGLING INTERFACE   a policy or route naming an interface the config never defines.

HONESTY ABOUT LIMITS — stated in the report, not buried here:
  • Address GROUPS are not expanded. Shadowing is therefore detected only where the
    match fields are literally equal or where the earlier rule uses "all". This
    UNDER-reports (misses real shadowing); it never over-reports.
  • Ordering follows the parsed sequence, which is the file's order.
  • Interface checks only fire when the config actually defines interfaces; a partial
    export is reported as "not checked" rather than as findings.
"""
from __future__ import annotations

from dataclasses import dataclass, field as _field

# severity ranking used for sorting and display
HIGH, MEDIUM, LOW, INFO = "high", "medium", "low", "info"
_ORDER = {HIGH: 0, MEDIUM: 1, LOW: 2, INFO: 3}
_MARK = {HIGH: "🔴", MEDIUM: "🟠", LOW: "🟡", INFO: "🔵"}

# values meaning "unrestricted" in FortiGate-style configs
_ANY = {"all", "any", "*", "0.0.0.0/0", "0.0.0.0 0.0.0.0"}


@dataclass
class Finding:
    rule: str                      # short machine-ish id, e.g. "shadowed-policy"
    severity: str
    title: str                     # one line a human reads first
    detail: str                    # why it matters / what to do
    objects: list = _field(default_factory=list)   # the object names involved

    def line(self):
        who = (" [" + ", ".join(str(o) for o in self.objects) + "]") if self.objects else ""
        return f"{_MARK.get(self.severity, '•')} {self.title}{who}\n     {self.detail}"


# ---------------------------------------------------------------------------- #
# helpers
# ---------------------------------------------------------------------------- #
def _vals(o, key):
    """A set() of the values of one field. FortiGate writes multi-values on one line:
        set srcaddr "A" "B"        →  {"a", "b"}"""
    raw = (o.get(key) or "").strip()
    if not raw:
        return set()
    parts, cur, inq = [], "", False
    for ch in raw:
        if ch == '"':
            inq = not inq
            continue
        if ch.isspace() and not inq:
            if cur:
                parts.append(cur)
                cur = ""
            continue
        cur += ch
    if cur:
        parts.append(cur)
    return {p.lower() for p in parts if p}


def _is_any(values):
    return bool(values) and all(v in _ANY for v in values)


def _covers(a, b):
    """Does field-set `a` (earlier rule) cover `b` (later rule)?

    Conservative on purpose: "all" covers anything; otherwise only a literal superset
    counts, because address GROUPS are not expanded here. Under-reporting is acceptable;
    claiming a rule is dead when it isn't is not."""
    if not a:
        # The field is ABSENT, which means unknown — not "matches everything". A partial
        # export omits fields, and treating that as unrestricted would invent shadowing
        # findings for rules that are perfectly fine. Silence beats a confident lie.
        return False
    if _is_any(a):
        return True
    if not b:
        return False
    return b.issubset(a)


def _enabled(o):
    return (o.get("status") or "enable").strip().strip('"').lower() != "disable"


def _action(o):
    return (o.get("action") or "deny").strip().strip('"').lower()


def _verb(o):
    """Readable past-tense of an action — 'deny' must not print as 'denyed'."""
    return {"accept": "accepts", "deny": "denies", "drop": "drops",
            "reject": "rejects"}.get(_action(o), _action(o) + "s")


_MATCH_FIELDS = ("srcintf", "dstintf", "srcaddr", "dstaddr", "service")


def _signature(o):
    return tuple(frozenset(_vals(o, f)) for f in _MATCH_FIELDS)


# ---------------------------------------------------------------------------- #
# the checks
# ---------------------------------------------------------------------------- #
def _check_policies(policies, wan=frozenset()):
    out = []
    if not policies:
        return out

    # -- any/any accepts, permissiveness, logging, disabled ------------------- #
    any_any_index = None
    for i, p in enumerate(policies):
        name = p.get("name") or p.name
        label = f"policy {p.name}" + (f' "{str(name).strip(chr(34))}"' if name != p.name else "")
        src, dst, svc = _vals(p, "srcaddr"), _vals(p, "dstaddr"), _vals(p, "service")

        if not _enabled(p):
            out.append(Finding("disabled-policy", LOW, f"{label} is disabled",
                               "Configured but switched off. Delete it or document why "
                               "it exists — disabled rules get read as live during "
                               "incidents.", [p.name]))
            continue

        if _action(p) == "accept" and _is_any(src) and _is_any(dst) and _is_any(svc):
            if any_any_index is None:
                any_any_index = i
            out.append(Finding(
                "any-any-accept", HIGH, f"{label} accepts ANY source to ANY destination "
                "on ANY service",
                "This permits everything that reaches it. Almost always a temporary rule "
                "that was never narrowed. Restrict at least the destination and service, "
                "or move it below the specific rules and log it.", [p.name]))
        elif _action(p) == "accept":
            # "all" on the INTERNET side of a rule is the normal case, not a finding:
            # outbound browsing has destination all, a published server has source all.
            # Only an unrestricted axis on the inside is worth a reviewer's time.
            src_if, dst_if = _vals(p, "srcintf"), _vals(p, "dstintf")
            src_wan = any(_is_wan(i, wan) for i in src_if)
            dst_wan = any(_is_wan(i, wan) for i in dst_if)
            loose = [f for f, v, inet in (("source", src, src_wan),
                                          ("destination", dst, dst_wan),
                                          ("service", svc, False))
                     if _is_any(v) and not inet]
            if len(loose) >= 2:
                out.append(Finding(
                    "overly-permissive", MEDIUM,
                    f"{label} leaves {' and '.join(loose)} unrestricted",
                    "Two unrestricted axes on an accept rule is a wide opening. Narrow "
                    "whichever one you can name concretely.", [p.name]))
            elif loose:
                out.append(Finding(
                    "permissive", LOW, f"{label} leaves {loose[0]} unrestricted",
                    "Worth confirming this is intended.", [p.name]))

        log = (p.get("logtraffic") or "").strip().strip('"').lower()
        if _action(p) == "accept" and log in ("disable", "utm") and log == "disable":
            out.append(Finding(
                "no-logging", MEDIUM, f"{label} accepts traffic with logging disabled",
                "Traffic permitted by this rule leaves no record. During an incident "
                "this rule is a blind spot — set logtraffic all.", [p.name]))

    # -- unreachable below an any/any accept ---------------------------------- #
    if any_any_index is not None:
        below = [p.name for p in policies[any_any_index + 1:] if _enabled(p)]
        if below:
            shown = ", ".join(str(b) for b in below[:10])
            out.append(Finding(
                "unreachable-after-any", HIGH,
                f"{len(below)} rule(s) sit below the ANY/ANY accept and can never match",
                f"Everything reaching policy {policies[any_any_index].name} is accepted "
                f"there, so these are dead: {shown}"
                + (" …" if len(below) > 10 else "")
                + ". Move the broad rule to the bottom, or narrow it.",
                [policies[any_any_index].name]))

    # -- duplicates and shadowing --------------------------------------------- #
    seen = {}
    for i, p in enumerate(policies):
        if not _enabled(p):
            continue
        sig = _signature(p)
        if sig in seen:
            first = seen[sig]
            if _action(first) != _action(p):
                # Same match criteria, OPPOSITE decisions. Not housekeeping — whichever
                # comes first silently wins, and the other rule documents an intent the
                # device does not honour.
                out.append(Finding(
                    "conflicting-policy", HIGH,
                    f"policy {p.name} contradicts policy {first.name}",
                    f"Identical match criteria but opposite actions: policy "
                    f"{first.name} {_verb(first)} this traffic, policy {p.name} "
                    f"{_verb(p)} it. Policy {first.name} is evaluated first and wins, "
                    f"so the {_action(p)} rule is decoration.",
                    [first.name, p.name]))
            else:
                out.append(Finding(
                    "duplicate-policy", MEDIUM,
                    f"policy {p.name} duplicates policy {first.name}",
                    "Identical match criteria. One of them never fires, and the pair will "
                    "drift apart the next time someone edits 'the' rule.",
                    [first.name, p.name]))
        else:
            seen[sig] = p

    for i, later in enumerate(policies):
        if not _enabled(later):
            continue
        for earlier in policies[:i]:
            if not _enabled(earlier):
                continue
            if _signature(earlier) == _signature(later):
                continue                       # already reported as a duplicate
            if all(_covers(_vals(earlier, f), _vals(later, f)) for f in _MATCH_FIELDS):
                same = _action(earlier) == _action(later)
                out.append(Finding(
                    "shadowed-policy", HIGH if not same else MEDIUM,
                    f"policy {later.name} is shadowed by policy {earlier.name}",
                    f"Policy {earlier.name} matches everything policy {later.name} would, "
                    f"and is evaluated first, so policy {later.name} never takes effect"
                    + ("" if same else
                       f" — and the two disagree: policy {later.name} "
                       f"{_verb(later)} this traffic, but policy {earlier.name} "
                       f"{_verb(earlier)} it first")
                    + ". Reorder them, or narrow the earlier rule.",
                    [earlier.name, later.name]))
                break                          # one shadower is enough to report
    return out


def _check_routes(routes):
    out = []
    by_dst, defaults = {}, []
    for r in routes:
        dst = (r.get("dst") or "").strip().strip('"')
        gw = (r.get("gateway") or "").strip().strip('"')
        if dst in _ANY or dst in ("0.0.0.0 0.0.0.0", "0.0.0.0/0", ""):
            defaults.append((r, gw))
            continue
        by_dst.setdefault(dst, []).append((r, gw))

    for dst, rs in by_dst.items():
        if len(rs) > 1:
            gws = {gw for _, gw in rs}
            names = [r.name for r, _ in rs]
            if len(gws) > 1:
                out.append(Finding(
                    "conflicting-route", MEDIUM,
                    f"{len(rs)} routes to {dst} with different gateways",
                    f"Gateways: {', '.join(sorted(g for g in gws if g))}. Deliberate "
                    "failover/ECMP is fine — otherwise one of these is wrong and which "
                    "one wins depends on distance/priority.", names))
            else:
                out.append(Finding(
                    "duplicate-route", LOW, f"{len(rs)} identical routes to {dst}",
                    "Same destination and gateway configured more than once.", names))

    if len(defaults) > 1:
        gws = sorted({gw for _, gw in defaults if gw})
        out.append(Finding(
            "multiple-defaults", MEDIUM, f"{len(defaults)} default routes configured",
            f"Gateways: {', '.join(gws) or '(none named)'}. Intentional for ECMP or "
            "failover; otherwise traffic leaves by whichever wins on distance/priority, "
            "which is rarely what someone expects.",
            [r.name for r, _ in defaults]))
    elif not defaults and routes:
        out.append(Finding("no-default-route", INFO, "no default route in this config",
                           "Normal for an internal device or a partial export; worth "
                           "confirming if this box faces the internet.", []))
    return out


def _check_unused(objects, policies):
    """An address/service defined but referenced by no policy."""
    out = []
    referenced = set()
    for p in policies:
        for f in ("srcaddr", "dstaddr", "service", "poolname", "nat-ippool"):
            referenced |= _vals(p, f)
    # address groups reference their members
    for o in objects:
        if "addrgrp" in (o.kind or "").lower() or "group" in (o.kind or "").lower():
            referenced |= _vals(o, "member")

    for kindsub, label in (("address", "address object"), ("service custom", "service")):
        defined = [o for o in objects if kindsub in (o.kind or "").lower()
                   and "group" not in (o.kind or "").lower()]
        unused = [o for o in defined if str(o.name).lower() not in referenced]
        if unused and defined:
            shown = ", ".join(str(o.name) for o in unused[:8])
            out.append(Finding(
                "unused-object", LOW,
                f"{len(unused)} of {len(defined)} {label}s are referenced by no policy",
                f"Examples: {shown}" + (" …" if len(unused) > 8 else "")
                + ". Harmless but they accumulate, and an unused object is often the "
                "leftover of a change that was only half applied.",
                []))                          # examples are in the detail; don't repeat
    return out


def _check_interfaces(objects, policies, routes):
    """Policies/routes naming an interface the config never defines."""
    ifaces = {str(o.name).lower() for o in objects
              if "system interface" in (o.kind or "").lower()}
    # a ZONE (FortiGate `system zone`, Palo Alto security zones) is a valid policy
    # interface reference too — without this every PAN-OS rule looked dangling
    ifaces |= {str(o.name).lower() for o in objects
               if (o.kind or "").strip().lower() == "system zone"}
    if not ifaces:
        return [Finding("interfaces-not-checked", INFO,
                        "interface references not checked",
                        "This export contains no `config system interface` section, so "
                        "I can't tell whether the interfaces named in policies and routes "
                        "exist. Include that section to enable the check.", [])]
    out, missing = [], {}
    for p in policies:
        for f in ("srcintf", "dstintf"):
            for v in _vals(p, f):
                if v not in ifaces and v not in _ANY:
                    missing.setdefault(v, []).append(f"policy {p.name}")
    for r in routes:
        for v in _vals(r, "device"):
            if v not in ifaces and v not in _ANY:
                missing.setdefault(v, []).append(f"route {r.name}")
    for iface, who in sorted(missing.items()):
        out.append(Finding(
            "dangling-interface", MEDIUM,
            f"interface '{iface}' is referenced but never defined",
            f"Referenced by {', '.join(who[:6])}"
            + (" …" if len(who) > 6 else "")
            + ". Either the export is partial, or these rules point at an interface that "
            "no longer exists — in which case they don't do what they look like they do.",
            sorted(set(who))[:6]))
    return out


# ---------------------------------------------------------------------------- #
# DEVICE HARDENING
#
# The rule-base checks above find logic errors between policies. These find the device
# itself exposed: management reachable from the internet, cleartext admin protocols,
# weak VPN cryptography, default SNMP communities. They cover the ground of the public
# FortiGate hardening guides (the CIS FortiGate Benchmark and the audit tools built on
# it) — written here from the practices themselves, not copied from any benchmark text.
#
# Same discipline as everything else in this file: a setting that is ABSENT from the
# export is never assumed to be bad. Where FortiOS's default is the insecure value
# (admin trusted hosts, which default to "anywhere") absence is reported, because in
# that case absence genuinely is the insecure state.
# ---------------------------------------------------------------------------- #
import re as _re

_WAN_NAME = _re.compile(r"(^|[^a-z])(wan\d*|internet|outside|external|isp\d*|untrust\w*)"
                        r"($|[^a-z])", _re.I)
_MGMT = {"https", "ssh", "http", "telnet", "snmp"}
_CLEARTEXT = {"http", "telnet"}


def _kind(objects, name):
    return [o for o in objects if (o.kind or "").strip().lower() == name]


def _one(objects, name):
    found = _kind(objects, name)
    return found[0] if found else None


def _val(o, key):
    return (o.get(key) or "").strip().strip('"').lower()


def _wan_interfaces(objects):
    """Names of internet-facing interfaces: those the config gives role 'wan', plus
    names that say so (wan1, internet, outside, isp2 …)."""
    names = set()
    for o in _kind(objects, "system interface"):
        if _val(o, "role") == "wan" or _WAN_NAME.search(str(o.name)):
            names.add(str(o.name).lower())
    return names


def _is_wan(name, wan):
    return name in wan or bool(_WAN_NAME.search(name))


def _check_hardening(objects, policies):
    out = []
    wan = _wan_interfaces(objects)

    # -- management access on interfaces --------------------------------------- #
    for o in _kind(objects, "system interface"):
        name = str(o.name)
        access = _vals(o, "allowaccess")
        if not access:
            continue
        exposed = sorted(access & _MGMT)
        if exposed and _is_wan(name.lower(), wan):
            out.append(Finding(
                "wan-management", HIGH,
                f"interface {name} (internet-facing) accepts {', '.join(exposed)} "
                "management access",
                "The firewall's own admin interface is reachable from the internet — the "
                "single most attacked surface on any FortiGate. Remove these from "
                f"allowaccess on {name} and manage it from an internal interface or VPN.",
                [name]))
        elif access & _CLEARTEXT:
            clear = sorted(access & _CLEARTEXT)
            out.append(Finding(
                "cleartext-admin", MEDIUM,
                f"interface {name} allows {' and '.join(clear)} (unencrypted) admin access",
                "Admin credentials cross the network in cleartext. Use https and ssh "
                "only.", [name]))

    # -- administrator accounts ------------------------------------------------ #
    for o in _kind(objects, "system admin"):
        name = str(o.name)
        hosts = [v for k, v in o.fields.items()
                 if k.startswith("trusthost") or k.startswith("ip6-trusthost")]
        restricted = [h for h in hosts
                      if h.strip().strip('"') not in ("0.0.0.0 0.0.0.0", "::/0", "")]
        if not restricted:
            out.append(Finding(
                "admin-no-trusthost", MEDIUM,
                f"admin account '{name}' can log in from any address",
                "No trusted hosts are set, which in FortiOS means anywhere. Set "
                "trusthost1 to your management subnet so a stolen password alone is not "
                "enough.", [name]))
        if name.lower() == "admin":
            out.append(Finding(
                "default-admin-name", LOW, "the default 'admin' account is still in use",
                "Every password-spraying attempt targets 'admin' first. Create a named "
                "super-admin account and remove or rename this one.", [name]))

    # -- device-wide settings ---------------------------------------------------- #
    g = _one(objects, "system global")
    if g is not None:
        tls = _vals(g, "admin-https-ssl-versions")
        weak = sorted(v for v in tls if v in ("tlsv1-0", "tlsv1-1", "sslv3"))
        if weak:
            out.append(Finding(
                "weak-admin-tls", MEDIUM,
                f"admin HTTPS still accepts {', '.join(weak)}",
                "These protocol versions are deprecated and broken. Allow tlsv1-2 and "
                "tlsv1-3 only.", ["system global"]))
        if _val(g, "strong-crypto") == "disable":
            out.append(Finding(
                "strong-crypto-off", MEDIUM, "strong-crypto is disabled",
                "The device will negotiate weak ciphers for HTTPS, SSH and VPN. "
                "Set strong-crypto enable.", ["system global"]))
        t = _val(g, "admintimeout")
        if t.isdigit() and int(t) > 15:
            out.append(Finding(
                "long-admin-timeout", LOW, f"admin sessions stay open for {t} minutes idle",
                "An unattended logged-in browser stays an open door that long. 5–15 "
                "minutes is usual.", ["system global"]))

    pp = _one(objects, "system password-policy")
    if pp is not None:
        if _val(pp, "status") == "disable":
            out.append(Finding(
                "password-policy-off", MEDIUM, "the admin password policy is disabled",
                "Nothing stops a short or trivial admin password. Enable it with a "
                "minimum length of at least 12.", ["system password-policy"]))
        else:
            n = _val(pp, "minimum-length")
            if n.isdigit() and int(n) < 8:
                out.append(Finding(
                    "short-passwords", LOW, f"admin passwords may be as short as {n}",
                    "Raise minimum-length to at least 12.", ["system password-policy"]))

    # -- SNMP --------------------------------------------------------------------- #
    for o in _kind(objects, "system snmp community"):
        cname = _val(o, "name")
        if cname in ("public", "private"):
            out.append(Finding(
                "snmp-default-community", HIGH,
                f"SNMP community '{cname}' is configured",
                "The first community string every scanner tries. It exposes the device's "
                "configuration and interfaces to anyone who can reach SNMP. Remove it, "
                "and prefer SNMPv3.", [o.name]))
        elif _val(o, "status") != "disable":
            out.append(Finding(
                "snmp-v2c", LOW, f"SNMPv1/v2c community '{cname or o.name}' is in use",
                "v1/v2c send the community string in cleartext. SNMPv3 with auth and "
                "privacy is the replacement.", [o.name]))

    # -- VPN cryptography ------------------------------------------------------- #
    for kindname in ("vpn ipsec phase1-interface", "vpn ipsec phase1",
                     "vpn ipsec phase2-interface", "vpn ipsec phase2"):
        for o in _kind(objects, kindname):
            name = str(o.name)
            props = _vals(o, "proposal")
            broken = sorted(p for p in props
                            if p.startswith(("des-", "3des-", "null-")) or p.endswith("-md5"))
            if broken:
                out.append(Finding(
                    "weak-ipsec-crypto", HIGH,
                    f"VPN {name} offers broken crypto: {', '.join(broken)}",
                    "DES, 3DES and MD5 can be broken or downgraded to. Offer only AES-GCM "
                    "or AES with SHA-256 or better.", [name]))
            elif any(p.endswith("-sha1") for p in props):
                out.append(Finding(
                    "sha1-ipsec", LOW, f"VPN {name} still offers SHA-1",
                    "SHA-1 is deprecated for new deployments. Prefer SHA-256 or better.",
                    [name]))
            weak_dh = sorted(d for d in _vals(o, "dhgrp") if d in ("1", "2", "5"))
            if weak_dh:
                out.append(Finding(
                    "weak-dh-group", MEDIUM,
                    f"VPN {name} allows weak Diffie-Hellman group(s) {', '.join(weak_dh)}",
                    "Groups 1, 2 and 5 are too small for today. Use 14 or higher, "
                    "ideally 19/20/21.", [name]))
            if "phase1" in kindname and _val(o, "mode") == "aggressive":
                out.append(Finding(
                    "ike-aggressive-mode", MEDIUM, f"VPN {name} uses IKEv1 aggressive mode",
                    "Aggressive mode exposes a hash of the pre-shared key to anyone who "
                    "initiates a connection, which can then be cracked offline. Use main "
                    "mode or IKEv2.", [name]))
            if "phase2" in kindname and _val(o, "pfs") == "disable":
                out.append(Finding(
                    "no-pfs", LOW, f"VPN {name} has perfect forward secrecy disabled",
                    "Without PFS, one leaked key decrypts past sessions too.", [name]))

    ssl = _one(objects, "vpn ssl settings")
    if ssl is not None and _val(ssl, "ssl-min-proto-ver") in ("tls1-0", "tls1-1"):
        out.append(Finding(
            "weak-sslvpn-tls", MEDIUM,
            f"SSL-VPN accepts {_val(ssl, 'ssl-min-proto-ver')}",
            "Set ssl-min-proto-ver tls1-2.", ["vpn ssl settings"]))

    # -- policies in the internet's direction ------------------------------------ #
    for p in policies:
        if not _enabled(p) or _action(p) != "accept":
            continue
        src_if, dst_if = _vals(p, "srcintf"), _vals(p, "dstintf")
        label = f"policy {p.name}"
        if any(_is_wan(i, wan) for i in src_if) and not any(_is_wan(i, wan) for i in dst_if) \
                and _is_any(_vals(p, "dstaddr")):
            out.append(Finding(
                "inbound-to-any", HIGH,
                f"{label} lets the internet reach ANY internal address",
                "An inbound accept should name the exact servers it publishes (usually a "
                "VIP). With dstaddr all, every internal host is one open port away.",
                [p.name]))
        if any(_is_wan(i, wan) for i in dst_if) and not any(_is_wan(i, wan) for i in src_if):
            inspected = (_val(p, "utm-status") == "enable"
                         or any(_val(p, k) for k in ("av-profile", "ips-sensor",
                                                     "webfilter-profile",
                                                     "application-list",
                                                     "profile-group")))
            if not inspected:
                out.append(Finding(
                    "no-inspection", LOW,
                    f"{label} sends traffic to the internet without security profiles",
                    "No AV, IPS, web filter or application control on this path, so "
                    "malware downloads and command-and-control traffic go unexamined.",
                    [p.name]))
    return out


# ---------------------------------------------------------------------------- #
# public API
# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #
# PUBLISHED SERVICES (VIP / destination NAT)
#
# A VIP is how a FortiGate puts an internal server on the internet. These checks
# answer the questions an exposure review starts with: what is published, is anything
# published that never should be, and is each publication actually narrowed by a
# policy. Matching is by object NAME (a policy's dstaddr naming the VIP or a group
# containing it) — exact, with no address arithmetic.
# ---------------------------------------------------------------------------- #

# services that should essentially never face the internet directly
_ADMIN_SERVICES = {"rdp", "ssh", "telnet", "smb", "samba", "cifs", "mssql", "mysql",
                   "postgres", "postgresql", "oracle", "vnc", "winrm", "ldap", "snmp",
                   "netbios", "ms-sql", "redis", "mongodb", "elasticsearch"}
# well-known admin ports, for VIPs that forward by number
_ADMIN_PORTS = {"22": "ssh", "23": "telnet", "445": "smb", "139": "netbios",
                "1433": "mssql", "3306": "mysql", "3389": "rdp", "5432": "postgres",
                "5900": "vnc", "5985": "winrm", "5986": "winrm", "389": "ldap",
                "161": "snmp", "6379": "redis", "27017": "mongodb", "9200": "elasticsearch"}


def _group_members(objects):
    """address/VIP group name → set of member names (one level; groups of groups are
    followed by _reaches)."""
    out = {}
    for o in objects:
        k = (o.kind or "").lower()
        if "grp" in k or "group" in k:
            out[str(o.name).lower()] = _vals(o, "member")
    return out


def _reaches(name, target, groups, seen=None):
    """Does address name `name` refer to `target`, directly or through groups?"""
    name = name.lower()
    if name == target:
        return True
    seen = seen or set()
    if name in seen:
        return False
    seen.add(name)
    return any(_reaches(m, target, groups, seen) for m in groups.get(name, ()))


def vip_exposure(objects):
    """[(vip, external, internal, ports, policies)] — every published service."""
    groups = _group_members(objects)
    policies = [p for p in objects if is_firewall_policy(p) and _enabled(p)
                and _action(p) == "accept"]
    rows = []
    for v in _kind(objects, "firewall vip"):
        name = str(v.name).lower()
        ext = (v.get("extip") or "").strip('"') or "?"
        mapped = " ".join(_vals(v, "mappedip")) or "?"
        if _val(v, "portforward") == "enable":
            ports = f"{_val(v, 'protocol') or 'tcp'} {(v.get('extport') or '?').strip()}"
            if v.get("mappedport"):
                ports += f" → {v.get('mappedport').strip()}"
        else:
            ports = "ALL PORTS"
        users = [p for p in policies
                 if any(_reaches(d, name, groups) for d in _vals(p, "dstaddr"))]
        rows.append((v, ext, mapped, ports, users))
    return rows


def _check_vips(objects):
    out = []
    for v, ext, mapped, ports, users in vip_exposure(objects):
        name = str(v.name)
        if _val(v, "portforward") != "enable":
            out.append(Finding(
                "vip-all-ports", HIGH,
                f"VIP {name} forwards EVERY port on {ext} to {mapped}",
                "Without port forwarding, the whole internal host is published — every "
                "service it runs, including ones nobody meant to expose. Enable "
                "portforward and publish only the ports the service needs.", [name]))
        else:
            port = (v.get("extport") or "").strip().split("-")[0]
            svc = _ADMIN_PORTS.get(port)
            if svc:
                out.append(Finding(
                    "vip-admin-port", HIGH,
                    f"VIP {name} publishes {svc.upper()} (port {port}) on {ext}",
                    f"{svc.upper()} on the internet is one of the most attacked "
                    "exposures there is. Put it behind the VPN instead.", [name]))
        if not users:
            out.append(Finding(
                "vip-unused", LOW, f"VIP {name} is not used by any accept policy",
                "Defined but not published — harmless now, but it is a ready-made "
                "exposure the moment someone references it. Remove it if unneeded.",
                [name]))
            continue
        for p in users:
            svcs = {s.lower() for s in _vals(p, "service")}
            if svcs & {"all", "any"}:
                out.append(Finding(
                    "vip-any-service", HIGH,
                    f"policy {p.name} allows ANY service to published server {name}",
                    "The VIP may narrow ports, but this policy does not — whatever the "
                    "VIP forwards is reachable. Name the exact services.", [p.name, name]))
            risky = sorted(svcs & _ADMIN_SERVICES)
            if risky:
                out.append(Finding(
                    "vip-admin-service", HIGH,
                    f"policy {p.name} publishes {', '.join(s.upper() for s in risky)} "
                    f"on server {name}",
                    "Administrative and database services should not face the internet. "
                    "Reach them over the VPN.", [p.name, name]))
    return out


def exposure_report(objects):
    """What this device publishes to the internet, then the findings about it."""
    rows = vip_exposure(objects)
    if not rows:
        return ("**Published services** — no VIPs (destination NAT) are configured, so "
                "this device publishes no internal servers to the internet.")
    lines = [f"**Published services** — {len(rows)} VIP(s):", ""]
    for v, ext, mapped, ports, users in rows:
        via = ", ".join(f"policy {p.name}" for p in users) or "no accept policy"
        lines.append(f"  • **{v.name}** — {ext} → {mapped}  [{ports}]  via {via}")
    findings = group(_check_vips(objects))
    if findings:
        lines += ["", "**Findings:**"] + [f.line() for f in findings]
    else:
        lines += ["", "No exposure findings: every publication is port-limited, used by "
                  "a policy, and narrowed to named services."]
    return "\n".join(lines)


# ---------------------------------------------------------------------------- #
# RULE-BASE CLEANUP PLAN
#
# Turns the review into a work list, sorted by how safe each action is:
#   SAFE TO DELETE   can never match or does nothing (shadowed by a rule with the same
#                    action, duplicate, disabled, unreachable, unused object)
#   DECIDE FIRST     the config contradicts itself; someone must say which intent wins
#   MERGE            accept rules identical except for one field
# ---------------------------------------------------------------------------- #
_MERGE_AXES = ("service", "srcaddr", "dstaddr")


def merge_candidates(policies):
    """Groups of enabled accept policies identical in every match field but one."""
    fields = ("srcintf", "dstintf", "srcaddr", "dstaddr", "service", "schedule")
    out = []
    live = [p for p in policies if _enabled(p) and _action(p) == "accept"]
    for axis in _MERGE_AXES:
        buckets = {}
        for p in live:
            key = tuple(frozenset(_vals(p, f)) for f in fields if f != axis) + \
                  (bool(_vals(p, "utm-status")), frozenset(_vals(p, "nat")))
            if all(_vals(p, f) for f in ("srcintf", "dstintf")):
                buckets.setdefault(key, []).append(p)
        for group_ in buckets.values():
            if len(group_) >= 2 and len({frozenset(_vals(p, axis)) for p in group_}) > 1:
                out.append((axis, group_))
    return out


def cleanup_plan(objects):
    """A prioritised rule-base cleanup list."""
    objects = list(objects or [])
    findings = audit(objects)
    policies = [o for o in objects if is_firewall_policy(o)]
    delete, decide = [], []
    for f in findings:
        if f.rule == "shadowed-policy" and "disagree" not in f.detail:
            delete.append(f"policy {f.objects[-1]} — never matches; shadowed by policy "
                          f"{f.objects[0]} with the same action")
        elif f.rule == "duplicate-policy":
            delete.append(f"policy {f.objects[-1]} — duplicate of policy {f.objects[0]}")
        elif f.rule == "disabled-policy":
            delete.append(f"policy {f.objects[0]} — disabled")
        elif f.rule == "unused-object":
            delete.append(f"{f.title} ({f.detail.split('.')[0].replace('Examples: ', '')})")
        elif f.rule == "vip-unused":
            delete.append(f"VIP {f.objects[0]} — not used by any policy")
        elif f.rule == "unreachable-after-any":
            decide.append(f"{f.title} — move the broad rule {f.objects[0]} down or "
                          "narrow it, then re-run the review")
        elif f.rule == "conflicting-policy" or (f.rule == "shadowed-policy"
                                                and "disagree" in f.detail):
            decide.append(f"{f.title} — the two rules disagree; decide which action is "
                          "intended, then delete the other")
    # a rule already slated for deletion, or caught in a contradiction, is not a merge
    # candidate — merging it would carry a dead or disputed rule into the new one
    settled = set()
    for f in findings:
        if f.rule in ("duplicate-policy", "disabled-policy", "conflicting-policy") or \
                (f.rule == "shadowed-policy"):
            settled.add(str(f.objects[-1]))
    merges = [(axis, grp) for axis, grp in
              merge_candidates([p for p in policies if str(p.name) not in settled])]

    lines = [f"**Rule-base cleanup plan** — {len(policies)} policies reviewed.", ""]
    if not (delete or decide or merges):
        lines.append("Nothing to clean up: no dead, duplicate, contradictory or mergeable "
                     "rules.")
        return "\n".join(lines)
    lines.append(f"Safe to delete: **{len(delete)}** · decide first: **{len(decide)}** · "
                 f"merge groups: **{len(merges)}**")
    if decide:
        lines += ["", "**1. Decide first** (the config contradicts itself):"]
        lines += [f"  ⚠️ {d}" for d in decide]
    if delete:
        lines += ["", "**2. Safe to delete** (these never take effect):"]
        lines += [f"  🗑️ {d}" for d in delete]
    if merges:
        lines += ["", "**3. Merge candidates** (identical except one field):"]
        for axis, grp in merges:
            ids = ", ".join(str(p.name) for p in grp)
            vals = sorted({v for p in grp for v in _vals(p, axis)})
            lines.append(f"  🔗 policies {ids} differ only in {axis} — one rule with "
                         f"{axis} {' '.join(vals)} would replace them")
    lines += ["", "*Order matters: resolve 1 before deleting anything in 2, because a "
              "contradiction decides which rule is the dead one. Back up the config "
              "first, then ask  what changed  after re-uploading to confirm the effect.*"]
    return "\n".join(lines)


def is_firewall_policy(o):
    """A FIREWALL policy (firewall policy / policy6 / proxy-policy …) — not every object
    whose kind merely contains the word. `config system password-policy` is a settings
    block, and counting it made the review report 'policy  is disabled' with no name."""
    k = (o.kind or "").strip().lower()
    return (k.startswith("firewall") and "policy" in k and "shaping" not in k
            and ">" not in k and not getattr(o, "parent", ""))


def audit(objects):
    """Run every check over parsed ConfigObjects. Returns findings, worst first."""
    objects = list(objects or [])
    policies = [o for o in objects if is_firewall_policy(o)]
    routes = [o for o in objects if "static" in (o.kind or "").lower()
              and "router" in (o.kind or "").lower() and ">" not in (o.kind or "")]

    findings = []
    findings += _check_policies(policies, _wan_interfaces(objects))
    findings += _check_routes(routes)
    findings += _check_unused(objects, policies)
    findings += _check_interfaces(objects, policies, routes)
    findings += _check_hardening(objects, policies)
    findings += _check_vips(objects)
    findings.sort(key=lambda f: (_ORDER.get(f.severity, 9), f.rule))
    return findings


# How a repeated finding should be phrased once, instead of N times. {n} is the count,
# {total} the population it was drawn from, {names} a few example objects.
_GROUPED = {
    "permissive": ("{n} of {total} policies leave one axis unrestricted",
                   "Same shape on all of them, so this is a design pattern rather than "
                   "a mistake — but it means each rule is wider than its name suggests. "
                   "Examples: {names}."),
    "overly-permissive": ("{n} of {total} policies leave two or more axes unrestricted",
                          "Each of these is a wide opening. Narrow whichever axis you can "
                          "name concretely. Examples: {names}."),
    "no-logging": ("{n} accept rules have logging disabled",
                   "Traffic permitted by these leaves no record — a blind spot during an "
                   "incident. Examples: {names}."),
    "disabled-policy": ("{n} policies are disabled",
                        "Dead config that still reads as live. Examples: {names}."),
    "duplicate-policy": ("{n} duplicate policy pairs",
                         "Identical match criteria; one of each pair never fires. "
                         "Examples: {names}."),
    "shadowed-policy": ("{n} policies are shadowed by an earlier rule",
                        "These never take effect. Examples: {names}."),
    "conflicting-policy": ("{n} policy pairs contradict each other",
                           "Same match criteria, opposite actions — the earlier one "
                           "silently wins. Examples: {names}."),
    "dangling-interface": ("{n} interfaces are referenced but never defined",
                           "Either the export is partial, or these rules point at "
                           "interfaces that no longer exist. Examples: {names}."),
    "duplicate-route": ("{n} duplicate route destinations", "Examples: {names}."),
    "admin-no-trusthost": ("{n} admin accounts can log in from any address",
                           "No trusted hosts are set on them. Examples: {names}."),
    "no-inspection": ("{n} of {total} policies send traffic to the internet without "
                      "security profiles",
                      "No AV, IPS, web filter or app control on these paths. "
                      "Examples: {names}."),
    "weak-ipsec-crypto": ("{n} VPNs offer broken crypto (DES/3DES/MD5)",
                          "Offer only AES-GCM or AES with SHA-256+. Examples: {names}."),
    "snmp-v2c": ("{n} SNMPv1/v2c communities are in use",
                 "Cleartext community strings; move to SNMPv3. Examples: {names}."),
    "conflicting-route": ("{n} destinations have routes with different gateways",
                          "Deliberate failover is fine; otherwise one of each pair is "
                          "wrong. Examples: {names}."),
}

# Which population each rule's "{n} of {total}" is drawn from. Guessing this from the
# rule name produced "120 of 40 policies"; it is small enough to state outright.
_POPULATION = {
    "permissive": "policies", "overly-permissive": "policies",
    "no-logging": "policies", "disabled-policy": "policies",
    "duplicate-policy": "policies", "shadowed-policy": "policies",
    "conflicting-policy": "policies", "dangling-interface": "interfaces",
    "duplicate-route": "routes", "conflicting-route": "routes",
    "no-inspection": "policies",
}

# Below this many occurrences, list them individually — the detail is still readable.
_GROUP_AT = 4


def group(findings, population=None):
    """Collapse a repeated finding into ONE that states the pattern and its size.

    A review that prints the same sentence 120 times is a linter dump: the reader
    learns nothing they could not have learned from the first line, and the findings
    that matter are buried under the ones that don't. Stating it once, with a count and
    examples, is both shorter and more informative."""
    population = population or {}
    by_rule = {}
    for f in findings:
        by_rule.setdefault(f.rule, []).append(f)

    out = []
    for rule, group_ in by_rule.items():
        if len(group_) < _GROUP_AT or rule not in _GROUPED:
            out.extend(group_)
            continue
        title_t, detail_t = _GROUPED[rule]
        names = []
        for f in group_:
            for o in f.objects:
                if str(o) not in names:
                    names.append(str(o))
        popkey = _POPULATION.get(rule)
        total = (population.get(popkey) if popkey else None) or len(group_)
        ctx = {"n": len(group_), "total": total,
               "names": ", ".join(names[:6]) + (" …" if len(names) > 6 else "")}
        # A pattern present on essentially everything is a design choice, not a defect —
        # but only judge that where the population is actually known. Otherwise four
        # SNMP communities would be measured against the number of POLICIES.
        sev = group_[0].severity
        if popkey and len(group_) >= max(4, int(total * 0.9)) and sev == LOW:
            sev = INFO
        # objects=[] on purpose: the detail already names examples, and Finding.line()
        # would otherwise print the same ids twice on one finding.
        out.append(Finding(rule, sev, title_t.format(**ctx), detail_t.format(**ctx), []))
    out.sort(key=lambda f: (_ORDER.get(f.severity, 9), f.rule))
    return out


# ---------------------------------------------------------------------------- #
# COMPLIANCE MAPPING
#
# Each finding tagged to the controls it bears on, for evidence and audit reports.
# Deliberately conservative: a check is only mapped to a control it clearly relates
# to. Where no control fits cleanly the entry is left out rather than guessed — a wrong
# control number in an audit pack does more harm than a missing one.
#
# PCI DSS v4.0 · ISO/IEC 27001:2022 Annex A · NIST SP 800-53 Rev. 5
# ---------------------------------------------------------------------------- #
PCI, ISO, NIST = "PCI DSS 4.0", "ISO 27001:2022", "NIST 800-53"
FRAMEWORKS = (PCI, ISO, NIST)

_RULE_HYGIENE = {PCI: ["1.2.7"], ISO: ["A.8.9"], NIST: ["CM-6"]}
_TOO_OPEN = {PCI: ["1.2.5", "1.4.2"], ISO: ["A.8.20", "A.8.22"], NIST: ["SC-7", "CM-7"]}
_VPN_CRYPTO = {PCI: ["4.2.1"], ISO: ["A.8.24"], NIST: ["SC-8", "SC-13"]}
_ADMIN_CRYPTO = {PCI: ["2.2.7"], ISO: ["A.8.24", "A.8.5"], NIST: ["SC-8", "SC-13"]}

CONTROLS = {
    # rule-base logic
    "shadowed-policy": _RULE_HYGIENE, "conflicting-policy": _RULE_HYGIENE,
    "duplicate-policy": _RULE_HYGIENE, "unreachable-after-any": _RULE_HYGIENE,
    "disabled-policy": _RULE_HYGIENE, "unused-object": _RULE_HYGIENE,
    "dangling-interface": {ISO: ["A.8.9"], NIST: ["CM-6"]},
    "any-any-accept": _TOO_OPEN, "overly-permissive": _TOO_OPEN,
    "permissive": _TOO_OPEN, "inbound-to-any": _TOO_OPEN,
    "no-logging": {PCI: ["10.2.1"], ISO: ["A.8.15"], NIST: ["AU-2", "AU-12"]},
    "no-inspection": {ISO: ["A.8.7"], NIST: ["SI-3", "SI-4"]},
    # published services (VIP / destination NAT)
    "vip-all-ports": _TOO_OPEN, "vip-any-service": _TOO_OPEN,
    "vip-admin-port": _TOO_OPEN, "vip-admin-service": _TOO_OPEN,
    "vip-unused": _RULE_HYGIENE,
    # routing
    "conflicting-route": {ISO: ["A.8.9"], NIST: ["CM-6"]},
    "duplicate-route": {ISO: ["A.8.9"], NIST: ["CM-6"]},
    "multiple-defaults": {ISO: ["A.8.9"], NIST: ["CM-6"]},
    # administrative access
    "wan-management": {PCI: ["1.4.2"], ISO: ["A.8.2", "A.8.20"], NIST: ["SC-7", "AC-17"]},
    "admin-no-trusthost": {ISO: ["A.8.2", "A.8.20"], NIST: ["AC-17"]},
    "cleartext-admin": _ADMIN_CRYPTO, "weak-admin-tls": _ADMIN_CRYPTO,
    "strong-crypto-off": _ADMIN_CRYPTO,
    "default-admin-name": {PCI: ["2.2.2"], ISO: ["A.8.2"], NIST: ["CM-6"]},
    "password-policy-off": {PCI: ["8.3.6"], ISO: ["A.5.17", "A.8.5"], NIST: ["IA-5"]},
    "short-passwords": {PCI: ["8.3.6"], ISO: ["A.5.17", "A.8.5"], NIST: ["IA-5"]},
    "long-admin-timeout": {PCI: ["8.2.8"], ISO: ["A.8.5"], NIST: ["AC-12"]},
    # SNMP
    "snmp-default-community": {PCI: ["2.2.2"], ISO: ["A.8.21", "A.8.9"],
                               NIST: ["CM-6", "CM-7"]},
    "snmp-v2c": {PCI: ["1.2.6"], ISO: ["A.8.21"], NIST: ["SC-8", "CM-7"]},
    # VPN
    "weak-ipsec-crypto": _VPN_CRYPTO, "sha1-ipsec": _VPN_CRYPTO,
    "weak-dh-group": _VPN_CRYPTO, "no-pfs": _VPN_CRYPTO,
    "ike-aggressive-mode": _VPN_CRYPTO, "weak-sslvpn-tls": _VPN_CRYPTO,
}

# What each referenced control is, so the report is readable without the standards
CONTROL_TITLES = {
    "1.2.5": "allowed services, protocols and ports are identified and approved",
    "1.2.6": "security features defined for insecure services and protocols",
    "1.2.7": "network security control configurations reviewed every six months",
    "1.4.2": "inbound traffic from untrusted networks is restricted",
    "2.2.2": "vendor default accounts are managed",
    "2.2.7": "non-console administrative access is encrypted",
    "4.2.1": "strong cryptography protects data over open, public networks",
    "8.2.8": "idle sessions over 15 minutes require re-authentication",
    "8.3.6": "passwords are at least 12 characters",
    "10.2.1": "audit logs are enabled and active",
    "A.5.17": "authentication information",
    "A.8.2": "privileged access rights",
    "A.8.5": "secure authentication",
    "A.8.7": "protection against malware",
    "A.8.9": "configuration management",
    "A.8.15": "logging",
    "A.8.20": "networks security",
    "A.8.21": "security of network services",
    "A.8.22": "segregation of networks",
    "A.8.24": "use of cryptography",
    "AC-12": "session termination",
    "AC-17": "remote access",
    "AU-2": "event logging",
    "AU-12": "audit record generation",
    "CM-6": "configuration settings",
    "CM-7": "least functionality",
    "IA-5": "authenticator management",
    "SC-7": "boundary protection",
    "SC-8": "transmission confidentiality and integrity",
    "SC-13": "cryptographic protection",
    "SI-3": "malicious code protection",
    "SI-4": "system monitoring",
}


def controls_for(rule):
    """{framework: [control ids]} for one finding rule; {} when unmapped."""
    return CONTROLS.get(rule, {})


def _control_sort(c):
    """Order controls naturally: 1.2.5 < 1.2.7 < 10.2.1, A.5.17 < A.8.2 < A.8.20."""
    import re as _r
    return [int(p) if p.isdigit() else p for p in _r.split(r"[.\-]", c)]


def compliance_report(findings, objects, framework=None):
    """Findings grouped under the controls they bear on, per framework."""
    fws = [f for f in FRAMEWORKS if framework is None or framework == f]
    real = [f for f in findings if f.severity != INFO]
    lines = [f"**Compliance view** — {len(list(objects))} object(s) reviewed, "
             f"{len(real)} finding(s) mapped to {', '.join(fws)}."]
    if not real:
        lines.append("\nNo findings — nothing to report against these controls.")
    unmapped = sorted({f.rule for f in real if not controls_for(f.rule)})
    for fw in fws:
        by_control = {}
        for f in real:
            for c in controls_for(f.rule).get(fw, []):
                by_control.setdefault(c, []).append(f)
        if not by_control:
            continue
        lines += ["", f"### {fw}"]
        for c in sorted(by_control, key=_control_sort):
            fs = by_control[c]
            worst = min(fs, key=lambda x: _ORDER.get(x.severity, 9)).severity
            title = CONTROL_TITLES.get(c, "")
            lines.append(f"{_MARK.get(worst, '•')} **{c}** — {title}  ({len(fs)} finding(s))")
            seen = set()
            for f in sorted(fs, key=lambda x: _ORDER.get(x.severity, 9)):
                if f.title not in seen:
                    seen.add(f.title)
                    lines.append(f"     · {f.title}")
                if len(seen) >= 5:
                    more = len({x.title for x in fs}) - 5
                    if more > 0:
                        lines.append(f"     · … and {more} more")
                    break
    if unmapped:
        lines += ["", "Findings with no clean control mapping (reported, not mapped): "
                  + ", ".join(unmapped)]
    lines += ["", "---", "*An indicative mapping to help gather evidence — it is not an "
              "assessment. Your QSA or auditor's interpretation of each control "
              "decides. Each finding comes from the deterministic review; no model was "
              "involved.*"]
    return "\n".join(lines)


def counts(findings):
    c = {HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0}
    for f in findings:
        c[f.severity] = c.get(f.severity, 0) + 1
    return c


def report(findings, objects, limit=40):
    """A review a human can act on: what was checked, what was found, what it means."""
    objects = list(objects or [])
    policies = sum(1 for o in objects if is_firewall_policy(o))
    routes = sum(1 for o in objects if "static" in (o.kind or "").lower())
    # Say each thing ONCE. 120 copies of the same sentence is a linter dump: the reader
    # learns nothing after the first, and the findings that matter get buried under the
    # ones that don't.
    findings = group(findings, {"policies": policies, "routes": routes})
    c = counts(findings)
    real = [f for f in findings if f.severity != INFO]
    serious = [f for f in findings if f.severity in (HIGH, MEDIUM)]

    # Lead with the verdict: whether anything needs acting on is the first thing the
    # reader wants, and they should not have to infer it by counting bullets.
    if serious:
        verdict = (f"**{len(serious)} thing(s) worth acting on** — "
                   f"{c[HIGH]} high, {c[MEDIUM]} medium, {c[LOW]} low.")
    elif real:
        verdict = ("**Nothing serious found.** No shadowed rules, contradictions, "
                   "any/any accepts or dangling references. What follows is "
                   "observation, not a problem list.")
    else:
        verdict = ("**Clean.** No shadowed rules, contradictions, any/any accepts, "
                   "duplicates or dangling references — every check ran and found "
                   "nothing.")

    head = (f"**Configuration review** — {len(objects)} object(s) analysed "
            f"({policies} policies, {routes} static routes).\n\n{verdict}")

    if not findings:
        body = ""
    else:
        body = "\n\n" + "\n".join(f.line() for f in findings[:limit])
        if len(findings) > limit:
            body += f"\n\n… and {len(findings) - limit} more finding(s)."

    notes = ("\n\n---\n*How this was produced:* every finding is arithmetic over your "
             "parsed configuration — set containment, rule order, reference counting. No "
             "model was involved, so nothing here is guessed.\n"
             "*Known limits:* address groups are not expanded, so shadowing is detected "
             "only where match fields are literally equal or the earlier rule uses `all` "
             "— this misses some real shadowing but never invents any. Rule order follows "
             "the order in the file.")
    return head + body + notes
