"""
executive  —  the Executive Controller.  [CORTEX-OS §5.1]

The prefrontal cortex of the system: the two-clock router.

  System-1 (fast clock)  — answers whose correctness is intrinsic: machine-verified
      math/tools, deterministic writes/summaries, user reflex skills, creative
      generation (explicitly unverified). No second-guessing needed → no critic run.
      This is where MOST messages end, which is the energy story: the expensive
      deliberation machinery simply never wakes.

  System-2 (slow clock)  — knowledge answers (retrieval/synthesis) and unknowns.
      These get the full Phase-2 deliberation tail: Confidence Engine scoring, then
      the Self-Critic checklist (conflict check → re-search → honest downgrade).

Every interaction is traced through the Cognitive Workspace as cognits
(percept → answer, with provenance), so the whole decision is replayable.

Phase-2 honesty note: routing is decided from which path the reasoner actually took
(its `how`), not by predicting difficulty up front — prediction-based dispatch to
specialist modules arrives with the specialist cortex (Phase 5). What IS real now:
the critic and confidence machinery only ever runs for System-2 answers.
"""

from __future__ import annotations

from kernel.workspace import Workspace, PERCEPT, ANSWER
from cognition.confidence import score as confidence_score, VERIFIED_EXACT, DETERMINISTIC
from cognition.critic import review as critic_review

# paths whose correctness is intrinsic — the fast clock, no critique needed
_SYSTEM1 = VERIFIED_EXACT | DETERMINISTIC | {"generation", "github"}


class Executive:
    def __init__(self, mind):
        self.mind = mind

    def process(self, q):
        """Run one interaction through the two-clock pipeline."""
        ws = self.mind.ws
        percept = ws.post(PERCEPT, q, source="user", salience=0.9)

        result = self.mind._ask_core(q)
        evidence = getattr(self.mind, "_last_evidence", {}) or {}
        conf = confidence_score(result, evidence)

        how = result.get("how", "")
        system = 1 if (how in _SYSTEM1 or how.startswith("skill:")
                       or how.startswith("generation")
                       or how.startswith("reasoning (")    # structured graph/rule inference
                       or how.startswith("planning (")
                       or how.startswith("world model (")) else 2

        if system == 2:
            result, conf = critic_review(q, result, conf, self.mind)

        result = dict(result)
        result["confidence"] = round(conf, 2)
        result["system"] = system

        ws.post(ANSWER, (result.get("answer") or "")[:160], source="executive",
                salience=0.8, confidence=conf, provenance=[percept.id])
        ws.step()                       # decay + GC the workspace each interaction
        return result
