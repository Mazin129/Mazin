"""
world_model  —  the World Model & internal simulation.  [CORTEX-OS §9]

"Think before you speak." The World Model represents cause→effect and can roll an
event FORWARD to predict its downstream consequences, or reason COUNTERFACTUALLY about
what would not happen without it — internally, before answering.

Practical instantiation (honest, laptop-fast): the World Model runs over the causal
edges Vio has actually learned (the Phase-3 Knowledge Graph's `causes` relations).
Simulation is a bounded forward walk of that causal DAG — O(reachable effects), depth-
capped — not a neural rollout. The predictive-coding prototype
(`prototype/predictive_coding_brain.py`) remains the substrate for *perceptual*
prediction in a later phase; here the World Model reasons over explicit causal
structure, which is what a knowledge assistant needs and can do reliably today.

It never invents causality: if Vio hasn't learned that X causes anything, the model
says the future is unknown rather than guessing.

PERFORMANCE CONTRACT: only the "what happens if / what if" trigger enters here; the
walk is depth-capped (default 4) and breadth-capped, so it stays O(small).
"""

from __future__ import annotations

import re

from memory.graph import _norm as _gnorm

MAX_DEPTH = 4
MAX_BRANCH = 6

_PREDICT = re.compile(r"^\s*(?:what\s+(?:happens?|results?|follows?)\s+(?:if|when)|"
                      r"what\s+if|what\s+would\s+happen\s+if|predict|"
                      r"what(?:'s| is)\s+the\s+(?:effect|consequence|result|impact)\s+of|"
                      r"what\s+does\s+(.+?)\s+lead\s+to)\b(.*)", re.I)
_COUNTERFACT = re.compile(r"what\s+if\s+(.+?)\s+(?:did\s*n['o]?t|does\s*n['o]?t|"
                          r"had\s*n['o]?t|were\s+not|was\s+not|never)\b", re.I)


def _clean(s):
    s = s.strip().strip("?.!،؟ ").strip()
    s = re.sub(r"^(the|a|an|there\s+is|there\s+are)\s+", "", s, flags=re.I)
    return s


class WorldModel:
    def __init__(self, graph):
        self.graph = graph

    def _resolve(self, event):
        """Map an event phrase to a known graph concept. Exact match first, else the
        graph node whose words are contained in the phrase (e.g. 'congestion occurs'
        -> 'congestion'). Returns the node or None if the model knows no such cause."""
        node = _gnorm(_clean(event))
        if node in self.graph.adj:
            return node
        words = set(node.split())
        best = None
        for cand in self.graph.adj:                      # small graph -> cheap scan
            cw = set(cand.split())
            if cw and cw <= words:                       # candidate's words all in phrase
                if best is None or len(cand) > len(best):
                    best = cand
        return best

    # ---- core: roll an event forward over learned causal edges ------------
    def simulate(self, event, depth=MAX_DEPTH):
        """Predicted chain(s) of downstream effects of `event`. Returns a list of
        paths, each a list of concepts [event, effect1, effect2, …]."""
        node = self._resolve(event)
        if not node:
            return []
        paths = []
        self._walk(node, [node], set(), paths, depth)
        return [p for p in paths if len(p) > 1]

    def _walk(self, node, path, seen, out, depth):
        if depth <= 0 or node in seen:
            if len(path) > 1:
                out.append(list(path))
            return
        seen = seen | {node}
        effects = [tgt for rel, tgt in self.graph.neighbors(node) if rel == "causes"][:MAX_BRANCH]
        if not effects:
            out.append(list(path))                       # a leaf effect — record the chain
            return
        for e in effects:
            self._walk(_gnorm(e), path + [e], seen, out, depth - 1)

    # ---- answer a prediction / counterfactual question --------------------
    def answer(self, q):
        # counterfactual first ("what if X didn't happen")
        cf = _COUNTERFACT.search(q)
        if cf:
            event = _clean(cf.group(1))
            paths = self.simulate(event)
            if not paths:
                return None                              # no causal knowledge -> defer
            effects = sorted({p[-1] for p in paths if len(p) > 1})
            chain = "; ".join(" → ".join(p) for p in paths[:3])
            return self._ok(
                f"Counterfactually, without “{event}” I'd expect these not to follow: "
                f"{', '.join(effects)}.\nSimulated causal chain(s): {chain}",
                "world model (counterfactual simulation)", paths)

        m = _PREDICT.match(q)
        if not m:
            return None
        event = _clean((m.group(1) or "") + " " + (m.group(2) or ""))
        if not event:
            return None
        paths = self.simulate(event)
        if not paths:
            return None                                  # unknown future -> let retrieval try
        endpoints = sorted({p[-1] for p in paths if len(p) > 1})
        chain = "; ".join(" → ".join(p) for p in paths[:3])
        return self._ok(
            f"If “{event}” happens, I predict: {', '.join(endpoints)}.\n"
            f"Simulated causal chain(s): {chain}",
            "world model (forward simulation)", paths)

    # ---- simulation-agreement signal (for Confidence §10 / Critic §11) ----
    def agreement(self, event, claimed_effect):
        """Does the causal model corroborate that `event` leads to `claimed_effect`?
        Returns 0..1 — used as the simulation_agreement confidence input."""
        eff = (claimed_effect or "").lower()
        for p in self.simulate(event):
            if any(step.lower() in eff or eff in step.lower() for step in p[1:]):
                return 1.0 / (p.index(next(s for s in p[1:] if s.lower() in eff
                                           or eff in s.lower())))
        return 0.0

    @staticmethod
    def _ok(answer, how, paths):
        # confidence reflects how far the simulation reached (a longer verified chain
        # is stronger evidence the model actually knows the dynamics)
        depth = max((len(p) for p in paths), default=1)
        return {"answer": answer, "how": how, "verified": True,
                "confidence": round(min(0.85, 0.6 + 0.08 * (depth - 1)), 2),
                "trace": [f"forward-simulated {len(paths)} causal path(s), depth {depth}"]}
