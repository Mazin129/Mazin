"""
understand — turn a question into a STRUCTURED INTENT before anything tries to answer it.

Vio printed "Understanding your question…" while doing nothing of the kind: it went
straight to keyword matching. That is why "show static route on SA-OCC firewall" came
back as manual prose — nothing ever established that the user wanted

    operation = list
    object    = route
    device    = SA-OCC
    evidence  = a device configuration (documentation CANNOT answer this)

Once that is explicit, three things follow that guessing could never give:

  • ROUTING is a lookup, not a keyword race — a config question goes to the config
    engine, a concept question to retrieval/reasoning.
  • The EVIDENCE REQUIREMENT is known up front, so Vio can say "this needs your config
    and I don't have it" instead of answering from whatever text happened to match.
  • The user can SEE the interpretation and correct it when it's wrong.

Deterministic and dependency-free: no model call, microseconds, same answer every time.
A multi-part question yields one Intent per part, so a four-question paste is not
flattened into one bag of keywords.
"""
from __future__ import annotations

import re

# ---- operations ------------------------------------------------------------ #
# order matters: the most specific pattern wins.
_OPS = [
    ("count",      r"\bhow many\b|\bcount\b|\bnumber of\b|\btotal\b"),
    ("list",       r"\b(show|list|display|give me|what are|print|dump)\b"),
    ("compare",    r"\b(difference|differences|compare|versus|vs\.?|better than)\b"),
    ("troubleshoot", r"\b(why (is|are|does|do|would|did)|not working|broken|fail\w*|"
                     r"flap\w*|drop\w*|timeout|timing out|can'?t (reach|connect|ping)|"
                     r"unreachable|troubleshoot|debug)\b"),
    ("howto",      r"\bhow (do|can|would|should) (i|we|you)\b|\bhow to\b|\bsteps to\b"),
    ("explain",    r"\b(explain|describe|tell me about|walk me through|how does|"
                   r"how do(?!\s+i)|what happens)\b"),
    ("define",     r"^\s*(what|which) (is|are|does)\b|\bwhat'?s\b|\bdefine\b|"
                   r"\bmeaning of\b"),
    ("assess",     r"\b(is it safe|secure|risk|vulnerab\w*|audit|review|harden|"
                   r"best practice|should i)\b"),
]

# ---- configuration object kinds -------------------------------------------- #
# what the user is asking ABOUT, when it is a device object.
_OBJECTS = [
    ("route",     r"\b(static\s+routes?|routes?|routing\s+table|default\s+gateway)\b"),
    ("policy",    r"\b(polic(?:y|ies)|rules?|firewall\s+rules?|acls?)\b"),
    ("address",   r"\b(address\s+objects?|addrgrp|address\s+groups?|subnets?\s+objects?)\b"),
    ("interface", r"\b(interfaces?|ports?|vlans?|sub-?interfaces?)\b"),
    ("service",   r"\b(services?|service\s+objects?|custom\s+services?)\b"),
    ("vpn",       r"\b(vpn|ipsec|tunnels?|phase\s*[12])\b"),
    ("vip",       r"\b(vips?|virtual\s+ips?|dnat|port\s+forward\w*)\b"),
    ("user",      r"\b(users?|admins?|accounts?|local\s+users?)\b"),
    ("zone",      r"\b(zones?|trust\s+boundar\w+)\b"),
]

# ---- concept topics (not device objects) ----------------------------------- #
_CONCEPTS = (
    "bgp", "ospf", "eigrp", "rip", "isis", "mpls", "vxlan", "stp", "lacp",
    "tls", "ssl", "mtls", "ipsec", "wireguard", "kerberos", "oauth", "saml",
    "dns", "dhcp", "nat", "cgnat", "qos", "mtu", "tcp", "udp", "icmp", "quic",
    "kubernetes", "k8s", "istio", "envoy", "iam", "s3", "zero trust", "mitre",
    "ransomware", "phishing", "ddos", "siem", "soar", "edr", "ids", "ips",
    "vlan", "subnet", "cidr", "vpn", "firewall", "routing", "acl", "vrf",
)

# ---- device naming --------------------------------------------------------- #
# "on SA-OCC firewall", "on the FGT-DC1", "for SA-OCC-FW01"
_DEVICE = re.compile(
    r"\b(?:on|for|from|in|of)\s+(?:the\s+)?"
    r"([A-Z][A-Z0-9]*(?:[-_][A-Z0-9]+)+|[A-Z]{2,}\d*)"
    r"(?:\s+(?:firewall|fw|router|switch|device|gateway|appliance))?", re.I)
_VENDOR = re.compile(r"\b(fortigate|forti(?:os|gate)?|palo\s*alto|panos|cisco|asa|"
                     r"juniper|junos|checkpoint|sophos|mikrotik|pfsense)\b", re.I)

# a filter/condition turns an exact listing into a search ("routes THAT point to WAN")
_FILTER = re.compile(r"\b(that|which|with|without|pointing|matching|using|where|"
                     r"containing|having|via|through|to the internet)\b", re.I)

_SPLIT = re.compile(r"[\n?]+|(?<=[a-z])\s*;\s*")


class Intent:
    """One structured reading of one question."""

    __slots__ = ("text", "operation", "object", "concept", "device", "vendor",
                 "filtered", "evidence", "agent")

    def __init__(self, text):
        self.text = text
        self.operation = "explain"
        self.object = None         # a device-config object kind, if any
        self.concept = None        # a protocol/technology topic, if any
        self.device = None
        self.vendor = None
        self.filtered = False
        self.evidence = "knowledge"   # knowledge | config | reasoning | live
        self.agent = "knowledge"

    # -- rendering ----------------------------------------------------------- #
    def summary(self):
        """One line a human can check — this is what 'Understanding…' should show."""
        bits = [f"{self.operation}"]
        if self.object:
            bits.append(f"{self.object} objects")
        elif self.concept:
            bits.append(self.concept.upper())
        if self.device:
            bits.append(f"on {self.device}")
        if self.vendor:
            bits.append(f"({self.vendor})")
        if self.filtered:
            bits.append("— filtered")
        return " ".join(bits) + f"  ·  needs: {self.needs()}"

    def needs(self):
        return {"config": "your device configuration",
                "knowledge": "documentation / knowledge",
                "reasoning": "reasoning",
                "live": "a live data feed"}[self.evidence]

    def as_dict(self):
        return {"text": self.text, "operation": self.operation, "object": self.object,
                "concept": self.concept, "device": self.device, "vendor": self.vendor,
                "filtered": self.filtered, "evidence": self.evidence, "agent": self.agent}


def _first(patterns, low):
    for name, pat in patterns:
        if re.search(pat, low, re.I):
            return name
    return None


def parse_one(q: str) -> Intent:
    """Parse ONE question into a structured intent."""
    it = Intent((q or "").strip())
    low = it.text.lower()
    if not low:
        return it

    it.operation = _first(_OPS, low) or "explain"
    it.object = _first(_OBJECTS, low)
    it.concept = next((c for c in _CONCEPTS if re.search(rf"\b{re.escape(c)}\b", low)), None)
    it.filtered = bool(_FILTER.search(low))

    mv = _VENDOR.search(it.text)
    if mv:
        it.vendor = mv.group(1)

    md = _DEVICE.search(it.text)
    if md:
        cand = md.group(1)
        # "on FortiGate" names a vendor, not a device; "on SA-OCC" names a device.
        if not _VENDOR.fullmatch(cand) and cand.lower() not in ("the", "a", "an"):
            it.device = cand

    # CONCEPT vs DEVICE OBJECT: "what is a VLAN" is a definition, not a request for
    # this box's interface table — the same word means both, and only the operation
    # separates them. A definitional/conceptual question never needs a config.
    if it.operation in ("define", "explain", "compare", "howto") and not it.device:
        it.object = None

    # ---- evidence requirement: the decision everything else hangs on -------- #
    # Asking to list or count device objects can ONLY be answered from a config.
    # Documentation describing those objects is not an answer, and saying so up
    # front is what stops manual prose being served as device data.
    if it.object and it.operation in ("list", "count"):
        it.evidence = "config"
    elif it.object and (it.device or it.vendor) and it.operation in ("assess", "troubleshoot"):
        it.evidence = "config"
    elif it.operation in ("troubleshoot", "howto", "assess", "compare"):
        it.evidence = "reasoning"
    else:
        it.evidence = "knowledge"

    # ---- which agent should own this --------------------------------------- #
    if it.evidence == "config":
        it.agent = "network_engineering"
    elif it.concept or it.object:
        it.agent = "network_engineering" if it.operation in (
            "troubleshoot", "assess", "compare", "howto") else "knowledge"
    else:
        it.agent = "knowledge"
    return it


def split_questions(q: str):
    """Split a pasted blob into separate questions. Four questions in one message
    used to be flattened into one bag of keywords, which is how a routes question
    and a policies question answered each other."""
    parts = [p.strip(" .\t") for p in _SPLIT.split(q or "")]
    return [p for p in parts if len(p.split()) >= 2] or [(q or "").strip()]


def parse(q: str):
    """Parse a (possibly multi-part) message into one Intent per question."""
    return [parse_one(p) for p in split_questions(q)]


def explain(q: str) -> str:
    """A human-readable report of how Vio read the question — the `understand:` command."""
    its = parse(q)
    if len(its) == 1:
        it = its[0]
        lines = [f"How I read this: **{it.summary()}**", ""]
    else:
        lines = [f"I read this as **{len(its)} separate questions**:", ""]
        for i, it in enumerate(its, 1):
            lines.append(f"  {i}. “{it.text}” → {it.summary()}")
        lines.append("")
    it = its[0]
    lines.append(f"  operation : {it.operation}")
    lines.append(f"  about     : {it.object or it.concept or '(not identified)'}")
    lines.append(f"  device    : {it.device or '(none named)'}")
    lines.append(f"  vendor    : {it.vendor or '(none named)'}")
    lines.append(f"  evidence  : {it.needs()}")
    lines.append(f"  agent     : {it.agent}")
    if it.evidence == "config":
        lines.append("")
        lines.append("  This question can ONLY be answered from a device configuration. "
                     "Documentation about the feature is not an answer to it.")
    return "\n".join(lines)
