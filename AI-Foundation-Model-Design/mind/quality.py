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


# ---------------------------------------------------------------------------- #
# FRAGMENT GATE — the general form of "it answered with shredded config lines".
#
# Lexical retrieval and synthesis can assemble an "answer" out of stray device-config
# directives and half-sentences lifted from a manual ("config router static." /
# "Per Route" / "Confirm the policy:"). It reads as an answer, gets a ✓ because the
# path is grounded-by-construction, and is worthless. This catches that SHAPE — for
# every question, on every path — instead of patching one question at a time.
# ---------------------------------------------------------------------------- #

# a device-config directive line: `config router static`, `set gateway 1.1.1.1`, `end`.
# \b after the keyword keeps prose like "Configure a policy…" out of it.
_CFG_STUB = re.compile(r"^\s*(config|edit|set|unset|next|end|append|select)\b", re.I)
# a bare heading / dangling label: "Per Route", "Confirm the policy:", "Example 1"
_LABEL_STUB = re.compile(r"^[\w ()/-]{1,40}:?$")
# deterministic paths whose short output is exact by construction — never fragments
_EXACT = ("exact listing", "exact count", "library-write", "memory-write", "skill-write",
          "correction-write", "feedback", "calibration", "consolidation")


def _units(ans: str):
    """Split an answer into its content units (lines and sentences), minus footers."""
    body = re.split(r"\n\s*(?:Grounded on|Sources|Sources I read)\s*:", ans or "")[0]
    parts = re.split(r"(?:\n+|(?<=[.!?:])\s+)", body)
    out = []
    for p in parts:
        p = p.strip().lstrip("•-*·").strip()
        if p:
            out.append(p)
    return out


def looks_fragmentary(ans: str) -> bool:
    """True when the 'answer' is a pile of config directives / dangling labels rather
    than something that actually answers anything."""
    units = _units(ans)
    if len(units) < 2:              # a single real sentence is an answer, not a pile
        return False
    stubs = sum(1 for u in units
                if _CFG_STUB.match(u) or (_LABEL_STUB.match(u) and len(u.split()) <= 4))
    if stubs / len(units) >= 0.5:
        return True
    # every unit is a scrap — no unit long enough to carry a claim
    return all(len(u.split()) < 6 for u in units)


def is_stub_passage(text: str) -> bool:
    """True for a retrieved passage that carries no information on its own: a lone
    config directive (`config router static.`) or a dangling label (`Per Route`,
    `Confirm the policy:`). These are ingest noise — a heading or a stanza opener that
    got chunked away from its body. Grounding an answer on them produces text that
    looks sourced and says nothing, so they are excluded from retrieval grounding.

    A MULTI-LINE config stanza is NOT a stub — it has `set` lines and real content."""
    t = (text or "").strip()
    if not t or "\n" in t:                     # multi-line = a real stanza / paragraph
        return False
    words = t.split()
    if len(words) > 8:                         # long enough to make a claim
        return False
    if _CFG_STUB.match(t):                     # `config router static.` / `end`
        return True
    return bool(_LABEL_STUB.match(t)) and len(words) <= 4


def fragment_reply(ans: str, q: str) -> str:
    """An honest replacement that shows the scraps as leads, never as the answer."""
    leads = [u for u in _units(ans)][:6]
    lead_txt = ("\n".join(f"  • {l}" for l in leads)) if leads else "  (nothing usable)"
    return (
        "I don't have a real answer to this. What I retrieved is only fragments — "
        "device-config lines and stray sentences from documentation — not anything "
        "that answers the question, so I won't dress it up as one.\n\n"
        f"The fragments (leads only, not an answer):\n{lead_txt}\n\n"
        "To answer it properly I need one of:\n"
        "  • the real device configuration — upload 📄 the .conf backup or the output of "
        "`show full-configuration`, and I'll list the actual objects exactly; or\n"
        "  • the local reasoning model running — start it with `ollama serve`, then I can "
        "reason over the documentation I already have.\n\n"
        "Run  python doctor.py  to see which of the two is missing."
    )


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
    exc = [x for x in (e.get("excerpts") or [])
           if x and x.strip() and not is_stub_passage(x)]
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

    # 1b. FRAGMENT GATE — a pile of config directives or dangling labels is not an
    #     answer, whatever path produced it. Replace it rather than demote it: leaving
    #     the scraps as the answer body is what made Vio look like it had answered.
    if ans and not any(k in how.lower() for k in _EXACT) and looks_fragmentary(ans):
        return {**r, "answer": fragment_reply(ans, q), "verified": False,
                "confidence": min(float(r.get("confidence") or 0.1), 0.1),
                "how": "fragments (not an answer)",
                "trace": list(r.get("trace") or [])
                + [f"quality gate: '{how or 'unknown path'}' returned "
                   f"{len(_units(ans))} fragment(s), not an answer"]}

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
