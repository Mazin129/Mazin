"""
confidence  —  the Confidence Engine.  [CORTEX-OS §10]

Every answer gets a calibrated 0..1 confidence, fused from real signals — not a
softmax guess:

    knowledge quality   how strong was the best retrieval hit?
    evidence support    how many independent passages / personal facts back it?
    reasoning quality   did a verification pass actually run (sympy substitute-back,
                        deterministic tool), or is this composed text?

Phase-2 scope, stated honestly: the weights below are hand-set priors chosen so the
number is *meaningful* (0.95 ⇒ machine-checked; 0.6 ⇒ well-grounded; 0.1 ⇒ Vio is
telling you it doesn't know). Confidences are logged with each episode (tags), so a
later phase can re-fit the weights against real outcomes (Brier-score calibration,
§10) instead of priors. simulation_agreement joins in Phase 4 when the World Model
exists — it is NOT faked here.
"""

from __future__ import annotations

# answers produced by a machine-checked computation (sympy verifies its own roots,
# unit tables are exact, the clock is the clock)
VERIFIED_EXACT = {
    "symbolic reasoning (sympy)", "symbolic reasoning (system)", "exact tool",
    "function plot", "quadratic analysis", "clock",
}

# deterministic acts — writes, summaries, recall of Vio's own stores
DETERMINISTIC = {
    "library-write", "memory-write", "skill-write", "learned from GitHub",
    "library summary", "episodic recall", "episodic timeline", "training",
    "identity", "capabilities", "greeting",
}

# grounded-retrieval paths — confidence scales with the evidence behind them
RETRIEVAL = {
    "reasoning over knowledge (synthesis)", "retrieval",
    "self-directed research (synthesis)", "self-directed research (retrieval)",
}


def score(result, evidence=None):
    """Fuse the available signals into one confidence for this result.

    result   — the answer dict ({answer, how, verified, trace})
    evidence — retrieval metadata the reasoner stashed: {top, hits, facts}
    """
    how = result.get("how", "")
    verified = bool(result.get("verified"))
    ev = evidence or {}

    hits = int(ev.get("hits") or 0)
    facts = int(ev.get("facts") or 0)
    empty_lib = hits == 0 and facts == 0 and ev.get("hits") is not None

    if how.startswith("reasoning over knowledge (LLM"):
        # Strong grounding only when the reasoner marked verified; weak hits stay modest
        # so the critic can escalate instead of sounding certain.
        if verified:
            return 0.80
        return 0.42
    if how == "reasoning (LLM)" or (how.startswith("reasoning (") and "llm" in how.lower()):
        # Open LLM: still modest when the library was empty (System-2 + research),
        # but above the honesty cliff so useful general reasoning is not rewritten.
        if empty_lib:
            return 0.40
        return 0.55 if verified else 0.48
    if how.startswith("analysis over your"):
        # Config aggregate: only high confidence when a real match was verified
        return 0.78 if verified else 0.25
    if how.startswith("skill:"):
        return 0.90                                     # user-defined reflex, exact match
    if how.startswith("data analysis ("):
        return 0.96                                     # exact computation over the table
    if how.startswith("reasoning (") and "llm" not in how.lower():
        return 0.82                                     # structured inference over the graph/rules
    if how.startswith("planning ("):
        return 0.72 if verified else 0.20               # grounded plan vs "no knowledge"
    if how.startswith("world model ("):
        return float(result.get("confidence", 0.72))    # depth-based, set by the simulator
    if how in VERIFIED_EXACT:
        return 0.95 if verified else 0.50               # machine-checked (or check failed)
    if how in DETERMINISTIC:
        return 0.90
    if how in RETRIEVAL:
        top = float(ev.get("top", 0.0))                 # best retrieval similarity
        # hits/facts already computed above
        c = 0.35
        c += 0.45 * min(top / 0.45, 1.0)                # knowledge quality
        c += 0.10 * min(hits / 3.0, 1.0)                # corroboration breadth
        if facts:
            c += 0.20                                   # stored user facts are exact
        if not verified:
            c -= 0.20
        return max(0.10, min(0.92, c))
    if how == "generation":
        return 0.30                                     # creative text — flagged unverified
    if how == "no-source":
        return 0.08                                     # an honest "I don't know"
    return 0.60 if verified else 0.35                   # anything else: modest default
