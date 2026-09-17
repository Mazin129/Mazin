"""
calibration  —  does Vio's confidence mean anything?  [CORTEX-OS §10, closing the loop]

Phase 2 shipped a confidence number from hand-set priors. Phase 6 measures whether that
number is HONEST, using real feedback: when you mark an answer right (👍) or wrong (👎),
the episode is graded. Calibration then compares the confidence Vio stated against how
often it was actually right, and derives a single correction scalar the Executive applies
to future confidences — so the number self-tunes toward the truth over time.

  well-calibrated  : of the answers it was ~80% sure of, ~80% were right.
  overconfident    : it claimed 80% but was right 55% → scale confidence DOWN.
  underconfident   : it claimed 60% but was right 90% → scale confidence UP.

Runs on demand and during idle consolidation — never on the hot path. With little
feedback it stays neutral (scalar 1.0) rather than over-reacting to noise.
"""

from __future__ import annotations

MIN_GRADED = 8            # need at least this many graded answers before adjusting


class Calibration:
    def __init__(self, mind):
        self.mind = mind
        self.scalar = 1.0                 # multiplicative correction on future confidence

    def _graded(self):
        out = []
        for e in self.mind.episodic.episodes:
            if e.get("outcome") in ("correct", "wrong"):
                c = (e.get("tags") or {}).get("confidence")
                if c is not None:
                    out.append((float(c), 1 if e["outcome"] == "correct" else 0))
        return out

    def refresh(self):
        """Recompute the correction scalar from graded feedback. Returns it."""
        g = self._graded()
        if len(g) < MIN_GRADED:
            self.scalar = 1.0
            return self.scalar
        stated = sum(c for c, _ in g) / len(g)
        actual = sum(k for _, k in g) / len(g)
        if stated <= 0.01:
            self.scalar = 1.0
        else:
            # move the scalar gently toward (actual/stated); clamp so one bad streak
            # can't wildly distort confidence
            target = max(0.5, min(1.5, actual / stated))
            self.scalar = round(0.7 * self.scalar + 0.3 * target, 3)
        return self.scalar

    def report(self):
        """A human-readable reliability report."""
        g = self._graded()
        if len(g) < MIN_GRADED:
            return (f"I don't have enough graded answers yet ({len(g)}/{MIN_GRADED}). "
                    "Mark my answers 👍/👎 and I'll learn how much to trust myself.")
        # reliability by confidence band
        bands = {}
        for c, k in g:
            b = round(c * 10) / 10
            bands.setdefault(b, []).append(k)
        stated = sum(c for c, _ in g) / len(g)
        actual = sum(k for _, k in g) / len(g)
        brier = sum((c - k) ** 2 for c, k in g) / len(g)
        gap = stated - actual
        verdict = ("well-calibrated" if abs(gap) < 0.1 else
                   "overconfident" if gap > 0 else "underconfident")
        lines = [f"Over {len(g)} answers you graded, I was right {actual*100:.0f}% of the "
                 f"time and on average {stated*100:.0f}% sure — I'm {verdict}.",
                 f"Brier score: {brier:.3f} (lower is better). Confidence correction now "
                 f"×{self.scalar:.2f}.",
                 "By how sure I was:"]
        for b in sorted(bands, reverse=True):
            v = bands[b]
            lines.append(f"  ~{int(b*100)}% sure → right {sum(v)/len(v)*100:.0f}% "
                         f"({len(v)} answer{'s' if len(v) != 1 else ''})")
        return "\n".join(lines)

    def summary(self):
        return {"graded": len(self._graded()), "scalar": self.scalar}
