"""
consolidation  —  the Memory Consolidation "sleep" cycle.  [CORTEX-OS §14]

When Vio is idle it reorganizes memory — the single biggest source of long-term
improvement. Like hippocampal replay -> neocortical consolidation, and §02.5's
"memory-consistency distillation". Each pass:

  1. MERGE duplicates     — collapse near-identical library passages to one canonical.
  2. MINE relations       — re-scan consolidated knowledge for causal/is_a/… edges the
                            teach-time pass missed, growing the Knowledge Graph.
  3. PRUNE the obsolete   — drop old, never-useful (zero-reward) episodes; keep every
                            rewarding one (active forgetting keeps recall fast + current).
  4. STRENGTHEN + REPORT  — surface what changed so improvement is visible.

SAFETY / PERFORMANCE: additive and reversible in spirit — merging keeps a canonical,
pruning only removes clearly-obsolete zero-reward episodes, and high-reward memories
are never touched. It runs OFF the hot path (idle timer or an explicit "consolidate"
command), is time-sliced/bounded, and is a no-op when there's nothing to do — so it can
never make answering slow.
"""

from __future__ import annotations

import re
import time

_WS = re.compile(r"\s+")


def _canon(text):
    return _WS.sub(" ", (text or "").strip().lower())


class Consolidator:
    def __init__(self, mind):
        self.mind = mind
        self.last_run = 0.0

    def consolidate(self, max_ms=400):
        """Run one bounded sleep pass. Returns a report of what changed."""
        t0 = time.perf_counter()
        report = {"merged": 0, "edges": 0, "pruned": 0, "library": 0, "episodes": 0}

        report["merged"] = self._merge_duplicates()
        if (time.perf_counter() - t0) * 1000 < max_ms:
            report["edges"] = self._mine_relations()
        report["pruned"] = self._prune_episodes()

        # rebuild the retrieval index + language model once, only if content changed
        if report["merged"]:
            self.mind._retrain()

        report["library"] = len(self.mind.lib.docs)
        report["episodes"] = len(self.mind.episodic.episodes)
        report["ms"] = round((time.perf_counter() - t0) * 1000, 1)
        self.last_run = time.time()
        return report

    # ---- 1. merge duplicate passages --------------------------------------
    def _merge_duplicates(self):
        docs = self.mind.lib.docs
        seen, keep, removed = set(), [], 0
        for d in docs:
            key = _canon(d)[:120]
            if key in seen:
                removed += 1
                continue
            seen.add(key)
            keep.append(d)
        if removed:
            self.mind.lib.docs = keep
        return removed

    # ---- 2. mine relations the teach-time pass missed ---------------------
    def _mine_relations(self, budget=400):
        before = self.mind.graph.summary()["edges"]
        for d in self.mind.lib.docs[:budget]:      # bounded scan
            self.mind.graph.learn_text(d)
        return self.mind.graph.summary()["edges"] - before

    # ---- 3. forget the obsolete -------------------------------------------
    def _prune_episodes(self):
        epi = self.mind.episodic
        eps = epi.episodes
        if len(eps) < 200:                          # nothing worth pruning yet
            return 0
        cutoff = time.time() - 30 * 86400           # older than 30 days
        keep = [e for e in eps if e.get("reward", 0) > 0 or e["t"] > cutoff]
        removed = len(eps) - len(keep)
        if removed:
            epi.episodes = keep
            epi._save()
        return removed

    def summary(self):
        return {"last_run": (time.strftime("%Y-%m-%d %H:%M", time.localtime(self.last_run))
                             if self.last_run else "never")}
