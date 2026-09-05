"""
executive  —  the Executive Controller.  [CORTEX-OS §5.1]

The prefrontal cortex of the system: the two-clock router.

  System-1 (fast clock)  — answers whose correctness is intrinsic: machine-verified
      math/tools, deterministic writes/summaries, user reflex skills, creative
      generation (explicitly unverified). No second-guessing needed → no critic run.
      This is where MOST messages end, which is the energy story: the expensive
      deliberation machinery simply never wakes.

  System-2 (slow clock)  — knowledge answers (retrieval/synthesis), LLM-composed
      answers, unverified results, and empty-evidence cases. These get the full
      deliberation tail: Confidence Engine scoring, then the Self-Critic checklist
      (conflict check → re-search → honest downgrade).

Every interaction is traced through the Cognitive Workspace as cognits
(percept → answer, with provenance), so the whole decision is replayable.

Phase-2 honesty note: routing is decided from which path the reasoner actually took
(its `how`), not by predicting difficulty up front. LLM paths and empty evidence
ALWAYS take the slow clock — fluent text is not intrinsic correctness.
"""

from __future__ import annotations

from kernel.workspace import PERCEPT, ANSWER
from cognition.confidence import score as confidence_score, VERIFIED_EXACT, DETERMINISTIC
from cognition.critic import review as critic_review

# paths whose correctness is intrinsic — the fast clock, no critique needed
_SYSTEM1 = VERIFIED_EXACT | DETERMINISTIC | {"generation", "github"}


def _is_llm_how(how: str) -> bool:
    return "llm" in (how or "").lower()


def _empty_evidence(evidence: dict) -> bool:
    """True when retrieval ran and found nothing. None hits = evidence not stashed."""
    if not evidence:
        return False
    hits = evidence.get("hits")
    if hits is None:
        return False
    facts = int(evidence.get("facts") or 0)
    return int(hits) == 0 and facts == 0


def choose_system(how: str, result: dict, evidence: dict) -> int:
    """Decide System-1 vs System-2.

    Fast clock only for intrinsically correct / intentional-unverified paths.
    Any LLM composition, unverified knowledge answer, or empty retrieval evidence
    takes the slow clock so the critic can escalate or rewrite.
    """
    how = how or ""
    verified = bool(result.get("verified"))

    # Force System-2: LLM, empty library support, or unverified non-intrinsic answers
    if _is_llm_how(how) or _empty_evidence(evidence):
        return 2
    if not verified and how not in _SYSTEM1 and not how.startswith("skill:"):
        # generation/github are in _SYSTEM1 (intentional creative / external)
        if not (how.startswith("generation") or how.startswith("github")):
            return 2

    # Intrinsic System-1
    if how in _SYSTEM1 or how.startswith("skill:") or how.startswith("generation"):
        return 1
    # Structured graph/rule inference — NOT LLM — only when verified
    if how.startswith("reasoning (") and not _is_llm_how(how) and verified:
        return 1
    if how.startswith("planning (") and verified:
        return 1
    if how.startswith("world model (") and verified:
        return 1
    if how.startswith("data analysis (") and verified:
        return 1
    return 2


class Executive:
    def __init__(self, mind):
        self.mind = mind

    def process(self, q):
        """Run one interaction through the two-clock pipeline."""
        ws = self.mind.ws
        percept = ws.post(PERCEPT, q, source="user", salience=0.9)

        result = self.mind._route(q)          # Stage 2: master is the live router
        evidence = getattr(self.mind, "_last_evidence", {}) or {}
        conf = confidence_score(result, evidence)

        how = result.get("how", "")
        system = choose_system(how, result, evidence)

        if system == 2:
            result, conf = critic_review(q, result, conf, self.mind)

        # Phase-6: apply the calibration correction learned from feedback (§10), so the
        # stated confidence self-tunes toward how often Vio is actually right.
        scalar = getattr(self.mind, "calibration", None)
        if scalar is not None:
            conf = max(0.02, min(0.99, conf * scalar.scalar))

        result = dict(result)
        result["confidence"] = round(conf, 2)
        result["system"] = system

        ws.post(ANSWER, (result.get("answer") or "")[:160], source="executive",
                salience=0.8, confidence=conf, provenance=[percept.id])
        ws.step()                       # decay + GC the workspace each interaction
        return result
