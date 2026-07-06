"""
Think  —  Vio's open-ended thinking engine (local, no market model).

Two honest capabilities, both running 100% on your laptop with no internet and no
downloaded model:

  1. SYNTHESIS ("reason over what I know").  For an open question, Vio gathers the
     sentences across its whole library + memory that actually bear on the question,
     ranks them, removes duplicates, and composes ONE grounded answer that draws on
     several sources at once — instead of dumping a single passage. Every sentence is
     traceable to something you taught it, so it still never hallucinates.

  2. GENERATION ("write / continue / imagine …").  Vio trains a small word-level
     n-gram language model ON THE BOOKS YOU TEACH IT and can generate new text in that
     style. This is a REAL (small) language model that is *yours* and learns from your
     documents. It is not GPT-sized — it is the laptop-native seed of the "language
     cortex", and it grows sharper the more you teach it.

No eval, no exec — it only ever consumes text already in the library. Pure stdlib.
"""

import random
import re
from collections import Counter, defaultdict

_STOP = {"the", "a", "an", "is", "are", "was", "were", "be", "of", "to", "in", "on",
         "for", "and", "or", "but", "with", "as", "by", "at", "from", "that", "this",
         "these", "those", "it", "its", "into", "than", "then", "so", "such", "can",
         "will", "would", "do", "does", "did", "has", "have", "had", "what", "who",
         "where", "when", "why", "how", "which", "about", "you", "your", "i", "me",
         "my", "we", "they", "he", "she", "them", "their"}


def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?؟])\s+|\n+", text.strip())
            if len(s.strip().split()) >= 3]


def _keywords(q):
    return [w for w in re.findall(r"[a-zA-Z؀-ۿ]+", q.lower())
            if len(w) > 2 and w not in _STOP]


class Thinker:
    """Synthesises grounded answers and generates text learned from the library."""

    def __init__(self):
        self.order = 3
        self.models = [defaultdict(Counter) for _ in range(self.order)]  # backoff n-grams
        self.starts = []            # sentence-start contexts, for seeding generation
        self._trained_on = 0

    # ---- learning: build the n-gram language model from the library text ----
    def train(self, docs):
        self.models = [defaultdict(Counter) for _ in range(self.order)]
        self.starts = []
        for doc in docs:
            for sent in _sentences(doc):
                toks = re.findall(r"[A-Za-z0-9'؀-ۿ]+|[.,;:!?،؛؟]", sent)
                if len(toks) < 3:
                    continue
                toks = toks + ["</s>"]
                self.starts.append(tuple(toks[:2]))
                for i in range(len(toks)):
                    for o in range(1, self.order + 1):     # unigram..trigram contexts
                        if i - o < 0:
                            continue
                        ctx = tuple(toks[i - o:i])
                        self.models[o - 1][ctx][toks[i]] += 1
        self._trained_on = len(docs)
        return self._trained_on

    def _next(self, history):
        """Pick the next word using the longest context we have data for (backoff)."""
        for o in range(self.order, 0, -1):
            ctx = tuple(history[-o:])
            dist = self.models[o - 1].get(ctx)
            if dist:
                words, weights = zip(*dist.items())
                return random.choices(words, weights=weights)[0]
        return "</s>"

    def generate(self, prompt="", max_words=40):
        if not self.starts:
            return None
        # topic-aware seeding: start from a real context that mentions the topic word
        kws = [w for w in re.findall(r"[a-z'؀-ۿ]+", prompt.lower())
               if len(w) > 2 and w not in _STOP]
        history = None
        if kws:
            cands = [list(ctx) for ctx in self.models[1]
                     if any(k in w.lower() for w in ctx for k in kws)]
            if cands:
                history = random.choice(cands)
        if history is None:
            seed = re.findall(r"[A-Za-z0-9'؀-ۿ]+|[.,;:!?،؛؟]", prompt)
            history = seed[-2:] if len(seed) >= 2 else list(random.choice(self.starts))
        out = list(history)
        for _ in range(max_words):
            nxt = self._next(history)
            if nxt == "</s>":
                if len(out) >= 6:
                    break
                history = list(random.choice(self.starts)); out += history; continue
            out.append(nxt); history.append(nxt)
        text = " ".join(out)
        text = re.sub(r"\s+([.,;:!?])", r"\1", text)          # tidy punctuation spacing
        text = re.sub(r"\s+", " ", text).strip()
        if text and text[-1] not in ".!?":
            text += " …"
        return text[0].upper() + text[1:] if text else None

    # ---- synthesis: compose a grounded answer from many passages at once ----
    def synthesize(self, question, passages, facts=()):
        kw = set(_keywords(question))
        if not kw:
            return None
        scored = []
        seen = set()
        for p in passages:
            for s in _sentences(p):
                key = s.lower()[:60]
                if key in seen:
                    continue
                seen.add(key)
                swords = set(_keywords(s))
                overlap = len(kw & swords)
                if overlap:
                    scored.append((overlap / (1 + 0.03 * len(swords)), s))
        scored.sort(key=lambda t: -t[0])
        picked = [s for _, s in scored[:3]]
        if not picked and not facts:
            return None
        lines = []
        rel_facts = [f for f in facts if kw & set(_keywords(f))]
        if rel_facts:
            lines.append("From what I know about you: " + "; ".join(rel_facts) + ".")
        if picked:
            lines.append("Putting together what you've taught me:")
            lines += [f"  • {s}" for s in picked]
        return "\n".join(lines) if lines else None


if __name__ == "__main__":
    t = Thinker()
    t.train([
        "The brain learns by strengthening connections between neurons that fire together.",
        "Memory is stored across many neurons, not in one place. Recall reactivates the pattern.",
        "Sleep helps the brain consolidate memories and clear waste from the day.",
    ])
    print("GENERATE:", t.generate("the brain"))
    print("SYNTHESIZE:\n", t.synthesize("how does the brain store memory?",
          ["Memory is stored across many neurons, not in one place. Recall reactivates the pattern.",
           "Sleep helps the brain consolidate memories and clear waste from the day."]))
