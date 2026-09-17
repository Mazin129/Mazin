"""
workspace  —  the Cognitive Workspace (Global-Workspace blackboard).  [CORTEX-OS §2]

The single communication channel for the whole mind. Modules never call each other;
they PUBLISH typed messages ("cognits") here and SUBSCRIBE to the kinds they care
about. Each tick, the highest-salience mutually-linked coalition "ignites" and is
broadcast — that broadcast is what drives the response, and choosing only a small
coalition is exactly the sparse-activation mechanism (most cognits stay subliminal).

This is Phase-1 scaffolding: pure stdlib, in-RAM, deterministic, fully testable. It
does not change any existing Vio behaviour by itself — modules opt in.

Design notes:
  • Decoupling: publishers and subscribers never hold references to each other.
  • Provenance: every cognit records which cognits it came from -> full audit trail.
  • Decay: salience fades each tick; stale cognits are garbage-collected so working
    memory stays small automatically (no unbounded growth).
"""

from __future__ import annotations

import itertools
import time
from dataclasses import dataclass, field


# Cognit types used across the system (extensible — just strings).
PERCEPT = "percept"
GOAL = "goal"
HYPOTHESIS = "hypothesis"
EVIDENCE = "evidence"
PREDICTION = "prediction"
PLAN = "plan"
CRITIQUE = "critique"
ANSWER = "answer"
MEMORY_HIT = "memory_hit"

_ids = itertools.count(1)


@dataclass
class Cognit:
    """One unit of information on the blackboard."""
    type: str
    payload: object
    source: str = "?"
    salience: float = 0.5              # 0..1 — how much it deserves attention
    confidence: float = 0.5           # 0..1 — how much it can be trusted
    ttl: int = 8                      # ticks to live before garbage-collection
    provenance: list = field(default_factory=list)   # ids of cognits this came from
    links: list = field(default_factory=list)        # ids of related cognits
    id: int = field(default_factory=lambda: next(_ids))
    born_tick: int = 0
    tags: dict = field(default_factory=dict)

    def __repr__(self):
        p = self.payload if isinstance(self.payload, str) else type(self.payload).__name__
        p = (p[:40] + "…") if isinstance(p, str) and len(p) > 40 else p
        return (f"Cognit(#{self.id} {self.type} sal={self.salience:.2f} "
                f"conf={self.confidence:.2f} src={self.source} {p!r})")


class Workspace:
    """The blackboard: publish, subscribe, ignite (broadcast), decay."""

    def __init__(self, decay=0.85, min_salience=0.05, max_cognits=512):
        self.decay = decay                 # salience *= decay each tick
        self.min_salience = min_salience   # below this, a cognit evaporates
        self.max_cognits = max_cognits     # hard cap (oldest low-salience dropped)
        self.tick = 0
        self._cognits: dict[int, Cognit] = {}
        self._subs = []                    # (type_or_None, threshold, callback)
        self._broadcast_log = []           # last ignited coalition per tick (for tracing)

    # ---- publish -----------------------------------------------------------
    def publish(self, cognit: Cognit) -> Cognit:
        """Post a cognit. Notifies matching subscribers immediately (event-driven)."""
        cognit.born_tick = self.tick
        self._cognits[cognit.id] = cognit
        for ctype, threshold, cb in self._subs:
            if (ctype is None or ctype == cognit.type) and cognit.salience >= threshold:
                try:
                    cb(cognit)
                except Exception:
                    pass                    # a bad subscriber must never crash the mind
        if len(self._cognits) > self.max_cognits:
            self._evict()
        return cognit

    def post(self, type, payload, **kw) -> Cognit:
        """Convenience: build + publish a cognit in one call."""
        return self.publish(Cognit(type=type, payload=payload, **kw))

    # ---- subscribe ---------------------------------------------------------
    def subscribe(self, callback, type=None, threshold=0.0):
        """Register interest. callback(cognit) fires when a matching cognit is posted."""
        self._subs.append((type, threshold, callback))

    # ---- query -------------------------------------------------------------
    def query(self, type=None, min_salience=0.0, min_confidence=0.0):
        """Read cognits currently on the board (highest salience first)."""
        out = [c for c in self._cognits.values()
               if (type is None or c.type == type)
               and c.salience >= min_salience and c.confidence >= min_confidence]
        return sorted(out, key=lambda c: -c.salience)

    # ---- ignition (broadcast) ---------------------------------------------
    def ignite(self, k=5):
        """Select the winning coalition for this tick: the top-k salient cognits plus
        anything strongly linked to them. This is the 'conscious' broadcast that the
        response is built from. Returns the coalition (highest salience first)."""
        ranked = sorted(self._cognits.values(), key=lambda c: -c.salience)
        winners = ranked[:k]
        chosen = {c.id: c for c in winners}
        for c in winners:                          # pull in linked cognits (binding)
            for lid in c.links + c.provenance:
                if lid in self._cognits:
                    chosen[lid] = self._cognits[lid]
        coalition = sorted(chosen.values(), key=lambda c: -c.salience)
        self._broadcast_log.append((self.tick, [c.id for c in coalition]))
        return coalition

    # ---- time --------------------------------------------------------------
    def step(self):
        """Advance one tick: decay salience, garbage-collect faded/expired cognits."""
        self.tick += 1
        dead = []
        for cid, c in self._cognits.items():
            c.salience *= self.decay
            if (self.tick - c.born_tick) >= c.ttl or c.salience < self.min_salience:
                dead.append(cid)
        for cid in dead:
            del self._cognits[cid]
        return len(dead)

    # ---- internals ---------------------------------------------------------
    def _evict(self):
        """Over the cap: drop the lowest-salience cognits."""
        ranked = sorted(self._cognits.values(), key=lambda c: c.salience)
        for c in ranked[:len(self._cognits) - self.max_cognits]:
            del self._cognits[c.id]

    def snapshot(self):
        """A small dict describing current state — for tracing / the UI."""
        return {"tick": self.tick, "live": len(self._cognits),
                "by_type": {t: len(self.query(type=t))
                            for t in {c.type for c in self._cognits.values()}}}

    def __len__(self):
        return len(self._cognits)


if __name__ == "__main__":
    # tiny self-test / demo
    ws = Workspace()
    heard = []
    ws.subscribe(lambda c: heard.append(c), type=GOAL)
    ws.post(PERCEPT, "what is execute ping?", source="attention", salience=0.9)
    g = ws.post(GOAL, "explain: execute ping", source="executive", salience=0.8)
    ws.post(EVIDENCE, "execute ping tests connectivity", source="semantic",
            salience=0.7, provenance=[g.id])
    print("snapshot:", ws.snapshot())
    print("goal subscribers heard:", [c.payload for c in heard])
    print("ignition:", [f"#{c.id} {c.type}" for c in ws.ignite()])
    ws.step()
    print("after 1 tick:", ws.snapshot())
