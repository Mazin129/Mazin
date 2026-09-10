"""
quality — the answer-quality gate applied to EVERY response, after routing and the
critic. It enforces the promises that matter more than any single agent:

  1. NEVER mark an empty, too-short, or weak answer as verified.
  2. A factual / security answer with NO local evidence is never "verified" — it may
     still be shown (a general-knowledge LLM reply), but it wears an honest
     "unverified" tag instead of a green check.
  3. Attach CITATIONS when the answer was grounded on real passages or web sources.

This is deliberately small, pure, and side-effect free so it can wrap any result dict
from any path without knowing which agent produced it.
"""
from __future__ import annotations

import re

# phrases that mean "this isn't really an answer" — must never be verified
_WEAK = re.compile(
    r"i'?m not confident|treat it as a lead|didn'?t finish|couldn'?t finish|"
    r"i don'?t know( that)? yet|web search failed|couldn'?t (read|find|cover)|"
    r"no (open )?results|not enough|internet (research )?(is )?(currently )?off|"
    r"needs? (internet|web) access|didn'?t answer in time|timed out", re.I)

# a question is factual/security-ish if it leans on verifiable technical claims
_FACTUAL_SEC = re.compile(
    r"\b(mtls|bgp|ospf|eigrp|firewall|vpn|tls|ssl|iam|s3|vlan|nat|acl|cve|"
    r"vulnerab\w*|exploit|secure|security|encrypt\w*|kubernetes|k8s|istio|port|"
    r"protocol|cidr|subnet|route|routing|polic\w*|attack|breach|exfiltrat\w*|"
    r"ransomware|malware|rfc|dns|dhcp|ipsec|wireguard|conntrack|mtu|ecmp)\b", re.I)

# intrinsic paths are correct by construction — evidence/citation rules don't apply
_INTRINSIC = ("symbolic", "quadratic", "function plot", "exact tool", "clock",
              "skill:", "data analysis", "math", "greeting", "library summary",
              "sources", "gaps", "agents", "who-answers", "library-write",
              "memory-write", "skill-write")

# GROUNDED-by-construction paths: they answer from the library / knowledge graph /
# structured config even when they don't populate the evidence slot — so the
# "no local evidence → unverified" rule must not fire on them (the empty/weak rule still
# does). Only ungrounded LLM/reasoning replies to a factual/security question get demoted.
_GROUNDED = ("planning (grounded", "reasoning over knowledge", "world model",
             "reasoning (causal", "reasoning (deductive", "reasoning (rule",
             "synthesis", "analysis over your config", "episodic")


def is_factual_or_security(q: str) -> bool:
    return bool(_FACTUAL_SEC.search(q or ""))


def has_evidence(evidence: dict) -> bool:
    e = evidence or {}
    return bool(e.get("hits") or e.get("facts") or e.get("sources"))


def _is_intrinsic(how: str) -> bool:
    h = (how or "").lower()
    return any(k in h for k in _INTRINSIC)


def citations(evidence: dict) -> str:
    """A short, honest 'where this came from' footer, or '' if nothing to cite."""
    e = evidence or {}
    src = [s for s in (e.get("sources") or []) if s]
    if src:
        return "Sources:\n" + "\n".join(f"  • {s}" for s in src[:5])
    exc = [x for x in (e.get("excerpts") or []) if x and x.strip()]
    if exc:
        return "Grounded on:\n" + "\n".join(
            "  • " + x.strip().replace("\n", " ")[:130] + ("…" if len(x) > 130 else "")
            for x in exc[:3])
    return ""


def finalize(result: dict, evidence: dict, q: str) -> dict:
    """Apply the quality gate to one result dict. Returns a new dict — never mutates."""
    r = dict(result or {})
    ans = (r.get("answer") or "").strip()
    how = (r.get("how") or "")
    intrinsic = _is_intrinsic(how)

    # 1. empty / too-short / weak → cannot be verified
    if not ans or len(ans) < 2 or _WEAK.search(ans):
        r["verified"] = False

    # 2. factual/security claim with no local evidence and no web sources → unverified.
    #    (Intrinsic, grounded-by-construction, and web-research paths are exempt.)
    hl = how.lower()
    grounded = any(g in hl for g in _GROUNDED)
    if (not intrinsic and not grounded and "web research" not in hl
            and is_factual_or_security(q) and not has_evidence(evidence)):
        if r.get("verified"):
            r["verified"] = False
            if "unverified" not in how.lower():
                r["how"] = how + " · unverified (no local evidence)"

    # 3. citations for a verified, grounded answer (don't double-cite)
    if r.get("verified"):
        low = ans.lower()
        if "source" not in low and "grounded on" not in low and "sources i read" not in low:
            c = citations(evidence)
            if c:
                r["answer"] = ans + "\n\n" + c
    return r
