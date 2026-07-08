"""
critic  —  the Self-Critic.  [CORTEX-OS §11]

Before a System-2 answer goes out, the critic interrogates it (the brain's error
monitoring). Checks run cheapest-first and escalate only when needed:

  1. Conflicting memory?  Did I answer a similar question differently before?
     (episodic containment check — flag it, lower confidence, stay transparent)
  2. Search again?        If evidence is thin, re-search with a reformulated
     keyword-only query and keep the better-supported answer.
  3. Be honest.           If confidence is still too low, do NOT bluff: say so,
     show the best lead found, and ask to be taught.

This generalizes Vio's "I don't know rather than guess" from the retrieval gate to
EVERY deliberative answer. The critic never touches System-1 results (machine-
verified math, deterministic tools) — there is nothing for it to second-guess.
"""

from __future__ import annotations

import re

from cognition.confidence import score as _score, RETRIEVAL

_WORD = re.compile(r"[a-zA-Z0-9؀-ۿ]+")
_STOP = {"the", "a", "an", "is", "are", "was", "of", "to", "in", "on", "for", "what",
         "who", "how", "why", "and", "i", "you", "it", "do", "does", "my", "me", "that",
         "this", "about", "tell"}

RESEARCH_THRESHOLD = 0.55        # below this, try to find stronger support
HONESTY_THRESHOLD = 0.35         # below this, admit uncertainty instead of answering


def _keywords(text):
    return {w for w in _WORD.findall((text or "").lower()) if len(w) > 2 and w not in _STOP}


def review(q, result, conf, mind):
    """Run the checklist. Returns (possibly revised result, final confidence)."""
    trace = list(result.get("trace", []))
    how = result.get("how", "")

    # -- 1. conflicting memory? ------------------------------------------------
    conflict = _conflicting_memory(q, result, mind)
    if conflict:
        conf = max(0.10, conf - 0.15)
        trace.append("self-critic: I answered a similar question differently before — "
                     "flagging the inconsistency instead of hiding it")

    if how in RETRIEVAL:
        # -- 2. search again with reformulated keys? ----------------------------
        if conf < RESEARCH_THRESHOLD:
            better = _research(q, mind)
            if better:
                answer2, ev2 = better
                cand = dict(result, answer=answer2)
                conf2 = _score(cand, ev2)
                if conf2 > conf and answer2.strip() != result.get("answer", "").strip():
                    result = cand
                    conf = conf2
                    trace.append("self-critic: re-searched with a keyword query and "
                                 "found stronger support")

        # -- 3. still weak: be honest, don't bluff ------------------------------
        if conf < HONESTY_THRESHOLD:
            lead = (result.get("answer") or "").strip().replace("\n", " ")
            lead = lead[:220] + ("…" if len(lead) > 220 else "")
            result = dict(result)
            result["answer"] = ("I'm not confident about this — treat it as a lead, "
                                "not an answer.\n"
                                f"The closest I found: {lead}\n"
                                "Teach me more about it (teach: … or 📄) and I'll do better.")
            result["verified"] = False
            result["how"] = how + " · low confidence"
            trace.append("self-critic: confidence too low — answered honestly "
                         "instead of guessing")

    result = dict(result)
    result["trace"] = trace
    return result, conf


def _research(q, mind):
    """Checklist item 'should I search again?' — keyword-only requery at a lower
    threshold; returns (answer, evidence) only if a grounded synthesis comes back."""
    kws = list(_keywords(q))
    if not kws:
        return None
    hits = [(d, s) for d, s in mind.lib.search(" ".join(kws), k=6) if s > 0.08]
    if not hits:
        return None
    syn = mind.thinker.synthesize(q, [d for d, _ in hits], mind.mem.get("facts", []))
    if not syn:
        return None
    return syn, {"top": hits[0][1], "hits": len(hits), "facts": 0}


_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def _conflicting_memory(q, result, mind):
    """Checklist item 'is there conflicting memory?' — compare this answer against
    what Vio told the user for the SAME past question. Flags two kinds of conflict:
      • topic divergence — the answers share almost no content (containment), and
      • value contradiction — same question, but the KEY NUMBERS differ (e.g. an MTU
        of 1500 vs 9000, a timer of 10 vs 30) — the common, dangerous case for a
        technical assistant, which pure word-overlap misses."""
    now_ans = result.get("answer", "")
    now_kw = _keywords(now_ans)
    if not now_kw:
        return False
    try:
        for ep in mind.episodic.recall(q, k=2):
            if ep.get("outcome") not in ("answered", "solved"):
                continue
            if len(_keywords(ep.get("cue", "")) & _keywords(q)) < 2:
                continue                       # not really the same question
            old_ans = ep.get("detail", "")
            old_kw = _keywords(old_ans)
            if not old_kw:
                continue
            containment = len(now_kw & old_kw) / min(len(now_kw), len(old_kw))
            if containment < 0.25:
                return True                    # they're basically different answers
            old_nums, new_nums = set(_NUM.findall(old_ans)), set(_NUM.findall(now_ans))
            if old_nums and new_nums and not (old_nums & new_nums):
                return True                    # same question, entirely different numbers
    except Exception:
        pass                                    # a broken check must never block answering
    return False
