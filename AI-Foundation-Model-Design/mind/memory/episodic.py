"""
episodic  —  Episodic Memory: Vio's autobiographical timeline.  [CORTEX-OS §3.3]

The hippocampal fast store. Every interaction becomes an EPISODE written in ONE shot
(no training), recalled later by *when* (recency) or by *what it was like* (content
similarity + reward). This is what lets Vio say "we talked about X yesterday" and
"I've solved this before" — memory the flat retrieval library never had.

Each episode: { time, kind, cue, detail, outcome, reward, tags }.
  cue     — a short searchable summary (the question / event)
  detail  — the answer / what happened
  outcome — "answered" | "solved" | "learned" | "unknown" | "corrected" …
  reward  — a small signal (+1 solved, 0 unknown) used later by consolidation.

Storage: append-only JSON on disk (user-owned, gitignored). Recall is a cheap
keyword-overlap + recency + reward score — the same honest, inspectable style as the
rest of Vio (embeddings arrive in a later phase; the API here won't change).
"""

from __future__ import annotations

import json
import os
import re
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EPI_FILE = os.path.join(HERE, "episodic.json")
MAX_EPISODES = 20000            # cap the on-disk log; oldest low-reward pruned beyond this

_WORD = re.compile(r"[a-zA-Z0-9؀-ۿ]+")
_STOP = {"the", "a", "an", "is", "are", "was", "of", "to", "in", "on", "for", "what",
         "who", "how", "why", "and", "i", "you", "it", "do", "does", "my", "me", "that"}


def _keywords(text):
    return {w for w in _WORD.findall((text or "").lower()) if len(w) > 2 and w not in _STOP}


class EpisodicMemory:
    def __init__(self, path=EPI_FILE):
        self.path = path
        self.episodes = []
        if os.path.exists(path):
            try:
                self.episodes = json.load(open(path, encoding="utf-8"))
            except (ValueError, OSError):
                self.episodes = []

    # ---- write (one-shot) --------------------------------------------------
    def record(self, cue, detail, outcome="answered", reward=0.0, kind="chat", tags=None):
        ep = {"t": time.time(), "kind": kind, "cue": cue, "detail": detail,
              "outcome": outcome, "reward": float(reward), "tags": tags or {}}
        self.episodes.append(ep)
        if len(self.episodes) > MAX_EPISODES:
            self._prune()
        self._save()
        return ep

    # ---- recall ------------------------------------------------------------
    def recall(self, query, k=3, min_score=0.15):
        """Most relevant past episodes, scored by content overlap + recency + reward."""
        qk = _keywords(query)
        if not qk:
            return []
        now = time.time()
        scored = []
        for ep in self.episodes:
            ek = _keywords(ep["cue"] + " " + ep["detail"])
            if not ek:
                continue
            overlap = len(qk & ek) / (len(qk) ** 0.5 * len(ek) ** 0.5)   # cosine-ish
            recency = 1.0 / (1.0 + (now - ep["t"]) / 86400.0)            # days-ago decay
            score = overlap + 0.15 * recency + 0.1 * max(0.0, ep["reward"])
            if overlap > 0:
                scored.append((score, ep))
        scored.sort(key=lambda s: -s[0])
        return [ep for s, ep in scored[:k] if s >= min_score]

    def find_solved(self, query, min_overlap=0.6):
        """Have I solved (almost) exactly this before? Returns the cached answer or None."""
        qk = _keywords(query)
        if not qk:
            return None
        for ep in reversed(self.episodes):                # most recent first
            if ep["outcome"] not in ("solved", "answered"):
                continue
            ek = _keywords(ep["cue"])
            if ek and len(qk & ek) / max(len(qk), len(ek)) >= min_overlap:
                return ep
        return None

    def recent(self, n=5, kind=None):
        eps = [e for e in self.episodes if kind is None or e["kind"] == kind]
        return eps[-n:][::-1]

    def summary(self):
        return {"episodes": len(self.episodes),
                "solved": sum(1 for e in self.episodes if e["outcome"] == "solved"),
                "learned": sum(1 for e in self.episodes if e["outcome"] == "learned"),
                "since": (time.strftime("%Y-%m-%d", time.localtime(self.episodes[0]["t"]))
                          if self.episodes else None)}

    # ---- internals ---------------------------------------------------------
    def _prune(self):
        # keep all high-reward episodes; drop the oldest zero-reward ones past the cap
        keep = [e for e in self.episodes if e["reward"] > 0]
        rest = [e for e in self.episodes if e["reward"] <= 0]
        overflow = len(self.episodes) - MAX_EPISODES
        rest = rest[overflow:] if overflow < len(rest) else []
        self.episodes = sorted(keep + rest, key=lambda e: e["t"])

    def _save(self):
        try:
            json.dump(self.episodes, open(self.path, "w", encoding="utf-8"),
                      ensure_ascii=False)
        except OSError:
            pass

    def clear(self):
        self.episodes = []
        if os.path.exists(self.path):
            os.remove(self.path)


if __name__ == "__main__":
    epi = EpisodicMemory(path="/tmp/_epi_test.json")
    epi.clear()
    epi = EpisodicMemory(path="/tmp/_epi_test.json")
    epi.record("what is execute ping?", "tests connectivity to a host", "answered", 0.5)
    epi.record("solve x^2-5x+6=0", "x = 2, 3", "solved", 1.0)
    epi.record("what is a vlan?", "a virtual LAN segments a network", "answered", 0.5)
    print("recall 'ping connectivity':", [e["cue"] for e in epi.recall("ping connectivity")])
    print("solved before? 'solve x^2 - 5x + 6 = 0':",
          (epi.find_solved("solve x^2 - 5x + 6 = 0") or {}).get("detail"))
    print("summary:", epi.summary())
    epi.clear()
