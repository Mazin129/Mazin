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

    def stats(self):
        """Real, inspectable size of the trained language model."""
        contexts = sum(len(m) for m in self.models)
        vocab = set()
        for m in self.models:
            for ctx, dist in m.items():
                vocab.update(dist.keys())
        return {"passages": self._trained_on, "contexts": contexts,
                "vocab": len(vocab), "order": self.order}

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

    # ---- synthesis: compose a grounded, natural-language answer ----
    @staticmethod
    def _tidy_sentence(s):
        s = re.sub(r"\s+", " ", s.strip())
        s = re.sub(r"\s+([.,;:!?])", r"\1", s)
        if s and s[-1] not in ".!?:":
            s += "."
        return s

    _DEF_CUE = re.compile(r"\b(is|are|means?|refers to|description|defined|used to|"
                          r"lets you|allows|enables|tests?|displays?|configures?)\b", re.I)

    def _lead(self, question):
        """A short, natural opener matched to a clean 'what is X' / 'how' question.
        It only frames the retrieved facts — it never adds information."""
        q = question.strip().lower()
        m = re.match(r"(what\s+(is|are)|who\s+(is|are)|define|explain)\s+(the\s+)?(.+?)[\s?.]*$", q)
        if m:
            subj = m.group(5).strip()
            if 0 < len(subj.split()) <= 5:
                return f"{subj[:1].upper()}{subj[1:]} — "
        if re.match(r"how\b", q):
            return "Here's how: "
        return ""

    def synthesize(self, question, passages, facts=()):
        kw = set(_keywords(question))
        if not kw:
            return None
        cand = []
        seen = set()
        for p in passages:
            for s in _sentences(p):
                key = s.lower()[:60]
                if key in seen:
                    continue
                seen.add(key)
                overlap = len(kw & set(_keywords(s)))
                if overlap:
                    cand.append((overlap, s))
        rel_facts = [f for f in facts if kw & set(_keywords(f))]
        if not cand and not rel_facts:
            return None

        picked = []
        if cand:
            best = max(o for o, _ in cand)
            # keep only the top relevance tier — this is what stops a query for one
            # command/topic from pulling in sentences that are really about another.
            tier = [s for o, s in cand if o >= best] or [s for _, s in cand]
            if len(tier) < 2:                       # broaden slightly if too thin
                tier = [s for o, s in cand if o >= best - 1]
            # order: a defining/description sentence first, then by original appearance
            tier.sort(key=lambda s: (0 if self._DEF_CUE.search(s) else 1, len(s)))
            for s in tier[:3]:
                t = self._tidy_sentence(s)
                if t not in picked:
                    picked.append(t)

        parts = []
        if rel_facts:
            parts.append(" ".join(self._tidy_sentence(f) for f in rel_facts))
        if picked:
            body = " ".join(picked)
            lead = self._lead(question) if not rel_facts else ""
            if lead and picked[0].lower().startswith(lead.rstrip(" —").lower()):
                lead = ""                            # avoid "Ping — Ping is…"
            parts.append(lead + body)
        return "\n\n".join(parts) if parts else None


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
