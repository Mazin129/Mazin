"""
planning  —  the Planning Engine.  [CORTEX-OS §8]

Turns a "how do I …" goal into an ordered, grounded plan: it decomposes the goal into
steps, then grounds each step in what Vio actually knows (retrieval), so the plan is
made of real learned material — never invented.

PERFORMANCE CONTRACT (never get slow): it triggers ONLY on explicit planning phrasings
("how do I …", "steps to …", "plan for …", "how to …"), so normal questions never enter
here. Decomposition is bounded (a few steps), and each step does at most one cheap
retrieval. If Vio has no relevant knowledge, it says so honestly rather than inventing a
procedure.
"""

from __future__ import annotations

import re

_TRIGGER = re.compile(r"^\s*(?:how\s+(?:do|would|can|should)\s+i|how\s+to|"
                      r"steps?\s+(?:to|for)|plan\s+(?:to|for)|guide\s+(?:to|for)|"
                      r"walk me through)\b(.*)", re.I)
MAX_STEPS = 6


def is_plan_request(q):
    return bool(_TRIGGER.match(q or ""))


class Planner:
    def __init__(self, mind):
        self.mind = mind

    def plan(self, q):
        m = _TRIGGER.match(q)
        if not m:
            return None
        goal = m.group(1).strip(" :?.")
        goal = re.sub(r"^(to|a|an|the)\s+", "", goal, flags=re.I).strip()
        if not goal:
            return None

        # 1) find the most relevant thing Vio knows about this goal
        hits = [d for d, s in self.mind.lib.search(goal, k=6) if s > 0.10]
        if not hits:
            return {"answer": f"I don't have anything learned about “{goal}” yet, so I "
                    "won't invent steps. Teach me a guide (📄 or a repo) and I'll build a "
                    "grounded plan.", "how": "planning (no knowledge)",
                    "verified": False, "trace": []}

        # 2) pull ordered, actionable sentences from what was retrieved (grounded steps)
        steps = self._extract_steps(hits)
        if not steps:
            # fall back to a grounded summary if no imperative steps were found
            syn = self.mind.thinker.synthesize(goal, hits, [])
            if syn:
                return {"answer": f"Here's what I know that bears on “{goal}”:\n{syn}",
                        "how": "planning (grounded summary)", "verified": True, "trace": []}
            return None

        lines = [f"Plan for “{goal}” (from what you taught me):"]
        for i, s in enumerate(steps[:MAX_STEPS], 1):
            lines.append(f"  {i}. {s}")
        return {"answer": "\n".join(lines), "how": "planning (grounded steps)",
                "verified": True, "trace": [f"decomposed into {len(steps[:MAX_STEPS])} steps"]}

    @staticmethod
    def _extract_steps(passages):
        """Grounded step extraction: sentences that read like actions (imperative /
        numbered / configure-set-enable…), de-duplicated, in document order."""
        action = re.compile(r"^\s*(?:\d+[.)]\s*)?(?:step\s*\d*[:.]?\s*)?"
                            r"(configure|set|enable|disable|create|add|connect|assign|"
                            r"install|run|execute|open|select|click|choose|define|apply|"
                            r"go to|navigate|type|enter|first|then|next|finally)\b", re.I)
        steps, seen = [], set()
        for p in passages:
            for s in re.split(r"(?<=[.!?؟])\s+|\n+", p):
                s = s.strip()
                if len(s.split()) < 3:
                    continue
                if action.match(s):
                    key = s.lower()[:50]
                    if key not in seen:
                        seen.add(key)
                        steps.append(s if len(s) < 160 else s[:157] + "…")
        return steps
