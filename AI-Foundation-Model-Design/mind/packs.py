"""
packs  —  portable knowledge packs.  [CORTEX-OS §19: shareable specialists + local sync]

A "pack" is Vio's knowledge for a topic bundled into one plain-JSON file you can share
or move between your own machines — the local-first, no-cloud version of "sync a
specialist". A pack carries library passages, knowledge-graph edges, skills, and
personal facts; importing MERGES it into another Vio (de-duplicated) and rebuilds the
indexes once. Data only — never code — so importing a pack is as safe as teaching text.

    pack = export_pack(mind, domain="networking")   # {version, domain, docs, edges, …}
    stats = import_pack(mind, pack)                  # merges, returns counts

Export can be scoped to a specialist domain (only passages whose words match that
expert's keywords) or "all" for a full portable brain snapshot.
"""

from __future__ import annotations

import re

PACK_VERSION = 1


def _domain_keywords(mind, domain):
    for e in mind.cortex.experts:
        if e.name == domain:
            return set(e.keywords)
    return set()


def _matches(text, kws):
    """Whole-word match (so 'port' doesn't fire inside 'support')."""
    words = set(re.findall(r"[a-z0-9]+", text.lower()))
    return bool(words & kws)


def export_pack(mind, domain=None):
    """Bundle Vio's knowledge (optionally just one domain) into a portable dict."""
    docs = list(mind.lib.docs)
    edges = {k: list(v) for k, v in mind.graph.adj.items()}
    facts = list(mind.mem.get("facts", []))
    skills = mind.skills.list()

    if domain and domain != "all":
        kws = _domain_keywords(mind, domain)
        if kws:
            docs = [d for d in docs if _matches(d, kws)]
            edges = {k: v for k, v in edges.items()
                     if _matches(k + " " + " ".join(t for _, t in v), kws)}
            facts = [f for f in facts if _matches(f, kws)]
    return {"version": PACK_VERSION, "domain": domain or "all",
            "docs": docs, "edges": edges, "facts": facts, "skills": skills}


def import_pack(mind, pack):
    """Merge a pack into this Vio (de-duplicated). Returns what was added."""
    if not isinstance(pack, dict) or pack.get("version") != PACK_VERSION:
        raise ValueError("This isn't a Vio knowledge pack (or it's a newer version).")

    added = {"docs": 0, "edges": 0, "facts": 0, "skills": 0}

    have = {re.sub(r'\s+', ' ', d.strip().lower()) for d in mind.lib.docs}
    new_docs = [d for d in pack.get("docs", [])
                if re.sub(r'\s+', ' ', d.strip().lower()) not in have]
    if new_docs:
        mind.lib.add_many(new_docs)
        added["docs"] = len(new_docs)

    for subj, elist in (pack.get("edges") or {}).items():
        for rel, obj in elist:
            if mind.graph.add_edge(subj, rel, obj):
                added["edges"] += 1
    if added["edges"]:
        mind.graph._save()

    for f in pack.get("facts", []):
        if f not in mind.mem["facts"]:
            mind.mem["facts"].append(f)
            added["facts"] += 1
    if added["facts"]:
        mind._save()

    for s in pack.get("skills", []):
        ok, _ = mind.skills.add(s.get("name", ""), s.get("trigger", ""), s.get("reply", ""))
        if ok:
            added["skills"] += 1

    mind._retrain()                       # one rebuild after all merges
    return added
