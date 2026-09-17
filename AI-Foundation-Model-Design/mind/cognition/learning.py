"""
learning  —  the Learning Engine: turn experience into reusable competence.  [CORTEX-OS §13]

Using Vio IS training it. This engine reads the episodic record and:

  • extracts LESSONS — what topics come up, what gets solved, where it fails;
  • PROMOTES repeated wins — a factual question asked and answered consistently more
    than once becomes an auto-skill (an instant reflex), so practice makes it a "single
    move" (procedural chunking, §3.4);
  • never promotes something it answered inconsistently or couldn't verify — a wrong
    reflex is worse than none.

Promotion runs during consolidation (idle), never on the hot path.
"""

from __future__ import annotations

import re
from collections import Counter

_WORD = re.compile(r"[a-zA-Z0-9؀-ۿ]+")
_STOP = {"the", "a", "an", "is", "are", "of", "to", "in", "on", "for", "what", "who",
         "how", "why", "and", "i", "you", "it", "do", "does", "my", "me", "that", "this"}


def _norm_q(q):
    return " ".join(w for w in _WORD.findall((q or "").lower()) if w not in _STOP)


class LearningEngine:
    def __init__(self, mind):
        self.mind = mind

    def promote_repeats(self, min_count=2):
        """Find questions asked >=min_count times with a STABLE answer and cache them as
        instant reflexes. Returns the number promoted. Conservative: only stable,
        already-verified answers become reflexes."""
        eps = self.mind.episodic.episodes
        by_q = {}
        for e in eps:
            if e.get("outcome") not in ("answered", "solved"):
                continue
            key = _norm_q(e.get("cue", ""))
            if len(key) < 4:
                continue
            by_q.setdefault(key, []).append(e)
        promoted = 0
        for key, group in by_q.items():
            if len(group) < min_count:
                continue
            answers = Counter(_canon(g["detail"]) for g in group)
            top, n = answers.most_common(1)[0]
            # promote only if the SAME answer came back every time (stable knowledge)
            if n == len(group) and top and top not in self.mind.mem["solved"].values():
                original = next(g["cue"] for g in group)      # store under the real phrasing
                if original not in self.mind.mem["solved"]:
                    self.mind.mem["solved"][original] = group[-1]["detail"]
                    promoted += 1
        if promoted:
            self.mind._save()
        return promoted

    def lessons(self):
        """A short self-report: what Vio has been doing and getting good at."""
        eps = self.mind.episodic.episodes
        if not eps:
            return "I don't have any experience yet — ask me things and I'll learn from them."
        topics = Counter()
        for e in eps:
            for w in _WORD.findall(e.get("cue", "").lower()):
                if len(w) > 3 and w not in _STOP:
                    topics[w] += 1
        solved = sum(1 for e in eps if e["outcome"] == "solved")
        learned = sum(1 for e in eps if e["outcome"] == "learned")
        top = ", ".join(w for w, _ in topics.most_common(6))
        return (f"From {len(eps)} interactions I've solved {solved} problems and learned "
                f"{learned} things. You ask most about: {top}.")


def _canon(text):
    return re.sub(r"\s+", " ", (text or "").strip().lower())
