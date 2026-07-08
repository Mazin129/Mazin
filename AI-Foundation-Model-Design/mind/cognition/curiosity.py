"""
curiosity  —  the Curiosity Engine.  [CORTEX-OS §12]

The drive that makes Vio smarter over time: notice what it doesn't know, and want to
close the gap. When an answer comes back as "I don't know" (or very low confidence),
curiosity logs the topic as a KNOWLEDGE GAP and can:

  • append a gentle, intelligent follow-up so the user can teach it right then, and
  • keep a queue of learning goals it would pursue (surfaced via "what do you want to
    learn?" and, in a later phase, during idle time via active inference).

PERFORMANCE: gap logging is O(1) on the miss path only; it never runs when Vio already
answered well, so it adds nothing to normal, confident replies.
"""

from __future__ import annotations

import json
import os
import re
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAPS_FILE = os.path.join(HERE, "gaps.json")
MAX_GAPS = 500

_WORD = re.compile(r"[a-zA-Z0-9؀-ۿ]+")
_STOP = {"the", "a", "an", "is", "are", "of", "to", "in", "on", "for", "what", "who",
         "how", "why", "and", "i", "you", "it", "do", "does", "my", "me", "that", "this",
         "about", "tell", "can"}


def _topic(q):
    ws = [w for w in _WORD.findall((q or "").lower()) if len(w) > 2 and w not in _STOP]
    return " ".join(ws[:5])


class Curiosity:
    def __init__(self, path=GAPS_FILE):
        self.path = path
        self.gaps = {}                 # topic -> {count, first, last, example}
        if os.path.exists(path):
            try:
                self.gaps = json.load(open(path, encoding="utf-8"))
            except (ValueError, OSError):
                self.gaps = {}

    def note_gap(self, q):
        """Record that Vio didn't know something. Returns a follow-up line to append."""
        topic = _topic(q)
        if not topic:
            return None
        g = self.gaps.get(topic, {"count": 0, "first": time.time(), "example": q.strip()})
        g["count"] += 1
        g["last"] = time.time()
        self.gaps[topic] = g
        if len(self.gaps) > MAX_GAPS:                # keep the most-asked gaps
            self.gaps = dict(sorted(self.gaps.items(), key=lambda kv: -kv[1]["count"])[:MAX_GAPS])
        self._save()
        again = " (you've asked before)" if g["count"] > 1 else ""
        return (f"I'd like to learn about “{topic}”{again} — teach me with "
                f"“teach: …”, a file (📄), or a repo, and I'll remember it.")

    def wishlist(self, n=5):
        """The topics Vio most wants to learn (most-asked unknowns)."""
        ranked = sorted(self.gaps.items(), key=lambda kv: -kv[1]["count"])[:n]
        return [{"topic": t, "count": g["count"]} for t, g in ranked]

    def resolved(self, q):
        """Called when Vio successfully answers — clears a matching gap it has closed."""
        topic = _topic(q)
        if topic in self.gaps:
            del self.gaps[topic]
            self._save()

    def summary(self):
        return {"gaps": len(self.gaps)}

    def _save(self):
        try:
            json.dump(self.gaps, open(self.path, "w", encoding="utf-8"), ensure_ascii=False)
        except OSError:
            pass

    def clear(self):
        self.gaps = {}
        if os.path.exists(self.path):
            os.remove(self.path)
