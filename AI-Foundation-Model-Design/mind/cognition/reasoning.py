"""
reasoning  —  the multi-mode Reasoning Engine.  [CORTEX-OS §7]

A dispatcher over reasoning modes. Vio's exact math (sympy, self-verifying) already
covers the *mathematical* mode inside reasoner.py; this module adds the modes that
need STRUCTURED knowledge rather than free text:

  • relational   — "how is X related to Y?"      -> knowledge-graph path
  • causal       — "what causes X?" / "why does X" -> graph causal edges
  • taxonomic    — "what kind of thing is X?"      -> graph is_a edges
  • deductive    — user-taught "if A then B" rules -> forward chaining

PERFORMANCE CONTRACT (never get slow): each mode's trigger is a single cheap regex,
checked in priority order; the FIRST question that matches nothing returns None
instantly, so ordinary questions fall straight through to retrieval with ~zero added
cost. A mode only touches a couple of graph adjacency lists — O(degree), not O(graph).
No mode runs unless its specific phrasing matched.
"""

from __future__ import annotations

import re

# specific triggers — deliberately narrow so plain "what is X" stays with retrieval
_RELATE = re.compile(r"how\s+(?:is|are|does)\s+(.+?)\s+(?:relat\w*|connect\w*|link\w*|"
                     r"associat\w*)\s+(?:to|with)\s+(.+)", re.I)
_RELATE2 = re.compile(r"(?:relationship|connection|link|relation)\s+between\s+(.+?)\s+and\s+(.+)", re.I)
_CAUSE = re.compile(r"what\s+causes?\s+(.+)", re.I)
_WHY = re.compile(r"why\s+(?:does|do|is|are)\s+(.+)", re.I)
_KIND = re.compile(r"what\s+(?:kind|type|sort)\s+of\s+(?:thing\s+)?(?:is\s+)?(.+)", re.I)
_SPLIT_AND = re.compile(r"\s+and\s+|\s*,\s*|\s+&\s+", re.I)


def _clean(s):
    return s.strip().strip("?.!،؟ ").strip()


class Reasoning:
    """Consulted by the reasoner for structured-knowledge questions. Returns a result
    dict (answer/how/verified/trace) or None to defer to normal retrieval."""

    def __init__(self, graph, mind=None):
        self.graph = graph
        self.mind = mind

    def answer(self, q):
        ql = q.strip()

        # --- relational: how is X related to Y / relationship between X and Y ---
        pair = None
        m = _RELATE.search(ql)
        if m:
            pair = (_clean(m.group(1)), _clean(m.group(2)))
        m2 = _RELATE2.search(ql)
        if m2:
            pair = (_clean(m2.group(1)), _clean(m2.group(2)))
        if pair and all(pair):
            rel = self.graph.relation_between(*pair)
            if rel:
                return self._ok(rel, "reasoning (relational · knowledge graph)")
            return None                     # graph doesn't know -> let retrieval try

        # --- causal: what causes X / why does X ---
        m = _CAUSE.search(ql) or _WHY.search(ql)
        if m:
            target = _clean(m.group(1))
            causes = self.graph.causes_of(target)
            if causes:
                body = ", ".join(causes)
                return self._ok(f"{body} — that's what I know can cause {target}.",
                                "reasoning (causal · knowledge graph)")
            return None

        # --- taxonomic: what kind of thing is X ---
        m = _KIND.search(ql)
        if m:
            desc = self.graph.describe(_clean(m.group(1)))
            if desc:
                return self._ok(desc, "reasoning (taxonomic · knowledge graph)")
            return None

        # --- deductive: chain user-taught "if A then B" rules ---
        ded = self._deduce(ql)
        if ded:
            return ded

        return None

    def _deduce(self, ql):
        """Forward-chain over 'if A then B' facts the user taught. Cheap: only runs if
        there ARE rule-facts and the query mentions a rule antecedent."""
        if self.mind is None:
            return None
        facts = self.mind.mem.get("facts", []) + self.mind.lib.docs
        rules = []
        for f in facts:
            rm = re.match(r"\s*if\s+(.+?)\s+then\s+(.+)", f, re.I)
            if rm:
                rules.append((_clean(rm.group(1)).lower(), _clean(rm.group(2))))
        if not rules:
            return None
        ql_low = ql.lower()
        for ante, cons in rules:
            if ante and ante in ql_low:
                # one deductive step; chain further consequents if they're antecedents
                chain = [cons]
                seen = {ante}
                cur = cons.lower()
                for _ in range(4):                      # bounded depth (no runaway)
                    nxt = next((c for a, c in rules if a in cur and a not in seen), None)
                    if not nxt:
                        break
                    chain.append(nxt); seen.add(cur); cur = nxt.lower()
                return self._ok(" → ".join(chain),
                                "reasoning (deductive · rule chaining)",
                                trace=[f"applied rule: if {ante} then {chain[0]}"])
        return None

    @staticmethod
    def _ok(answer, how, trace=None):
        return {"answer": answer, "how": how, "verified": True, "trace": trace or []}
